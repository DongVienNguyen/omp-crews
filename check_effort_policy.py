"""Run with runtime-venv/Scripts/python.exe check_effort_policy.py (no network)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from crews import omp_adapter as a


def plan(state, need, difficulty, kind='research'):
    role = {'name': 'effort-policy-checker', 'kind': kind,
            'mission': 'Inspect configuration effort policy and verify assigned effort',
            'deliverable': 'effort.json', 'scope': [],
            'acceptance': ['Assigned effort matches the global policy'],
            'criteria': ['Assigned effort matches the global policy'],
            'inputs': ['fixture.txt'] if kind == 'check' else [],
            'answers': {'need': need, 'difficulty': difficulty, 'divisible': 0, 'specific': 1}}
    if kind in ('produce', 'integrate'):
        role['scope'] = ['fixture.txt']
    answers = {'need': {'choice': need, 'confidence': 1, 'probabilities': {need: 1}},
               'difficulty': {'score': difficulty}, 'divisible': {'noul': 0},
               'needs_verifier': {'noul': 1 if kind == 'check' else 0}}
    result = a.build_plan({'task': 'Inspect configuration effort policy', 'roles': [role]},
                          answers, str(Path(state).resolve()), 'effort-check', state)
    return result, result['waves'][0]['calls'][0]


def fail(state, result, cell):
    a.admit(result['run_id'], cell['role_id'], cell['prompt'], result['project'], result['session'], state)
    a.record(result['run_id'], cell['role_id'], {'status': 'FAILED', 'verification': ['Check failed']},
             result['project'], result['session'], state)


with tempfile.TemporaryDirectory() as state:
    for need, difficulty, kind, model, effort in [
        ('mechanical_verification', 0, 'research', 'code-seek', 'high'),
        ('mechanical_verification', 3, 'check', 'code-seek', 'high'),
        ('repeatable_task', 0, 'produce', 'code-seek', 'high'),
        ('repeatable_task', 2.49, 'research', 'code-seek', 'high'),
        ('repeatable_task', 2.5, 'research', 'code-sol', 'low'),
        ('repeatable_task', 0, 'check', 'code-sol', 'low'),
        ('everyday_implementation', 0, 'produce', 'code-sol', 'low'),
        ('everyday_implementation', 2.5, 'research', 'code-sol', 'medium'),
        ('long_running_agentic', 0, 'integrate', 'code-sol', 'high'),
        ('long_running_agentic', 3, 'integrate', 'code-sol', 'xhigh'),
        ('difficult_review', 0, 'research', 'code-astra', 'low'),
        ('difficult_review', 0.999, 'check', 'code-astra', 'low'),
        ('difficult_review', 1, 'research', 'code-astra', 'medium'),
        ('difficult_review', 1.999, 'research', 'code-astra', 'medium'),
        ('difficult_review', 2, 'research', 'code-astra', 'high'),
        ('integration_architecture', 3, 'research', 'code-astra', 'high'),
    ]:
        _, cell = plan(state, need, difficulty, kind)
        assert (cell['model'], cell['reasoning_effort']) == (model, effort), cell
        assert cell['agent_type'] == 'crew-' + kind + '-' + model.removeprefix('code-')

    for need, difficulty, kind, expected in [
        ('repeatable_task', 0, 'research', ('code-sol', 'low')),
        ('everyday_implementation', 0, 'research', ('code-sol', 'medium')),
        ('everyday_implementation', 3, 'research', ('code-sol', 'high')),
        ('long_running_agentic', 0, 'integrate', ('code-sol', 'xhigh')),
        ('long_running_agentic', 3, 'integrate', ('code-astra', 'low')),
        ('difficult_review', 0, 'research', ('code-astra', 'medium')),
        ('difficult_review', 1, 'research', ('code-astra', 'high')),
    ]:
        result, cell = plan(state, need, difficulty, kind)
        original = (cell['model'], cell['reasoning_effort'])
        fail(state, result, cell)
        repaired = a.escalate(result['run_id'], cell['role_id'], 'Concrete check failed', result['project'], result['session'], True, state)['call']
        assert (repaired['model'], repaired['reasoning_effort']) == original
        fail(state, result, repaired)
        raised = a.escalate(result['run_id'], cell['role_id'], 'Still failed', result['project'], result['session'], False, state)['call']
        assert (raised['model'], raised['reasoning_effort']) == expected, raised

    result, cell = plan(state, 'difficult_review', 3)
    fail(state, result, cell)
    try:
        a.escalate(result['run_id'], cell['role_id'], 'Top seat failed', result['project'], result['session'], False, state)
    except ValueError:
        pass
    else:
        raise AssertionError('Astra/high must refuse escalation')

    result, cell = plan(state, 'mechanical_verification', 0)
    with a.database(state) as db:
        stored = json.loads(db.execute('SELECT plan FROM runs WHERE id=?', (result['run_id'],)).fetchone()[0])
        stored['waves'][0]['calls'][0]['model'] = 'gpt-6-luna'
        db.execute('UPDATE runs SET plan=? WHERE id=?', (json.dumps(stored), result['run_id']))
    try:
        a.admit(result['run_id'], cell['role_id'], cell['prompt'], result['project'], result['session'], state)
    except ValueError as exc:
        assert 'Unsupported OMP model' in str(exc), exc
    else:
        raise AssertionError('Legacy Luna plan must be refused before dispatch')

    result, cell = plan(state, 'repeatable_task', 0)
    cell['prompt'] += '\nKiểm tra chính sách mới'
    with a.database(state) as db:
        stored = json.loads(db.execute('SELECT plan FROM runs WHERE id=?', (result['run_id'],)).fetchone()[0])
        stored['waves'][0]['calls'][0]['prompt'] = cell['prompt']
        db.execute('UPDATE runs SET plan=? WHERE id=?', (json.dumps(stored), result['run_id']))
        db.execute('UPDATE calls SET digest=? WHERE run=?', (hashlib.sha256(cell['prompt'].encode()).hexdigest(), result['run_id']))
    request = {'op': 'dispatch', 'run': result['run_id'], 'role': cell['role_id'], 'project': result['project'], 'session': result['session']}
    process = subprocess.run([sys.executable, str(Path(__file__).with_name('omp_bridge.py'))],
                             input=json.dumps(request, ensure_ascii=False).encode('utf-8'), capture_output=True,
                             env={**os.environ, 'CREWS_OMP_HOME': state, 'PYTHONIOENCODING': 'cp1252'}, timeout=30)
    assert process.returncode == 0, process.stdout
    assert 'Kiểm tra chính sách mới' in json.loads(process.stdout)['call']['prompt']
print('PASS: global remap, difficulty boundaries, repair, escalation, legacy rejection and UTF-8 bridge')
