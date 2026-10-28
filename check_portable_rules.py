"""External AI packets remain proposals until authenticated Large approval."""
import copy,json,tempfile
from pathlib import Path
from check_effort_policy import isolated_home
from check_keyless import review,rejects
from crews import automation as a,governance


def run():
    with tempfile.TemporaryDirectory(prefix='crews-rules-') as folder,isolated_home(folder):
        a.install(folder);a.ensure(folder,folder)
        ref=a.next_review(folder,folder)
        policy=copy.deepcopy(governance.DEFAULTS)
        review(ref,folder,dict(decision='approve',policy=policy,reason='fixture initial policy'))
        assert a.next_review(folder,folder) is None
        packet=a.dispatch(dict(operation='export'),folder,folder)
        assert packet['format']=='crews-rule' and packet['version']==1
        changed=copy.deepcopy(packet);changed['proposal']['audit_every']=2
        request=dict(operation='import',confirmed=True,packet='```json\n'+json.dumps(changed)+'\n```')
        queued=a.dispatch(request,folder,folder)
        assert queued['applied'] is False and a.audit_interval(folder,folder)==10
        assert a.dispatch(request,folder,folder)['job_id']==queued['job_id']
        ref=a.next_review(folder,folder)
        review(ref,folder,dict(decision='approve',policy=changed['proposal'],reason='fixture external optimization accepted'))
        assert a.next_review(folder,folder) is None
        assert a.audit_interval(folder,folder)==2
        rejects(lambda:a.dispatch(request,folder,folder))
        fresh=a.dispatch(dict(operation='export'),folder,folder)
        bad=copy.deepcopy(fresh);bad['version']=2
        rejects(lambda:a.dispatch(dict(operation='import',confirmed=True,packet=bad),folder,folder))
        for version in (True,1.0):
            bad=copy.deepcopy(fresh);bad['version']=version
            rejects(lambda:a.dispatch(dict(operation='import',confirmed=True,packet=bad),folder,folder))
        bad=copy.deepcopy(fresh);bad['proposal']['write_scope']=['*']
        rejects(lambda:a.dispatch(dict(operation='import',confirmed=True,packet=bad),folder,folder))
        with tempfile.TemporaryDirectory(prefix='crews-rules-other-') as other:
            rejects(lambda:a.dispatch(dict(operation='import',confirmed=True,packet=fresh),other,folder))
        from crews.portable_rules import parse
        rejects(lambda:parse('{"version":1,"version":2}'))
        rejects(lambda:parse('Here is JSON '+json.dumps(fresh)))
        rejects(lambda:parse('{"value":NaN}'))
        from crews import recipes,omp_adapter as adapter,outcomes
        from check_effort_policy import task_answers
        from check_automation import complete
        import sys
        criterion='integer mapping doubles exact input'
        command=sys.executable.replace('\\','/')+' -B verify.py'
        Path(folder,'input.json').write_text('{"value":3}')
        Path(folder,'target.py').write_text('result=0\n')
        Path(folder,'verify.py').write_text('import json\nfrom target import result\nassert result==6\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
        features=dict(domain='mapping',language='python',operation='double',invariant=criterion,dependency_shape='single')
        writer=dict(name='writer',kind='produce',mission='Double integer mapping input',deliverable='target.py',scope=['target.py'],inputs=['input.json','target.py'],commands=[],acceptance=[criterion],routine_check='checker',model_revision='fixture-1',recipe_features=features,recipe_profile=dict(input='verify.py',command=command),facts={**dict.fromkeys(recipes.TRUE_FACTS,True),**dict.fromkeys(recipes.FALSE_FACTS,False)},answers=dict(need='everyday_implementation',difficulty=1,divisible=0,specific=1))
        checker=dict(name='checker',kind='check',mission='Verify integer mapping input',deliverable='verdict',scope=[],inputs=['input.json','target.py','verify.py'],commands=[command],criteria=[criterion],verify_targets=['writer'],checker_profile=dict(input='verify.py',command=command,version='1'),answers=dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1))
        plan=adapter.build_plan(dict(task='Double integer mapping input',roles=[writer,checker]),task_answers('everyday_implementation',1,True),folder,'portable-source',folder)
        Path(folder,'target.py').write_text('result=6\n')
        complete(plan,'writer',folder);complete(plan,'checker',folder)
        ref=a.next_review(folder,folder);assert ref
        review(ref,folder)
        assert a.next_review(folder,folder) is None
        old=recipes.dispatch(dict(operation='status'),folder,folder)['recipes'][0]
        packet=a.dispatch(dict(operation='export',kind='recipe',recipe_id=old['recipe_id']),folder,folder)
        packet['proposal']['lesson']='Preserve integer mapping invariant; independently verify zero and negatives.'
        queued=a.dispatch(dict(operation='import',confirmed=True,packet=packet),folder,folder)
        assert queued['state']=='queued'
        ref=a.next_review(folder,folder);review(ref,folder)
        assert a.next_review(folder,folder) is None
        versions=recipes.dispatch(dict(operation='status'),folder,folder)['recipes']
        assert len(versions)==2 and versions[0]['state']=='suspended' and versions[1]['state']=='candidate',versions
        assert versions[1]['train']==versions[1]['holdout']==0,'new guidance inherited activation evidence'
        assert a.dispatch(dict(operation='export',kind='recipe',recipe_id=versions[1]['recipe_id']),folder,folder)['proposal']['lesson']==packet['proposal']['lesson']
    print('PASS: policy and recipe portable roundtrip, independent review, new recipe candidate without inherited evidence; stale/foreign/context/authority refusal')


if __name__=='__main__':run()
