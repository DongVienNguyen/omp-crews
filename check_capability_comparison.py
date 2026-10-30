"""Freeze/execute/report signed comparisons; synthetic native receipts, host oracle real."""
import copy
import json
import platform
import sys
import tempfile
import subprocess
import time
from itertools import count
from unittest.mock import patch
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home, rejects
from check_cross_node_proof import setup, complete
from crews import omp_adapter as a, outcomes, workflow, workflow_evaluation as ev
from crews.classification import policy_version


def main(benefit=False):
    with tempfile.TemporaryDirectory() as folder,isolated_home(folder),patch('time.time',side_effect=count(time.time(),.01).__next__):
        root=Path(folder);project=root/'project';project.mkdir();state=root/'state';signer=Signer()
        left=project/'baseline';right=project/'candidate';left.mkdir();right.mkdir()
        baseline=setup(left,1.5);candidate=setup(right,1)
        profile=outcomes.profile(baseline['nodes'][1]['roles'][0],str(left),[r for n in baseline['nodes'] for r in n['roles']])
        before=outcomes.fingerprints(str(left),['input.txt','output.txt'])
        unit=dict(id='unit',source_group=outcomes.digest(dict(before_content=sorted(before.values()))),before_hash=outcomes.digest(dict(acceptance=baseline['invariants'],before=before)),acceptance_hash=outcomes.digest(baseline['invariants']),profile_hash=outcomes.digest(profile))
        policy=a.model_policy(state);environment=dict(python=sys.version,platform=platform.platform())
        arms={name:dict(combo=combo,provider=policy['provider'],model=policy['combos'][combo]['model'],effort='medium',policy=policy_version(),revision='fixture-revision',environment=environment) for name,combo in [('baseline','Medium'),('candidate','Small')]}
        for arm in arms.values():
            arm['roles']={'writer':{k:arm[k] for k in ('provider','model','effort','policy','revision')},'checker':dict(provider=policy['provider'],model=policy['combos']['Small']['model'],effort='medium',policy=policy_version(),revision='unversioned')}
        request=dict(version=1,operation='freeze',spec=dict(objective='token-primary',units=[unit],arms=arms),confirmed=True)
        rejects(lambda:ev.capability_dispatch(request,str(project),state),'signed')
        changed_checker=copy.deepcopy(request)
        changed_checker['spec']['arms']['candidate']['roles']['checker']['model']='different-checker'
        rejects(lambda:ev.capability_dispatch(signer.approve(changed_checker,str(project),state),str(project),state),'producer treatment')
        from crews.recipes import evidence_lock
        script='import sys;from crews.recipes import evidence_lock;print("ready",flush=True)\nwith evidence_lock(sys.argv[1]):print("acquired",flush=True)\n'
        with evidence_lock(state):
            child=subprocess.Popen([sys.executable,'-B','-c',script,str(state)],cwd=Path(__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            assert child.stdout.readline().strip()=='ready'
            try:child.wait(timeout=.15)
            except subprocess.TimeoutExpired:pass
            else:raise AssertionError('cross-process evidence lock did not serialize')
        stdout,stderr=child.communicate(timeout=15)
        assert child.returncode==0 and stdout.strip()=='acquired',stderr
        frozen=ev.capability_dispatch(signer.approve(request,str(project),state),str(project),state)
        from crews.recipes import _check_holdout
        rejects(lambda:_check_holdout(str(right),dict(source_group=unit['source_group'],unit_hash='different'),state),'holdout')
        rejects(lambda:_check_holdout(str(right),dict(source_group='renamed',unit_hash='different',execution={'before_hash':unit['before_hash']}),state),'content holdout')
        references={}
        for arm,child,spec in [('baseline',left,baseline),('candidate',right,candidate)]:
            first=workflow.dispatch(dict(operation='prepare',slot=arm,session=arm,workflow=spec,confirmed=True),str(child),state)
            producer=first['next'][0];complete(producer,child,state,True,tokens=100 if benefit and arm=='baseline' else 10)
            second=workflow.dispatch(dict(operation='next',slot=arm,session=arm,confirmed=True),str(child),state)
            checker=second['next'][0];complete(checker,child,state)
            proof=outcomes.verified_pair(producer['run'],'writer',dict(run=checker['run'],role='checker'),str(child),state)
            with a.database(state) as db:
                evidence,_,_=ev._snapshot(db,proof['reference']['workflow'],a.canonical(str(child)),True)
            coverage={key:[] for key in ev.COMPONENTS}
            coverage['producer']=[r[1] for r in evidence['attempts'] if r[2]=='writer']
            coverage['checker']=[r[1] for r in evidence['attempts'] if r[2]=='checker']
            references[arm]={'unit':dict(project=str(child),reference=proof['reference'],coverage=coverage)}
        bad=copy.deepcopy(references);bad['candidate']['unit']['coverage']['checker']=[]
        report=dict(version=1,operation='report',comparison_id=frozen['comparison_id'],arms=bad)
        rejects(lambda:ev.capability_dispatch(report,str(project),state),'coverage')
        report['arms']=references
        result=ev.capability_dispatch(report,str(project),state)
        assert result['authenticated'] and result['qualifies'] is benefit and result['money_status']=='not_evaluated'
        assert result['reason']==('measured_benefit' if benefit else 'no_measured_benefit')
        rejects(lambda:ev.capability_dispatch(report,str(project),state),'already reported')
    print('PASS signed freeze, distinct actual arm bindings, full attempt coverage, equal-pass/no-benefit and replay rejection; synthetic model receipts only')

if __name__=='__main__':
    main(False)
    main(True)
