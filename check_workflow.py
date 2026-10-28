"""Offline workflow durability, authority, dependency and legacy runner checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from crews import omp_adapter as a, runner, workflow
from check_effort_policy import isolated_home, role, task_answers, rejects

CRITERION = 'Report assigned Combo and effort accurately'


def spec():
    first = role('bounded_retrieval', 1, 'research', 'inspect-policy-source')
    first['inputs'] = ['fixture.txt']
    second = role('bounded_retrieval', 1, 'research', 'inspect-policy-next')
    second['inputs'] = ['fixture.txt']
    check = role('mechanical_verification', 1, 'check', 'verify-policy-contract')
    return dict(task='Inspect Combo model and effort policy', authority=dict(read=['fixture.txt'], write=[], commands=[]), invariants=[CRITERION], max_calls=5, nodes=[dict(id='discovery', stage='discovery', depends_on=[], roles=[first], answers=task_answers('bounded_retrieval', 1)), dict(id='architecture', stage='architecture', depends_on=['discovery'], roles=[second], answers=task_answers('bounded_retrieval', 1)), dict(id='acceptance', stage='acceptance', depends_on=['architecture'], roles=[check], answers=task_answers('mechanical_verification', 1, True))])


def request(value, slot='workflow', operation='workflow_prepare'):
    return dict(operation=operation, slot=slot, session='session', confirmed=True, workflow=value)


def complete(ref, project, state, criteria=False, write=None):
    with a.database(state) as db:
        plan = a.load_run(db, ref['run'], str(project), ref['session'])
    cell = next(c for w in plan['waves'] for c in w['calls'] if c['role_id'] == ref['role'])
    admitted=a.dispatch(ref['run'],ref['role'],str(project),ref['session'],state)
    if write is not None:(project / 'output.txt').write_text(write,encoding='utf-8')
    wire=dict(token=admitted['token'],role=ref['role'],provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort'])
    a.store_receipt(admitted['token'],str(project),wire,state)
    if cell.get('checker_profile'):a.verify_profile(admitted['token'],str(project),state,host_key=admitted['host_key'])
    result = dict(status='COMPLETE', verification=['Isolated contract fixture'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']),wire=wire)
    if criteria:
        result['criterion_results'] = [dict(criterion=CRITERION, status='pass')]
    a.record(ref['run'], ref['role'], result, str(project), ref['session'], state,host_key=admitted['host_key'])
    return cell


def run_checks():
    with tempfile.TemporaryDirectory() as folder, isolated_home(folder):
        project = Path(folder) / 'project'; project.mkdir()
        state = Path(folder) / 'state'
        (project / 'fixture.txt').write_text('immutable input', encoding='utf-8')
        value = spec()
        send = lambda req: runner.dispatch(req, str(project), state)
        prepared = send(request(value))
        assert prepared['profile']=='sdlc_cost_aware'
        assert prepared['next'][0]['role'] == 'inspect-policy-source'
        assert [n['state'] for n in prepared['nodes']] == ['planned', 'pending', 'pending']
        assert send(request(value))['next'] == prepared['next']
        changed = deepcopy(value); changed['max_calls'] = 6
        rejects(lambda: send(request(changed)), 'slot request changed')
        rejects(lambda: send(request(value, 'new-slot')), 'unresolved identity')
        cell = complete(prepared['next'][0], project, state)
        assert cell['workflow_id'] == prepared['workflow_id'] and cell['node_id'] == 'discovery'
        second = send(dict(operation='workflow_next', slot='workflow', session='session', confirmed=True))
        assert second['next'][0]['role'] == 'inspect-policy-next'
        complete(second['next'][0], project, state)
        final = send(dict(operation='workflow_next', slot='workflow', session='session', confirmed=True))
        final_cell = complete(final['next'][0], project, state, True)
        assert 'producer conclusions' not in final_cell['prompt'].lower() or 'not evidence' in final_cell['prompt'].lower()
        assert 'records/' not in final_cell['prompt'].replace('\\', '/')
        assert final_cell['workflow_invariants'] == [CRITERION]
        done = send(dict(operation='workflow_status', slot='workflow', session='session'))
        assert done['complete'] and done['budget']['planned'] == 3
        with a.database(state) as db:
            workflow.reserve_attempt(db, cell, 'repair')
            workflow.reserve_attempt(db, cell, 'repair')
        with a.database(state) as db:
            rejects(lambda: workflow.reserve_attempt(db, cell, 'repair'), 'cap exhausted')
        cycle = spec(); cycle['nodes'][0]['depends_on'] = ['architecture']
        rejects(lambda: send(request(cycle, 'cycle')), 'cycle')
        unknown = spec(); unknown['nodes'][0]['depends_on'] = ['missing']
        rejects(lambda: send(request(unknown, 'unknown')), 'unknown dependency')
        budget = spec(); budget['max_calls'] = 2
        rejects(lambda: send(request(budget, 'budget')), 'actual planned cells')
        overlap = spec()
        overlap['authority']['write'] = ['output.txt']
        overlap['authority']['read'].append('output.txt')
        writer = role('everyday_implementation', 1, 'produce', 'write-policy-artifact'); writer['scope'] = ['output.txt']
        overlap['nodes'][0]['roles'] = [writer]
        overlap['nodes'][1]['depends_on'] = []
        overlap['nodes'][1]['roles'][0]['inputs'].append('output.txt')
        overlap['nodes'][2]['depends_on'] = ['discovery', 'architecture']
        overlap['nodes'][2]['roles'][0]['inputs'].append('output.txt')
        rejects(lambda: send(request(overlap, 'overlap')), 'overlap')
        widened = spec(); widened['nodes'][0]['roles'][0]['inputs'] = ['outside.txt']
        rejects(lambda: send(request(widened, 'widened')), 'original authority')
        no_check = spec(); no_check['nodes'][2]['roles'][0]['criteria'] = ['different criterion']
        rejects(lambda: send(request(no_check, 'no-check')), 'final independent check')
        # Distinct invariant binds separate logical identity, without bypassing unresolved slot.
        crash = spec(); crash['invariants'] = ['Crash reservation never replays']
        crash['nodes'][2]['roles'][0]['criteria'].append(crash['invariants'][0])
        with patch.object(a, 'prepare_plan', side_effect=RuntimeError('crash after reservation')):
            try: send(request(crash, 'crash'))
            except RuntimeError: pass
            else: raise AssertionError('reservation fault not exercised')
        restarted = send(dict(operation='workflow_status', slot='crash', session='session'))
        assert restarted['blocked'].startswith('reserved') and restarted['next'] == []
        assert send(request(crash, 'crash'))['blocked'].startswith('reserved')
        rejects(lambda: send(request(crash, 'crash-new')), 'unresolved identity')
        (project / 'fixture.txt').write_text('changed', encoding='utf-8')
        assert 'source authority changed' in send(dict(operation='workflow_status', slot='workflow', session='session'))['blocked']
        (project / 'fixture.txt').write_text('immutable input', encoding='utf-8')
        branches = spec()
        branches['nodes'][1]['depends_on'] = []
        branches['nodes'][2]['depends_on'] = ['discovery', 'architecture']
        branches['invariants'] = ['Independent branches remain bounded']
        branches['nodes'][2]['roles'][0]['criteria'].append(branches['invariants'][0])
        parallel = send(request(branches, 'branches'))
        assert len(parallel['next']) == 2
        for ref in parallel['next']:
            with a.database(state) as db:
                p = a.load_run(db, ref['run'], str(project), ref['session'])
                c = p['waves'][0]['calls'][0]
                workflow.guard(db, c, a.canonical(str(project)), state)
            a.admit(ref['run'], ref['role'], c['prompt'], str(project), ref['session'], state)
        assert send(dict(operation='workflow_status', slot='branches', session='session'))['next'] == []
        artifacts = spec()
        artifacts['authority']['write'] = ['output.txt']
        artifacts['authority']['read'].append('output.txt')
        for node in artifacts['nodes'][:2]:
            writer = role('everyday_implementation', 1, 'produce', 'write-policy-' + node['id'])
            writer['scope'] = ['output.txt']; writer['inputs'] = ['fixture.txt']
            node['roles'] = [writer]
        artifacts['nodes'][2]['roles'][0]['inputs'].append('output.txt')
        command=__import__('sys').executable.replace('\\','/')+' -B verify.py'
        (project/'verify.py').write_text('import json\nfrom pathlib import Path\nassert Path("output.txt").read_text()=="version two"\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(CRITERION)+',"status":"pass"}]}))\n')
        artifacts['authority']['read'].append('verify.py');artifacts['authority']['commands']=[command]
        artifacts['nodes'][2]['roles'][0].update(inputs=['fixture.txt','output.txt','verify.py'],commands=[command],checker_profile=dict(input='verify.py',command=command,version='1'))
        artifact_state = send(request(artifacts, 'artifacts'))
        complete(artifact_state['next'][0], project, state,write='version one')
        artifact_next = send(dict(operation='workflow_next', slot='artifacts', session='session', confirmed=True))
        complete(artifact_next['next'][0], project, state,write='version two')
        assert send(dict(operation='workflow_next', slot='artifacts', session='session', confirmed=True))['next']
        (project / 'output.txt').write_text('unauthorized change', encoding='utf-8')
        assert 'outside authorized transition' in send(dict(operation='workflow_status', slot='artifacts', session='session'))['blocked']
        legacy_role = role('bounded_retrieval', 1, 'research', 'legacy-policy-reader')
        legacy = dict(operation='prepare', slot='legacy', session='legacy-session', confirmed=True, spec=dict(task=value['task'], roles=[legacy_role]), answers=task_answers('bounded_retrieval', 1))
        legacy_state = send(legacy)
        assert legacy_state['next'] == send(legacy)['next']
        assert send(dict(operation='status', slot='legacy'))['next'] == legacy_state['next']
        with a.database(state) as db:
            db.execute("UPDATE calls SET status='admitted' WHERE run=?", (legacy_state['run'],))
        assert 'admitted' in send(dict(operation='status', slot='legacy'))['blocked']
        with tempfile.TemporaryDirectory() as fresh:
            (Path(fresh)/'fixture.txt').write_text('original',encoding='utf-8')
            baseline=runner.dispatch({**request(spec()),'profile':'baseline'},fresh,Path(fresh)/'state')
            retry=runner.dispatch(request(spec()),fresh,Path(fresh)/'state')
            assert baseline['profile']==retry['profile']=='baseline' and baseline['next']==retry['next']
    print('PASS: workflow dependencies/same-kind ordering, immutable slots, crash/restart no replay, authority/overlap/cycle/unknown rejection, original final checks, host metadata, total retry budget/caps, source freeze and legacy runner compatibility')


if __name__ == '__main__':
    run_checks()
