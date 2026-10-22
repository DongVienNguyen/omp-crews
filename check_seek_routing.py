"""Offline routing checks; run with installed runtime Python."""
import tempfile
from pathlib import Path
from check_effort_policy import plan, fail
from crews import omp_adapter as a

with tempfile.TemporaryDirectory() as state:
    for difficulty in (0, 1):
        result, cell = plan(state, 'bounded_retrieval', difficulty)
        assert (cell['model'], cell['reasoning_effort']) == ('code-seek', 'high'), cell
        assert cell['role_answers'] == {'need': 'bounded_retrieval', 'difficulty': difficulty, 'divisible': 0, 'specific': 1}
        assert cell['routing_reason'] == 'bounded_retrieval research difficulty <= 1'
        fail(state, result, cell)
        repair = a.escalate(result['run_id'], cell['role_id'], 'Lookup failed', result['project'], result['session'], True, state)['call']
        assert (repair['model'], repair['reasoning_effort']) == ('code-seek', 'high')
        fail(state, result, repair)
        raised = a.escalate(result['run_id'], cell['role_id'], 'Lookup still failed', result['project'], result['session'], False, state)['call']
        assert (raised['model'], raised['reasoning_effort']) == ('code-sol', 'low')
    for need, difficulty, kind in [
        ('bounded_retrieval', 1.001, 'research'),
        ('bounded_retrieval', 0, 'integrate'),
        ('bounded_retrieval', 0, 'check'),
        ('everyday_implementation', 0, 'produce'),
        ('difficult_review', 0, 'research'),
        ('integration_architecture', 0, 'integrate'),
    ]:
        _, cell = plan(state, need, difficulty, kind)
        assert cell['model'] != 'code-seek', cell
    _, cell = plan(state, 'repeatable_task', 0, 'produce')
    assert (cell['model'], cell['reasoning_effort']) == ('code-seek', 'high')
    _, cell = plan(state, 'mechanical_verification', 0, 'check')
    assert (cell['model'], cell['reasoning_effort']) == ('code-seek', 'high')
print('PASS: bounded Seek routing, excluded roles/needs, audit answers and escalation')
