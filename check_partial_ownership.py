"""Partial output succession retains original writer and permits repair before successor replay."""
import tempfile,json
from pathlib import Path
from copy import deepcopy
from crews import omp_adapter as a,workflow
from check_effort_policy import isolated_home,role,task_answers
from check_workflow import complete


def run():
    with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
        p=Path(folder);(p/'fixture.txt').write_text('fixed')
        first=role('everyday_implementation',1,'produce','first');first.update(scope=['output.txt','other.txt'],inputs=['fixture.txt'])
        second=deepcopy(first);second.update(name='second',scope=['output.txt'])
        check=role('mechanical_verification',1,'check','check');check['inputs']=['output.txt','other.txt','verify.py']
        import sys
        command=sys.executable.replace('\\','/')+' -B verify.py'
        check['name']='verify-policy-output'
        criterion=first['acceptance'][0]
        (p/'verify.py').write_text('import json\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"fail"}]}))\nraise SystemExit(1)\n')
        check.update(commands=[command],checker_profile=dict(input='verify.py',command=command,version='1'))
        spec=dict(task='Inspect Combo policy',authority=dict(read=['fixture.txt','output.txt','other.txt','verify.py'],write=['output.txt','other.txt'],commands=[command]),invariants=[criterion],max_calls=9,nodes=[dict(id='first',stage='implementation',depends_on=[],roles=[first],answers=task_answers('everyday_implementation',1)),dict(id='second',stage='implementation',depends_on=['first'],roles=[second],answers=task_answers('everyday_implementation',1)),dict(id='check',stage='acceptance',depends_on=['second'],roles=[check],answers=task_answers('mechanical_verification',1,True))])
        def send(op,**kw):return workflow.dispatch(dict(operation='workflow_'+op,slot='partial',session='session',confirmed=True,**kw),folder,folder)
        one=send('prepare',workflow=spec)['next'][0];(p/'other.txt').write_text('old');complete(one,p,folder,write='first')
        two=send('next')['next'][0];complete(two,p,folder,write='second')
        final=send('next')['next'][0]
        with a.database(folder) as db:
            plan=a.load_run(db,final['run'],folder,'session');cell=plan['waves'][0]['calls'][0]
            assert {x['role'] for x in cell['workflow_targets']}=={'first','second'}
            manifest=workflow._manifest(db,send('status')['workflow_id'])
            assert not workflow._superseded(db,manifest,'first',['output.txt','other.txt'])
            assert workflow._superseded(db,manifest,'first',['output.txt'])
        complete(final,p,folder,criteria=True)
        a.escalate(one['run'],'first','Repair remaining owned other.txt',folder,'session',True,folder)
        complete(one,p,folder,write='repaired intermediate')
        a.escalate(two['run'],'second','Rebuild invalidated successor',folder,'session',True,folder)
        complete(two,p,folder,write='final')
        assert send('status')['recheck_required']
        print('PASS partial successor ownership, retained checker targets, ancestor repair followed by explicit successor rebuild without stale intermediate deadlock; lineage fixture only')

if __name__=='__main__':run()
