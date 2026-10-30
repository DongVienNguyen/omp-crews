"""Exercise canonical split-node routing and immutable proof, isolated host fixtures."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from check_effort_policy import isolated_home, task_answers, rejects
from crews import omp_adapter as a, workflow, outcomes, opportunities

CRITERION = 'Output preserves exact integer mapping'

def setup(project, difficulty=1):
    command=sys.executable.replace('\\','/')+' -B verify.py'
    (project/'input.txt').write_text('7')
    (project/'output.txt').write_text('-1')
    (project/'verify.py').write_text('import json\nfrom pathlib import Path\nok=Path("output.txt").read_text()==str(int(Path("input.txt").read_text())*2)\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(CRITERION)+',"status":"pass" if ok else "fail"}]}))\nraise SystemExit(0 if ok else 1)\n')
    facts={**dict.fromkeys(a.BOUNDED_ROUTE['true_facts'],True),**dict.fromkeys(a.BOUNDED_ROUTE['false_facts'],False)}
    writer=dict(name='writer',kind='produce',mission='Map integer',deliverable='output.txt',scope=['output.txt'],inputs=['input.txt','output.txt'],commands=[],acceptance=[CRITERION],routine_check='checker',model_revision='fixture-revision',facts=facts,answers=dict(need='everyday_implementation',difficulty=difficulty,divisible=0,specific=1))
    checker=dict(name='checker',kind='check',mission='Verify integer mapping',deliverable='verdict',scope=[],inputs=['input.txt','output.txt','verify.py'],commands=[command],criteria=[CRITERION],checker_profile=dict(input='verify.py',command=command,version='1'),answers=dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1))
    spec=dict(task='Map integer preserving original acceptance',authority=dict(read=['input.txt','output.txt','verify.py'],write=['output.txt'],commands=[command]),invariants=[CRITERION],max_calls=4,nodes=[dict(id='writer',stage='implementation',depends_on=[],roles=[writer],answers=task_answers('everyday_implementation',difficulty)),dict(id='checker',stage='verification',depends_on=['writer'],roles=[checker],answers=task_answers('mechanical_verification',1,True))])
    return spec

def complete(ref,project,state,write=False,tokens=10,status='COMPLETE'):
    admitted=a.dispatch(ref['run'],ref['role'],str(project),ref['session'],state)
    cell=admitted['call'];token=admitted['token']
    if write:(project/'output.txt').write_text('14')
    receipt=dict(token=token,role=ref['role'],provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort'])
    a.store_receipt(token,str(project),receipt,state)
    if cell.get('checker_profile'):a.verify_profile(token,str(project),state,host_key=admitted['host_key'])
    result=dict(status='COMPLETE',verification=['Isolated host fixture, not provider competence'],criterion_results=[dict(criterion=CRITERION,status='pass')],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort'],usage=dict(input=tokens,output=5),durationMs=10),wire=receipt)
    result['status']=status
    if status!='COMPLETE':result['failure_kind']='provider_error'
    a.record(ref['run'],ref['role'],result,str(project),ref['session'],state,host_key=admitted['host_key'])
    return cell

def execute(project,state,slot='proof',difficulty=1):
    spec=setup(project,difficulty)
    prepared=workflow.dispatch(dict(operation='prepare',slot=slot,session=slot,workflow=spec,confirmed=True),str(project),state)
    producer=prepared['next'][0]
    cell=complete(producer,project,state,True)
    checked=workflow.dispatch(dict(operation='next',slot=slot,session=slot,confirmed=True),str(project),state)
    checker=checked['next'][0];complete(checker,project,state)
    proof=outcomes.verified_pair(producer['run'],'writer',dict(run=checker['run'],role='checker'),str(project),state)
    return spec,cell,proof

def main():
    with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
        root=Path(folder);project=root/'project';project.mkdir();state=root/'state'
        spec,cell,proof=execute(project,state)
        assert cell['policy_combo']=='Small' and proof['verified'] and proof['combo']=='Small'
        assert outcomes.verified_reference(proof['reference'],str(project),state)['verified']
        assert len(opportunities.report(str(project),state)['opportunities'])==1
        stale=copy.deepcopy(proof['reference']);stale['producer']['attempt']+=100
        rejects(lambda:outcomes.verified_reference(stale,str(project),state),'stale')
        (project/'output.txt').write_text('wrong')
        rejects(lambda:outcomes.verified_reference(proof['reference'],str(project),state),'changed')
        failed=root/'failed';failed.mkdir()
        spec=setup(failed)
        prepared=workflow.dispatch(dict(operation='prepare',slot='failed-check',session='failed-check',workflow=spec,confirmed=True),str(failed),state)
        writer=prepared['next'][0];complete(writer,failed,state,True)
        checked=workflow.dispatch(dict(operation='next',slot='failed-check',session='failed-check',confirmed=True),str(failed),state)
        checker=checked['next'][0];complete(checker,failed,state,status='FAILED')
        terminal=outcomes.verified_pair(writer['run'],'writer',dict(run=checker['run'],role='checker'),str(failed),state)
        assert not terminal['verified'] and terminal['reference']['checker']['attempt']
    print('PASS split-node Small routing, authenticated attempt pair, opportunity discovery and stale proof rejection; isolated host fixtures only')

if __name__=='__main__':main()
