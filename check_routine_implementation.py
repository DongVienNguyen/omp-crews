"""Behavioral routing/admission checks; isolated state, no provider calls."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from crews import omp_adapter as a
from check_effort_policy import isolated_home, task_answers, fail, escalate
from omp_server import RoleSpec


def run():
    with TemporaryDirectory() as folder, isolated_home(folder):
        root = Path(folder)
        (root / 'verify.py').write_text('from out import value\nassert value == 1\n', encoding='utf-8')
        acceptance = ['Return the specified value for normal and boundary inputs']
        role = {'name': 'routine-edit', 'kind': 'produce', 'mission': 'Implement fixed local behavior',
                'deliverable': 'out.py', 'scope': ['out.py'], 'acceptance': acceptance,
                'routine_check': 'independent-check',
                'answers': {'need': 'everyday_implementation', 'difficulty': 1, 'divisible': 0, 'specific': 1},
                'facts': {**dict.fromkeys(a.BOUNDED_ROUTE['true_facts'][:-1], True),
                          **dict.fromkeys(a.BOUNDED_ROUTE['false_facts'], False)}}
        checker = {'name': 'independent-check', 'kind': 'check', 'mission': 'Verify original behavior independently',
                   'deliverable': 'verdict', 'scope': [], 'inputs': ['out.py', 'verify.py'],
                   'commands': ['python verify.py'], 'criteria': acceptance,
                   'answers': {'need': 'mechanical_verification', 'difficulty': 1, 'divisible': 0, 'specific': 1}}
        def preview(value, check=checker):
            return a.preview(value, str(root), [value, check])
        assert preview(role)['small_route'] == 'routine'
        assert preview(role)['policy_combo'] == 'Small'
        assert a.preview(role, str(root))['policy_combo'] == 'Medium'
        for difficulty, combo, effort in [(0.5, 'Small', 'low'), (1, 'Small', 'medium'), (1.001, 'Medium', 'medium')]:
            value = deepcopy(role); value['answers']['difficulty'] = difficulty
            result = preview(value)
            assert (result['policy_combo'], result['reasoning_effort']) == (combo, effort)
        for key in role['facts']:
            value = deepcopy(role); del value['facts'][key]
            assert preview(value)['policy_combo'] == 'Medium', key
            value['facts'][key] = None
            assert preview(value)['policy_combo'] == 'Medium', key
        for key in ('cross_system', 'concurrency_sensitive'):
            value = deepcopy(role); value['facts'][key] = True
            assert preview(value)['policy_combo'] == 'Medium'
        for scope in [[], ['a', 'b', 'c', 'd'], ['*.py'], ['../out.py'], ['C:/out.py']]:
            value = deepcopy(role); value['scope'] = scope
            assert not a.small_eligibility(value, str(root), [value, checker], True)['eligible']
        for change in [{'kind': 'research'}, {'scope': ['verify.py']}, {'inputs': []}, {'criteria': []}, {'commands': ['python out.py']}]:
            other = {**checker, **change}
            # The writable target must exist to exercise command dependency checks.
            (root / 'out.py').write_text('value = 1\n', encoding='utf-8')
            assert preview(role, other)['policy_combo'] == 'Medium', change
        for command in ['python -c"exec(open(\'out.py\').read())"', 'python -m out', 'node --eval="require(\'./out.py\')"', 'python verify.py && python out.py']:
            assert preview(role, {**checker, 'commands': [command]})['policy_combo'] == 'Medium', command
        sibling = {**role, 'name': 'other-writer', 'scope': ['verify.py']}
        assert not a.small_eligibility(role, str(root), [role, checker, sibling], True)['eligible']
        data_role = {**role, 'scope': ['out.json']}
        data_check = {**checker, 'inputs': ['out.json','verify.py'], 'commands': ['python verify.py out.json']}
        assert a.small_eligibility(data_role, str(root), [data_role,data_check], True)['eligible']
        source_data_check = {**checker, 'commands': ['python verify.py out.py']}
        assert preview(role, source_data_check)['policy_combo'] == 'Small'
        assert preview(role, {**checker, 'commands': ['python']})['policy_combo'] == 'Medium'
        extensionless = {**role, 'scope': ['out']}
        (root / 'checks').mkdir()
        (root / 'checks' / 'verify.py').write_text('raise AssertionError("not executed by routing test")\n')
        escaped_role = {**role, 'scope': ['checksverify.py']}
        escaped_check = {**checker, 'inputs': ['checksverify.py','checks/verify.py'], 'commands': ['python checks\\verify.py']}
        assert not a.small_eligibility(escaped_role, str(root), [escaped_role,escaped_check], True)['eligible']
        for option in ('-cpass','-mout'):
            (root / option).write_text('raise AssertionError("decoy checker")\n')
            decoy_check = {**checker, 'inputs': ['out.py',option], 'commands': ['python '+option]}
            assert preview(role,decoy_check)['policy_combo']=='Medium'
        newline_check = {**checker, 'inputs': ['out','verify.py'], 'commands': ['python verify.py\npython out']}
        assert not a.small_eligibility(extensionless, str(root), [extensionless,newline_check], True)['eligible']
        for invalid in [4, [], 'bad name']:
            try:
                RoleSpec.model_validate({**role, 'routine_check': invalid})
            except ValueError:
                pass
            else:
                raise AssertionError('invalid routine_check accepted')
        plan = a.build_plan({'task': 'Fixed routine behavior', 'roles': [role, checker]},
                            task_answers('everyday_implementation', 1, True), str(root), 'routine', folder)
        cells = [cell for wave in plan['waves'] for cell in wave['calls']]
        call = next(cell for cell in cells if cell['role_id'] == role['name'])
        assert (call['requested_combo'], call['effective_combo'], call['small_route'], call['bounded_small']) == ('Medium', 'Small', 'routine', False)
        a.validate_model(call, folder)
        stale = {**call, 'routing_policy_version': 'stale'}
        try:
            a.validate_model(stale, folder)
        except ValueError as error:
            assert 'fresh plan' in str(error)
        else:
            raise AssertionError('stale route admitted')
        fail(folder, plan, call)
        repaired = escalate(folder, plan, call, True)
        assert repaired['effective_combo'] == 'Small'
        fail(folder, plan, repaired)
        raised = escalate(folder, plan, repaired)
        assert raised['effective_combo'] == 'Medium' and raised['small_route'] == 'routine'
        a.admit(plan['run_id'], raised['role_id'], raised['prompt'], plan['project'], plan['session'], folder)
        a.record(plan['run_id'], raised['role_id'], {'status': 'COMPLETE', 'verification': ['producer conclusion must remain private']}, plan['project'], plan['session'], folder)
        checked = next(cell for cell in cells if cell['role_id'] == checker['name'])
        assert plan['records'][role['name']] not in checked['prompt']
        a.admit(plan['run_id'], checked['role_id'], checked['prompt'], plan['project'], plan['session'], folder)
        assert not Path(plan['records'][role['name']]).exists(), 'checker handoff materialized producer conclusions'
        missing = deepcopy(role); missing['routine_check'] = 'absent'
        try:
            a.build_plan({'task': 'Invalid check', 'roles': [missing, checker]}, task_answers('everyday_implementation', 1), str(root), 'invalid', folder)
        except ValueError as error:
            assert 'routine_check' in str(error)
        else:
            raise AssertionError('missing checker admitted')
    print('PASS: routine eligibility, missing facts, scope, independent acceptance, stale binding, repair and escalation')


if __name__ == '__main__':
    run()
