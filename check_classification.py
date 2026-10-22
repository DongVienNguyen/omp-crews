"""No-provider classification, safety, preview, persistence, UTF-8 and history checks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from pydantic import ValidationError
import omp_server as server
from crews import omp_adapter as adapter
from crews.classification import classify_role, policy_version
from check_effort_policy import DEFAULT_MODELS, NEED_COMBOS, isolated_home, write_policy

ROOT = Path(__file__).resolve().parent


def rejects(action, fragment):
    try:
        action()
    except (ValueError, ValidationError) as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError(f'Unsafe input accepted: {fragment}')


def bridge(payload, state):
    return subprocess.run(
        [sys.executable, str(ROOT / 'omp_bridge.py')], input=json.dumps(payload, ensure_ascii=False),
        text=True, encoding='utf-8', capture_output=True, timeout=30,
        env={**os.environ, 'CREWS_OMP_HOME': state, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'},
    )


def check_corpus(corpus):
    for case in corpus:
        role = {'kind': case['kind'], 'mission': case['mission'], 'facts': case['facts'],
                'classification': True, 'answers': {'divisible': 0, 'specific': 1}}
        before = deepcopy(role)
        result = adapter.preview(role)
        assert role == before, case['id']
        assert result['policy_version'] == policy_version()
        if case['need'] is None:
            assert result['answers'] is None, case['id']
            assert result['outcome'] == 'requires_classification', case['id']
            assert result['policy_combo'] is None and result['model'] is None, case['id']
            continue
        expected_combo = NEED_COMBOS[case['need']]
        assert result['answers'] == {'need': case['need'], 'difficulty': case['difficulty'],
                                     'divisible': 0, 'specific': 1}, case['id']
        assert result['policy_combo'] == expected_combo, (case['id'], result)
        assert result['model'] == case['model'] == DEFAULT_MODELS[expected_combo], case['id']
        expected_effort = 'low' if case['difficulty'] < 1 else 'medium' if case['difficulty'] < 2 else 'high'
        assert result['reasoning_effort'] == expected_effort, (case['id'], result)


def check_input_safety(declared):
    assert classify_role(declared)['outcome'] == 'declared'
    for difficulty in (1, 1.001, 3):
        role = {**declared, 'answers': {**declared['answers'], 'difficulty': difficulty}}
        assert adapter.preview(role)['policy_combo'] == 'Small'
    for facts in ([], False, 0, ''):
        rejects(lambda: adapter.preview({**declared, 'facts': facts}), 'ClassificationFacts')
    for key in ('unknown_cause', 'consequential_judgment', 'behavior_undecided'):
        rejects(lambda: adapter.preview({**declared, 'facts': {key: True}}), 'answers.need')
    for value in (0, 'false'):
        rejects(lambda: adapter.preview({**declared, 'facts': {'unknown_cause': value}}), 'unknown_cause')
    rejects(lambda: adapter.preview({**declared, 'facts': {'invented': False}}), 'invented')
    rejects(lambda: adapter.preview({**declared, 'classification': True, 'answers': {'divisible': 0}}), 'specific')
    for difficulty in (True, float('nan')):
        rejects(lambda: adapter.preview({**declared, 'answers': {**declared['answers'], 'difficulty': difficulty}}), 'difficulty')


def check_persistence_and_bridge(corpus, declared, project, state):
    assert server.crew_test(declared, project)['model'] == 'code-seek'
    assert adapter.history(project) == [] and not (Path(state) / 'runs.sqlite').exists()
    example = server.minimal_example()
    spec, answers = example['spec'], example['answers']
    lookup = next(case for case in corpus if case['id'] == 'lookup-vi')
    auto = deepcopy(spec)
    auto['task'] = 'Inspect configuration: ' + lookup['mission']
    auto['roles'][0].update(classification=True, solution_space='Chỉ đọc cấu hình',
                            mission='Inspect configuration: ' + lookup['mission'], facts=lookup['facts'],
                            answers={'divisible': 0, 'specific': 1})
    original = deepcopy(auto)
    plan = adapter.prepare_plan(auto, answers, project, 'auto-contract')
    call = plan['waves'][0]['calls'][0]
    assert call['role_answers']['need'] == 'bounded_retrieval'
    assert call['solution_space'] == 'Chỉ đọc cấu hình' and call['facts'] == lookup['facts']
    assert call['declared_role_answers'] == {'divisible': 0, 'specific': 1}
    assert call['classification']['outcome'] == 'deterministic'
    assert auto == original
    rows = server.crew_history(project, 1)
    assert len(rows) == 1 and rows[0]['roles'][0]['status'] == 'planned'
    assert set(rows[0]) == {'run_id', 'project', 'session', 'created', 'roles'}
    assert set(rows[0]['roles'][0]) == {'role_id', 'status', 'model', 'reasoning_effort', 'role_answers', 'routing_reason'}
    assert 'prompt' not in json.dumps(rows)
    with tempfile.TemporaryDirectory() as other:
        assert adapter.history(other) == []
    for limit in (0, 201, True, 1.5):
        rejects(lambda: adapter.history(project, limit), 'limit')
    bad = deepcopy(spec)
    bad['roles'][0]['facts'] = {'unknown_cause': True}
    rejects(lambda: adapter.build_plan(bad, answers, project, 'unsafe'), 'spec.roles.0.answers.need')
    try:
        server.PlanArguments.model_validate({'spec': bad, 'answers': answers, 'project': project, 'session': 'typed'})
    except ValidationError as exc:
        assert ('spec', 'roles', 0, 'answers', 'need') in {error['loc'] for error in exc.errors()}
    else:
        raise AssertionError('Canonical safety accepted contradictory facts')
    unresolved = deepcopy(auto)
    unresolved['roles'][0]['facts'] = {}
    rejects(lambda: adapter.prepare_plan(unresolved, answers, project, 'unresolved'), 'requires_classification')
    rejects(lambda: server.PlanSpec.model_validate(unresolved), 'need')
    result = bridge({'op': 'preview', 'role': auto['roles'][0], 'project': project}, state)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['answers']['need'] == 'bounded_retrieval'
    assert 'Chỉ đọc cấu hình' in auto['roles'][0]['solution_space']
    result = bridge({'op': 'plan', 'spec': bad, 'answers': answers, 'project': project, 'session': 'unsafe-bridge'}, state)
    assert result.returncode == 1 and 'spec.roles.0.answers.need' in json.loads(result.stdout)['error']
    original_version = policy_version()
    policy = {'provider': 'local-provider', 'combos': {
        'Small': {'model': 'small-v2', 'effort': 'Auto'},
        'Medium': {'model': 'medium-v2', 'effort': 'Low'},
        'Large': {'model': 'large-v2', 'effort': 'High'},
    }}
    write_policy(state, policy)
    assert policy_version() != original_version
    assert server.crew_catalog()['model_policy'] == policy
    assert adapter.preview(declared, project)['classifier_model'] == 'local-provider/large-v2:high'
    result = bridge({'op': 'policy'}, state)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == adapter.policy()
    rejects(lambda: adapter.admit(plan['run_id'], call['role_id'], call['prompt'], project, 'auto-contract'), 'policy binding')


def main():
    corpus = json.loads((ROOT / 'examples/routing-corpus.json').read_text(encoding='utf-8'))
    declared = {'kind': 'research', 'mission': 'Read configuration',
                'answers': {'need': 'bounded_retrieval', 'difficulty': 1, 'divisible': 0, 'specific': 1}}
    with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as state, isolated_home(state):
        check_corpus(corpus)
        check_input_safety(declared)
        check_persistence_and_bridge(corpus, declared, project, state)
    print(f'PASS: {len(corpus)} bilingual cases, precedence, strict safety, pure preview, intake, history and UTF-8 bridge')


if __name__ == '__main__':
    main()
