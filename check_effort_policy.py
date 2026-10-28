"""Offline Combo model/effort contracts; run with provisioned runtime Python."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from crews import omp_adapter as adapter


NEED_COMBOS = {
    'mechanical_verification': 'Small',
    'repeatable_task': 'Small',
    'bounded_retrieval': 'Small',
    'everyday_implementation': 'Medium',
    'long_running_agentic': 'Medium',
    'difficult_review': 'Large',
    'integration_architecture': 'Large',
    'specialist': 'Large',
}
DEFAULT_MODELS = {'Small': 'code-seek', 'Medium': 'code-sol', 'Large': 'code-astra'}


@contextmanager
def isolated_home(state):
    previous = os.environ.get('CREWS_OMP_HOME')
    os.environ['CREWS_OMP_HOME'] = str(state)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('CREWS_OMP_HOME', None)
        else:
            os.environ['CREWS_OMP_HOME'] = previous


def rejects(action, fragment):
    try:
        action()
    except ValueError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError(f'Expected refusal containing {fragment!r}')


def role(need, difficulty, kind='research', name='combo-policy-checker'):
    if need=='repeatable_task' and kind=='research':kind='produce'
    if need=='mechanical_verification':kind='check'
    return {
        'name': name, 'kind': kind,
        'mission': 'Inspect Combo model and effort policy', 'deliverable': name + '.json',
        'scope': [name + '.txt'] if kind in ('produce', 'integrate') else [],
        'inputs': ['fixture.txt'] if kind == 'check' else [],
        'acceptance': ['Report assigned Combo and effort accurately'],
        'criteria': ['Report assigned Combo and effort accurately'],
        'answers': {'need': need, 'difficulty': difficulty, 'divisible': 0, 'specific': 1},
    }


def task_answers(need, difficulty, verifier=False):
    return {
        'need': {'choice': need, 'confidence': 1, 'probabilities': {need: 1}},
        'difficulty': {'score': difficulty}, 'divisible': {'noul': 0},
        'needs_verifier': {'noul': int(verifier)},
    }


def plan(state, need, difficulty, kind='research'):
    result = adapter.build_plan(
        {'task': 'Inspect Combo model and effort policy', 'roles': [role(need, difficulty, kind)]},
        task_answers(need, difficulty, kind == 'check'), str(Path(state).resolve()), 'combo-policy', state,
    )
    return result, result['waves'][0]['calls'][0]


def fail(state, result, call):
    adapter.admit(result['run_id'], call['role_id'], call['prompt'], result['project'], result['session'], state)
    adapter.record(result['run_id'], call['role_id'],
                   {'status': 'FAILED', 'verification': ['Combo check failed']},
                   result['project'], result['session'], state)


def escalate(state, result, call, repair=False):
    return adapter.escalate(result['run_id'], call['role_id'], 'Recorded Combo check failure',
                            result['project'], result['session'], repair, state)['call']


def write_policy(state, policy):
    (Path(state) / 'policy.json').write_text(json.dumps(policy), encoding='utf-8')


def check_auto(state):
    for need, combo in NEED_COMBOS.items():
        kind = 'check' if need == 'mechanical_verification' else 'produce' if need=='repeatable_task' else 'research'
        for difficulty, effort in [(0, 'low'), (0.999, 'low'), (1, 'medium'),
                                   (1.999, 'medium'), (2, 'high'), (3, 'high')]:
            _, call = plan(state, need, difficulty, kind)
            assert (call['policy_combo'], call['model'], call['reasoning_effort']) == (
                combo, DEFAULT_MODELS[combo], effort), call
            assert call['agent_type'] == f'crew-{kind}-{combo.lower()}', call
            assert call['configured_effort'] == 'Auto', call
            assert call['policy_binding'] == adapter.policy_binding(state), call


def check_explicit_and_retries(state):
    policy = {'provider': 'local-provider', 'combos': {
        'Small': {'model': 'shared-model', 'effort': 'HIGH'},
        'Medium': {'model': 'shared-model', 'effort': 'Low'},
        'Large': {'model': 'large-model', 'effort': 'Medium'},
    }}
    write_policy(state, policy)
    normalized = adapter.model_policy(state)
    assert normalized['combos']['Small']['effort'] == 'High'
    for need, combo in NEED_COMBOS.items():
        configured = normalized['combos'][combo]
        for difficulty in (0, 3):
            _, call = plan(state, need, difficulty)
            assert (call['policy_combo'], call['model'], call['reasoning_effort']) == (
                combo, configured['model'], configured['effort'].lower()), call
    result, call = plan(state, 'bounded_retrieval', 2.5)
    fail(state, result, call)
    repaired = escalate(state, result, call, repair=True)
    assert (repaired['policy_combo'], repaired['reasoning_effort']) == ('Small', 'high')
    assert repaired['role_answers'] == call['role_answers']
    fail(state, result, repaired)
    raised = escalate(state, result, repaired)
    assert (raised['policy_combo'], raised['reasoning_effort'], raised['model']) == ('Medium', 'low', 'shared-model')
    fail(state, result, raised)
    strongest = escalate(state, result, raised)
    assert (strongest['policy_combo'], strongest['reasoning_effort']) == ('Large', 'medium')
    fail(state, result, strongest)
    rejects(lambda: escalate(state, result, strongest), 'Large')

    # Auto escalation uses this role's difficulty, not a fixed upgrade effort.
    (Path(state) / 'policy.json').unlink()
    for difficulty, effort in [(0, 'low'), (1, 'medium'), (3, 'high')]:
        result, call = plan(state, 'bounded_retrieval', difficulty)
        fail(state, result, call)
        repaired = escalate(state, result, call, repair=True)
        assert repaired['reasoning_effort'] == effort
        fail(state, result, repaired)
        raised = escalate(state, result, repaired)
        assert (raised['policy_combo'], raised['reasoning_effort']) == ('Medium', effort)


def check_binding_and_validation(state):
    result, call = plan(state, 'bounded_retrieval', 1)
    policy = adapter.model_policy(state)
    changed = deepcopy(policy)
    changed['combos']['Small']['effort'] = 'High'
    write_policy(state, changed)
    assert adapter.policy_binding(state) != call['policy_binding']
    rejects(lambda: adapter.admit(result['run_id'], call['role_id'], call['prompt'],
                                  result['project'], result['session'], state), 'policy binding')
    write_policy(state, policy)
    assert adapter.policy_binding(state) == call['policy_binding']
    for invalid, fragment in [
        ({**policy, 'secret': 'forbidden'}, 'provider and combos only'),
        ({**policy, 'provider': '../provider'}, 'provider'),
        ({**policy, 'combos': {**policy['combos'], 'Tiny': {'model': 'tiny'}}}, 'Small, Medium and Large'),
    ]:
        rejects(lambda: adapter.validate_policy(invalid), fragment)
    for field, value in [('model', ''), ('model', '../unsafe model'), ('effort', 'XHigh'), ('effort', False)]:
        invalid = deepcopy(policy)
        invalid['combos']['Small'][field] = value
        rejects(lambda: adapter.validate_policy(invalid), field)
    missing_effort = deepcopy(policy)
    del missing_effort['combos']['Small']['effort']
    assert adapter.validate_policy(missing_effort)['combos']['Small']['effort'] == 'Auto'
    write_policy(state, {'provider': 'legacy-provider', 'models': {
        'haiku': 'legacy-small', 'sonnet': 'legacy-medium', 'opus': 'legacy-large'}})
    assert adapter.model_policy(state) == {'provider': 'legacy-provider', 'combos': {
        combo: {'model': model, 'effort': 'Auto'}
        for combo, model in zip(DEFAULT_MODELS, ('legacy-small', 'legacy-medium', 'legacy-large'))}}


def check_serialized_save(state):
    (Path(state) / 'policy.json').unlink(missing_ok=True)
    expected = adapter.policy_binding(state)
    barrier = Barrier(2)
    def save(model):
        value = adapter.model_policy(state)
        value['combos']['Small']['model'] = model
        barrier.wait()
        try:
            adapter.save_policy(value, expected)
            return 'saved'
        except ValueError as error:
            assert 'changed during editing' in str(error)
            return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ['first-small', 'second-small']))
    assert sorted(results) == ['saved', 'stale'], results


def main():
    with tempfile.TemporaryDirectory() as state, isolated_home(state):
        check_auto(state)
        check_explicit_and_retries(state)
        check_binding_and_validation(state)
        check_serialized_save(state)
    print('PASS: all Combo needs, Auto boundaries, explicit effort, retries, policy binding and validation')


if __name__ == '__main__':
    main()
