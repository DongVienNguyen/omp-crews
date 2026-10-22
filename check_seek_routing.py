"""Offline bounded routing and role-local multi-role Combo checks."""
import tempfile

from crews import omp_adapter as adapter
from check_effort_policy import isolated_home, plan, role, task_answers


def main():
    with tempfile.TemporaryDirectory() as state, isolated_home(state):
        for kind in ('research', 'produce', 'integrate', 'check'):
            for difficulty, effort in [(0, 'low'), (1, 'medium'), (1.001, 'medium'), (3, 'high')]:
                _, call = plan(state, 'bounded_retrieval', difficulty, kind)
                assert (call['policy_combo'], call['model'], call['reasoning_effort']) == ('Small', 'code-seek', effort), call
                assert call['role_answers'] == {'need': 'bounded_retrieval', 'difficulty': difficulty, 'divisible': 0, 'specific': 1}
        roles = [role('bounded_retrieval', 0, name='bounded-reader'),
                 role('everyday_implementation', 1.5, name='daily-reader'),
                 role('difficult_review', 3, name='hard-reader')]
        spec = {'task': 'Inspect three independent Combo policy sources', 'roles': roles}
        # Task-level budget allows fan-out; role answers still own model and effort.
        for task_need, task_difficulty in [('bounded_retrieval', 2), ('difficult_review', 3)]:
            answers = task_answers(task_need, task_difficulty)
            answers['divisible'] = {'noul': 1}
            result = adapter.build_plan(spec, answers, state, 'role-local', state)
            calls = {call['role_id']: call for wave in result['waves'] for call in wave['calls']}
            expected = {'bounded-reader': ('Small', 'code-seek', 'low'),
                        'daily-reader': ('Medium', 'code-sol', 'medium'),
                        'hard-reader': ('Large', 'code-astra', 'high')}
            assert set(calls) == set(expected)
            for source in roles:
                call = calls[source['name']]
                assert (call['policy_combo'], call['model'], call['reasoning_effort']) == expected[source['name']], call
                assert call['role_answers'] == source['answers']
                assert call['dispatch_path'] == 'crew' and call['context'] == 'fresh'
            assert result['task_answers'] == answers
            assert any('Main chat' in warning for warning in result['warnings'])
    print('PASS: bounded needs across kinds/difficulties, audit answers, role-local routing and main-chat boundary')


if __name__ == '__main__':
    main()
