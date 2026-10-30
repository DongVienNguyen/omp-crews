"""Ephemeral signatures and host execution. Fixture prices never prove real rollout."""
import copy
import json
import platform
import sys
import tempfile
import sqlite3
import time
from itertools import count
from unittest.mock import patch
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home, task_answers
from crews import omp_adapter as a, workflow, workflow_evaluation as e
from crews.outcomes import digest, fingerprints

C = 'Output equals seven'


def reject(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('expected refusal')


def run(evaluation_mode='monetary', max_latency_ms=None):
    with tempfile.TemporaryDirectory(prefix='workflow-accounting-') as folder, isolated_home(folder), patch('time.time',side_effect=count(time.time(),.01).__next__):
        root = Path(folder)
        signer = Signer()
        specs, arms = {}, {}
        environment = dict(python=sys.version, platform=platform.platform())
        for arm, profile in (('baseline', 'baseline'), ('candidate', 'sdlc_cost_aware')):
            p = root / arm
            p.mkdir()
            (p / 'input.txt').write_text('7')
            (p / 'output.txt').write_text('initial writable contents')
            (p / 'verify.py').write_text('import json\nfrom pathlib import Path\nok=Path("output.txt").read_text()=="7"\nprint(json.dumps({"criterion_results":[{"criterion":' + repr(C) + ',"status":"pass" if ok else "fail"}]}))\nraise SystemExit(0 if ok else 1)\n')
            command = sys.executable.replace('\\', '/') + ' -B verify.py'
            writer = dict(name='writer', kind='produce', mission='Write integer output', deliverable='output.txt', scope=['output.txt'], inputs=['input.txt'], commands=[], acceptance=[C], answers=dict(need='everyday_implementation', difficulty=1, divisible=0, specific=1))
            successor = copy.deepcopy(writer)
            successor.update(name='successor', mission='Replace intermediate output with final integer', inputs=['input.txt', 'output.txt'])
            checker = dict(name='checker', kind='check', mission='Verify integer output', deliverable='verdict', scope=[], inputs=['input.txt', 'output.txt', 'verify.py'], commands=[command], criteria=[C], checker_profile=dict(input='verify.py', command=command, version='1'), answers=dict(need='mechanical_verification', difficulty=1, divisible=0, specific=1))
            specs[arm] = dict(task=C, authority=dict(read=['input.txt', 'output.txt', 'verify.py'], write=['output.txt'], commands=[command]), invariants=[C], max_calls=4, nodes=[dict(id='build', stage='implementation', depends_on=[], roles=[writer], answers=task_answers('everyday_implementation', 1)), dict(id='replace', stage='implementation', depends_on=['build'], roles=[successor], answers=task_answers('everyday_implementation', 1)), dict(id='check', stage='acceptance', depends_on=['replace'], roles=[checker], answers=task_answers('mechanical_verification', 1, True))])
            scout=dict(name='inspect-integer-source',kind='research',mission='Inspect integer output before implementation',deliverable='source facts',scope=[],inputs=['input.txt','output.txt'],commands=[],acceptance=['Report original integer source'],answers=dict(need='bounded_retrieval',difficulty=1,divisible=0,specific=1))
            specs[arm]['nodes'].insert(0,dict(id='scout',stage='discovery',depends_on=[],roles=[scout],answers=task_answers('bounded_retrieval',1)))
            specs[arm]['nodes'][1]['depends_on']=['scout'];specs[arm]['max_calls']=5
            policy = workflow._policy(str(p), folder)
            arms[arm] = dict(profile=profile, model=policy['model'], policy=policy, environment=environment)
        before = fingerprints(str(root / 'baseline'), specs['baseline']['authority']['read'] + specs['baseline']['authority']['write'])
        unit = dict(id='integer', family='integer', source_group='original-integer', split='holdout', expected_abstain=False, before_hash=digest(dict(acceptance=[C], before=before)), acceptance_hash=digest([C]))
        frozen = dict(units=[unit], arms=arms, noninferiority_margin=0, max_latency_ratio=1.2, min_cost_reduction=.15)
        if evaluation_mode == 'quality_only':
            frozen['evaluation_mode'] = evaluation_mode
            del frozen['min_cost_reduction']
            reject(lambda: e.dispatch(dict(operation='freeze', spec=frozen), folder, folder))
        if max_latency_ms is not None:
            frozen.pop('max_latency_ratio')
            frozen['max_latency_ms']=max_latency_ms
            for limit in (None,True,'400000',0,-1,float('nan'),float('inf')):
                invalid=copy.deepcopy(frozen);invalid['max_latency_ms']=limit
                reject(lambda: e.dispatch(signer.approve(dict(operation='freeze',spec=invalid),folder,folder),folder,folder))
            invalid=copy.deepcopy(frozen);invalid['max_latency_ratio']=1.2
            reject(lambda: e.dispatch(signer.approve(dict(operation='freeze',spec=invalid),folder,folder),folder,folder))
        for key in ('profile', 'model', 'policy', 'environment'):
            bad = copy.deepcopy(frozen)
            bad['arms']['candidate'][key] = 'wrong' if key in ('profile', 'model') else {'wrong': True}
            reject(lambda: e.dispatch(signer.approve(dict(operation='freeze', spec=bad), folder, folder), folder, folder))
        signed_freeze = signer.approve(dict(operation='freeze', spec=frozen), folder, folder)
        eid = e.dispatch(signed_freeze, folder, folder)['evaluation_id']
        refs = []
        for arm in ('baseline', 'candidate'):
            project = str(root / arm)
            def send(op, **kw):
                return workflow.dispatch(dict(operation='workflow_' + op, slot='accounting', session=arm, profile=arms[arm]['profile'], confirmed=True, **kw), project, folder)
            status = send('prepare', workflow=specs[arm])
            # Fixture host clock advances deterministically; no scheduler-dependent sleep.
            while not status.get('complete'):
                assert not status.get('blocked'), status
                for ref in status['next']:
                    admitted = a.dispatch(ref['run'], ref['role'], project, arm, folder)
                    cell = admitted['call']
                    if ref['role'] in ('writer', 'successor'):
                        (root / arm / 'output.txt').write_text('intermediate' if ref['role'] == 'writer' else '7')
                    a.store_receipt(admitted['token'], project, dict(token=admitted['token'], role=ref['role'], provider=cell['provider'], model=cell['model'], effort=cell['reasoning_effort']), folder)
                    result = dict(status='COMPLETE', verification=['Host fixture observed'], native=dict(exitCode=0, resolvedModel=cell['provider'] + '/' + cell['model'] + ':' + cell['reasoning_effort'], resolvedThinkingLevel=cell['reasoning_effort']))
                    if cell.get('checker_profile'):
                        result['criterion_results'] = a.verify_profile(admitted['token'], project, folder, host_key=admitted['host_key'])['receipt']['criterion_results']
                    a.record(ref['run'], ref['role'], result, project, arm, folder, host_key=admitted['host_key'])
                status = send('next')
            evidence = e.dispatch(dict(operation='evidence', workflow_id=status['workflow_id']), project, folder)
            if evaluation_mode == 'monetary':
                metrics = dict(components={k: (2 if arm == 'baseline' else 1) for k in e.COMPONENTS}, latency_ms=10, pricing_reference='ephemeral signed fixture only; not real provider pricing or real rollout evidence', coverage={k: True for k in ('all_attempts', 'main', 'governance', 'context')})
                signed = signer.approve(dict(operation='attest', workflow_id=status['workflow_id'], evidence_hash=evidence['evidence_hash'], metrics=metrics), project, folder)
                e.dispatch(signed, project, folder)
            refs.append(dict(unit=unit['id'], arm=arm, workflow_id=status['workflow_id'], project=project))
        request = dict(operation='report', evaluation_id=eid, results=refs)
        report = e.dispatch(request, folder, folder)
        assert report['rollout'] == 'GO', report
        assert report['accounting_complete'] is (evaluation_mode == 'monetary'), report
        if evaluation_mode == 'quality_only':
            assert report['evaluation_mode'] == 'quality_only' and report['money_status'] == 'not_evaluated'
            assert report['cost_gate'] is None and not report['missing'] and not report['violations']
            if max_latency_ms is not None:assert report['latency_criterion']==dict(kind='absolute',max_latency_ms=max_latency_ms)
            for arm in ('baseline', 'candidate'):
                assert report[arm]['total_cost'] is None and report[arm]['cost_per_accepted'] is None
                assert report[arm]['latency_complete'] and not report[arm]['accounting_complete']
            with a.database(folder) as db:
                assert db.execute('SELECT count(*) FROM workflow_accounting').fetchone()[0] == 0
                for ref in refs:
                    created = db.execute('SELECT created FROM workflows WHERE id=?', (ref['workflow_id'],)).fetchone()[0]
                    end = db.execute('SELECT max(created) FROM execution_attempts WHERE workflow=?', (ref['workflow_id'],)).fetchone()[0]
                    assert report[ref['arm']]['p95'] == (end - created) * 1000
                try:
                    db.execute('UPDATE execution_attempts SET created=0')
                except sqlite3.IntegrityError as exc:
                    assert 'attempt history immutable' in str(exc)
                else:
                    raise AssertionError('timestamp history mutable')
                raw = db.execute('SELECT spec FROM workflow_evaluations WHERE id=?', (eid,)).fetchone()[0]
                changed = json.loads(raw)
                changed['evaluation_mode'] = 'monetary'
                db.execute('UPDATE workflow_evaluations SET spec=? WHERE id=?', (json.dumps(changed), eid))
            reject(lambda: e.dispatch(request, folder, folder))
            with a.database(folder) as db:
                db.execute('UPDATE workflow_evaluations SET spec=? WHERE id=?', (raw, eid))
            replay = copy.deepcopy(refs)
            replay[1]['workflow_id'] = replay[0]['workflow_id']
            reject(lambda: e.dispatch(dict(request, results=replay), folder, folder))
            with a.database(folder) as db:
                run, role, raw = db.execute('SELECT c.run,c.role,c.result FROM calls c JOIN runs r ON r.id=c.run WHERE r.project=? LIMIT 1', (a.canonical(refs[1]['project']),)).fetchone()
                unauthenticated = json.loads(raw)
                unauthenticated['host_authenticated'] = False
                db.execute('UPDATE calls SET result=? WHERE run=? AND role=?', (json.dumps(unauthenticated), run, role))
            refused = e.dispatch(request, folder, folder)
            assert refused['rollout'] == 'NO_GO' and refused['missing'], refused
            with a.database(folder) as db:
                db.execute('UPDATE calls SET result=? WHERE run=? AND role=?', (raw, run, role))
        assert report['baseline']['accepted'] == report['candidate']['accepted'] == 1
        assert all(r['attempts'] == 4 for r in report['receipts'])
        # Re-signing wrong frozen controls still cannot authorize mismatched executions.
        for key in ('before', 'profile', 'model', 'policy', 'environment'):
            bad = copy.deepcopy(frozen)
            if key == 'before':
                bad['units'][0]['before_hash'] = digest(dict(acceptance=[C], before=workflow._sources(str(root / 'baseline'), specs['baseline'])))
            elif key == 'profile':
                # Invalid arm profile is rejected at authenticated freeze.
                bad['arms']['candidate']['profile'] = 'baseline'
                reject(lambda: e.dispatch(signer.approve(dict(operation='freeze', spec=bad), folder, folder), folder, folder))
                continue
            else:
                for binding in bad['arms'].values():
                    if key == 'model':
                        binding['model'] = binding['policy']['model'] = 'wrong-model-binding'
                    else:
                        binding[key]['fixture_changed'] = True
            wrong_id = digest(dict(project=a.canonical(folder), spec=bad))
            wrong_signed = signer.approve(dict(operation='freeze', spec=bad), folder, folder)
            # Persist signed alternative using same pre-execution freeze time, not a later corpus.
            with a.database(folder) as db:
                created = db.execute('SELECT created FROM workflow_evaluations WHERE id=?', (eid,)).fetchone()[0]
                db.execute('INSERT INTO workflow_evaluations VALUES(?,?,?,?,?)', (wrong_id, a.canonical(folder), json.dumps(bad), created, json.dumps(wrong_signed)))
            refused = e.dispatch(dict(request, evaluation_id=wrong_id), folder, folder)
            assert refused['rollout'] == 'NO_GO' and refused['violations'], (key, refused)
        # Initial writable fingerprints match both arms, but cannot be omitted.
        assert before['output.txt'] is not None
        (root / 'candidate' / 'output.txt').write_text('bad')
        stale = e.dispatch(request, folder, folder)
        assert stale['rollout'] == 'NO_GO' and stale['violations'], stale
        print('PASS ' + evaluation_mode + ': signed SDLC freeze, paired profiles, immutable host attempts, independent host verifier, model/policy/before/environment mismatch refusal, stale artifacts blocked; fixtures only, no real rollout or savings claim')


if __name__ == '__main__':
    run()
