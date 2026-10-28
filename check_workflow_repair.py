"""Exercise real host profile, cross-node repair, recheck and bounded strikes."""
import json
import sys
import tempfile
from pathlib import Path
from crews import omp_adapter as a, runner
from check_effort_policy import isolated_home, task_answers, rejects

C='Output equals expected integer'

def run():
    with tempfile.TemporaryDirectory() as folder, isolated_home(folder):
        p=Path(folder);(p/'input.txt').write_text('7')
        (p/'verify.py').write_text('import json\nfrom pathlib import Path\nok=Path("output.txt").read_text()=="7"\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(C)+',"status":"pass" if ok else "fail"}]}))\nraise SystemExit(0 if ok else 1)\n')
        command=sys.executable.replace('\\','/')+' -B verify.py'
        writer=dict(name='writer',kind='produce',mission='Write output integer',deliverable='output.txt',scope=['output.txt'],inputs=['input.txt'],commands=[],acceptance=[C],answers=dict(need='everyday_implementation',difficulty=1,divisible=0,specific=1))
        checker=dict(name='checker',kind='check',mission='Check output integer',deliverable='verdict',scope=[],inputs=['output.txt','verify.py'],commands=[command],criteria=[C],checker_profile=dict(input='verify.py',command=command,version='1'),answers=dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1))
        spec=dict(task='Write expected integer',authority=dict(read=['input.txt','output.txt','verify.py'],write=['output.txt'],commands=[command]),invariants=[C],max_calls=9,nodes=[dict(id='build',stage='implementation',depends_on=[],roles=[writer],answers=task_answers('everyday_implementation',1)),dict(id='check',stage='acceptance',depends_on=['build'],roles=[checker],answers=task_answers('mechanical_verification',1,True))])
        from copy import deepcopy
        scaffold=deepcopy(writer);scaffold['name']='scaffold'
        spec['nodes'].insert(0,dict(id='scaffold',stage='scaffold',depends_on=[],roles=[scaffold],answers=task_answers('everyday_implementation',1)))
        spec['nodes'][1]['depends_on']=['scaffold']
        def send(op,**kw):return runner.dispatch(dict(operation='workflow_'+op,slot='repair',session='cycle',confirmed=True,**kw),folder,folder)
        def execute(ref,value=None):
            admitted=a.dispatch(ref['run'],ref['role'],folder,'cycle',folder);cell=admitted['call']
            if value is not None:(p/'output.txt').write_text(value)
            wire=dict(token=admitted['token'],role=ref['role'],provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort']);a.store_receipt(admitted['token'],folder,wire,folder)
            verdict=None
            if cell.get('checker_profile'):verdict=a.verify_profile(admitted['token'],folder,folder,host_key=admitted['host_key'])['receipt']
            ok=verdict is None or verdict['exit_code']==0
            result=dict(status='COMPLETE' if ok else 'FAILED',verification=['Real fixture behavior checked'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']))
            if verdict:result['criterion_results']=verdict['criterion_results']
            a.record(ref['run'],ref['role'],result,folder,'cycle',folder,host_key=admitted['host_key'])
        initial=send('prepare',workflow=spec)['next'][0];execute(initial,'intermediate')
        first=send('next')['next'][0];execute(first,'wrong')
        check=send('next')['next'][0];execute(check)
        assert 'failed' in send('status')['blocked']
        rejects(lambda:a.escalate(initial['run'],'scaffold','Wrong superseded repair',folder,'cycle',True,folder),'recorded failed role')
        a.escalate(first['run'],'writer','Independent integer acceptance failed',folder,'cycle',True,folder)
        assert send('status')['next']==[first]
        execute(first,'still wrong')
        required=send('status')['recheck_required'];assert required==[check]
        send('recheck',node='check');execute(check)
        a.escalate(first['run'],'writer','Same independently failed acceptance',folder,'cycle',True,folder)
        execute(first,'7');send('recheck',node='check');execute(check)
        assert send('status')['complete']
        with a.database(folder) as db:
            rows=db.execute('SELECT role,count(*) FROM execution_attempts GROUP BY role').fetchall()
            assert dict(rows)==dict(scaffold=1,writer=3,checker=3)
        assert send('status')['budget']['repairs']==2
        print('PASS successor-writer ownership, two producer repairs, independent executable rechecks, seven immutable attempts and shared cap preserved')

if __name__=='__main__':run()
