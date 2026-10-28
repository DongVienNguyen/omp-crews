"""Consumer-visible delegated lifecycle; fixture model receipts, real checker execution."""
import copy,json,sys,tempfile,time
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home,task_answers
from crews import automation as auto, omp_adapter as a, recipes


def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('expected refusal')


def complete(plan,role,folder,status='COMPLETE'):
    ticket=a.dispatch(plan['run_id'],role,folder,plan['session'],folder);cell=ticket['call'];token=ticket['token']
    wire=dict(token=token,role=role,provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort'])
    a.store_receipt(token,folder,wire,folder)
    if cell.get('checker_profile'):a.verify_profile(token,folder,folder,host_key=ticket['host_key'])
    result=dict(status=status,producer_claim=status,verification=['fixture review of original contract and executable checker'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']),wire=wire)
    a.record(plan['run_id'],role,result,folder,plan['session'],folder,host_key=ticket['host_key'])


def run():
    with tempfile.TemporaryDirectory(prefix='crews-automation-') as folder,isolated_home(folder):
        p=Path(folder);signer=Signer();criterion='integer result doubles input including zero and negatives'
        command=sys.executable.replace('\\','/')+' -B verify.py'
        (p/'verify.py').write_text('import json\nfrom target import result\nv=json.load(open("input.json"))["value"]\nassert type(result) is int and result==v*2\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
        features=dict(domain='mapping',language='python',operation='double',invariant=criterion,dependency_shape='single')
        writer=dict(name='writer',kind='produce',mission='Double immutable integer input',deliverable='target.py',scope=['target.py'],inputs=['input.json','target.py'],commands=[],acceptance=[criterion],routine_check='checker',model_revision='fixture-1',facts={**dict.fromkeys(recipes.TRUE_FACTS,True),**dict.fromkeys(recipes.FALSE_FACTS,False)},recipe_features=features,recipe_profile=dict(input='verify.py',command=command),answers=dict(need='everyday_implementation',difficulty=1,divisible=0,specific=1))
        checker=dict(name='checker',kind='check',mission='Independently verify integer mapping',deliverable='verdict',scope=[],inputs=['input.json','target.py','verify.py'],commands=[command],criteria=[criterion],verify_targets=['writer'],checker_profile=dict(input='verify.py',command=command,version='1'),answers=dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1))
        grant=dict(operation='grant',expires=time.time()+3600,max_reviews=8,max_difficulty=1,auto_promotion=auto.AUTO_POLICY,policy_binding=a.policy_binding(folder))
        reject(lambda:auto.dispatch(grant,folder,folder))
        signed=signer.approve(grant,folder,folder)
        gid=auto.dispatch(signed,folder,folder)['grant_id']
        reject(lambda:auto.dispatch(signed,folder,folder))
        def source(value):
            (p/'input.json').write_text(json.dumps({'value':value}));(p/'target.py').write_text('result=-999\n')
            plan=a.build_plan(dict(task='Double integer input',roles=[writer,checker]),task_answers('everyday_implementation',1,True),folder,'source-'+str(value),folder)
            (p/'target.py').write_text('result='+str(value*2)+'\n')
            complete(plan,'writer',folder);complete(plan,'checker',folder)
            return plan
        source(0)
        status=auto.dispatch(dict(operation='status'),folder,folder)
        assert status['enabled'] and len(status['jobs'])==1 and status['jobs'][0]['state']=='queued',status
        ref=auto.next_review(folder,folder)
        assert ref and ref['role']=='approve-automation',ref
        with a.database(folder) as db:plan=a.load_run(db,ref['run'],folder,ref['session'])
        complete(plan,ref['role'],folder)
        assert auto.next_review(folder,folder) is None
        status=recipes.dispatch(dict(operation='status'),folder,folder)
        assert status['recipes'][0]['state']=='candidate' and status['recipes'][0]['train']+status['recipes'][0]['holdout']==1,status
        rid=status['recipes'][0]['recipe_id']
        # Evidence accumulates automatically, but five units never bypass statistical gate.
        for value in (1,-1,2,-2):source(value)
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['train']+row['holdout']==5 and row['state']!='active',row
        assert auto.next_review(folder,folder) is None
        # Duplicate discovery has no second review or training label.
        assert len(auto.dispatch(dict(operation='status'),folder,folder)['jobs'])==1
        for value in range(10,75):source(value)
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['train']+row['holdout']==70 and row['state']!='active',row
        ref=auto.next_review(folder,folder)
        with a.database(folder) as db:plan=a.load_run(db,ref['run'],folder,ref['session'])
        complete(plan,ref['role'],folder)
        assert auto.next_review(folder,folder) is None
        assert recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]['state']=='active'
        writer['recipe_confirmed']=True
        for value in range(100,110):source(value)
        ref=auto.next_review(folder,folder)
        assert ref and ref['role']=='approve-automation',ref
        with a.database(folder) as db:plan=a.load_run(db,ref['run'],folder,ref['session'])
        complete(plan,ref['role'],folder)
        assert auto.next_review(folder,folder) is None
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['audits']==1 and not row['audit_pending'] and row['state']=='active',row
        assert row['train']+row['holdout']==70,'learned or audit execution self-trained'
        # A fresh audit review denied by Large remains blocked, never replayed.
        for value in range(110,120):source(value)
        ref=auto.next_review(folder,folder)
        with a.database(folder) as db:plan=a.load_run(db,ref['run'],folder,ref['session'])
        complete(plan,ref['role'],folder,status='FAILED')
        reject(lambda:a.escalate(ref['run'],ref['role'],'retry denied automatic review',folder,ref['session'],True,folder))
        denied=auto.next_review(folder,folder)
        assert denied and 'blocked' in denied,denied
        assert auto.next_review(folder,folder) is None
        assert recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]['audit_pending']
        source(120)
        ref=auto.next_review(folder,folder)
        ticket=a.dispatch(ref['run'],ref['role'],folder,ref['session'],folder)
        paused=auto.next_review(folder,folder)
        assert 'blocked' in paused and 'admitted' in paused['blocked'],paused
        used=auto.dispatch(dict(operation='status'),folder,folder)['grants'][0]['used']
        assert auto.next_review(folder,folder)==paused
        assert auto.dispatch(dict(operation='status'),folder,folder)['grants'][0]['used']==used
        # Revocation stops effective routing and further automatic training.
        auto.dispatch(signer.approve(dict(operation='revoke',grant_id=gid),folder,folder),folder,folder)
        reject(lambda:a.ticket(ticket['token'],folder,folder))
        reject(lambda:a.dispatch(ref['run'],ref['role'],folder,ref['session'],folder))
        assert not auto.dispatch(dict(operation='status'),folder,folder)['enabled']
        source(7)
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['train']+row['holdout']==70,row
        assert recipes.match(writer,folder,[writer,checker],folder)['reason']=='delegation_inactive'
        # Expired review plans terminate without replay or wedging the queue.
        with a.database(folder) as db:
            db.execute('UPDATE runs SET created=? WHERE id=?',(time.time()-86401,ref['run']))
        assert auto.next_review(folder,folder) is None
        jobs=auto.dispatch(dict(operation='status'),folder,folder)['jobs']
        assert next(j for j in jobs if j['run']==ref['run'])['state']=='blocked'
        # Nonzero checker without JSON stays unknown, but must suspend reuse/promotion.
        (p/'input.json').write_text('{"value":900}');(p/'target.py').write_text('result=-999\n')
        failed=a.build_plan(dict(task='Double integer input',roles=[writer,checker]),task_answers('everyday_implementation',1,True),folder,'unknown-checker',folder)
        complete(failed,'writer',folder);complete(failed,'checker',folder,status='FAILED')
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['state']=='suspended' and row['unknown']>0,row
        source(901)
        row=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert row['state']=='suspended' and row['unknown']>0,row
        narrow={**grant,'expires':time.time()+3600,'max_difficulty':0}
        auto.dispatch(signer.approve(narrow,folder,folder),folder,folder)
        assert recipes.match(writer,folder,[writer,checker],folder)['reason']=='recipe_outside_current_delegation'
        before=len(auto.dispatch(dict(operation='status'),folder,folder)['jobs'])
        prior=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        source(902)
        assert len(auto.dispatch(dict(operation='status'),folder,folder)['jobs'])==before
        current=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        assert (current['train'],current['holdout'],current['state'])==(prior['train'],prior['holdout'],prior['state'])
    print('PASS: signed grant; Large register/promotion/audit; no self-training; denied review sticky; admitted restart never replayed; statistical gate and revocation')


if __name__=='__main__':run()
