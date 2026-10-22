"""Offline bounded implementation routing and escalation acceptance."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from crews import omp_adapter as a
from crews.classification import ClassificationFacts, classify_role
from check_effort_policy import isolated_home, task_answers, fail, escalate
from omp_server import BoundedCheck, crew_catalog


def run():
    with TemporaryDirectory() as folder, isolated_home(folder):
        project=Path(folder);(project/'check.py').write_text('assert True\n',encoding='utf-8')
        role={'name':'bounded-edit','kind':'produce','mission':'Implement fixed behavior','deliverable':'out.py',
              'scope':['out.py'],'inputs':['check.py'],'commands':['python check.py'],
              'bounded_check':{'input':'check.py','command':'python check.py'},
              'acceptance':['Exact expected behavior passes independent checker'],
              'answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1},
              'facts':{**dict.fromkeys(a.BOUNDED_ROUTE['true_facts'],True),**dict.fromkeys(a.BOUNDED_ROUTE['false_facts'],False)}}
        def preview(value):return a.preview(value,str(project))
        assert preview(role)['policy_combo']=='Small'
        assert a.preview(role)['policy_combo']=='Medium'
        for difficulty,combo,effort in [(0.5,'Small','low'),(1.5,'Small','medium'),(1.501,'Medium','medium')]:
            candidate=deepcopy(role);candidate['answers']['difficulty']=difficulty
            seat=preview(candidate);assert (seat['policy_combo'],seat['reasoning_effort'])==(combo,effort),seat
            assert seat['answers']['need']=='everyday_implementation'
        for key in a.BOUNDED_ROUTE['true_facts']+a.BOUNDED_ROUTE['false_facts']:
            candidate=deepcopy(role);del candidate['facts'][key]
            assert preview(candidate)['policy_combo']=='Medium',key
        for key in ('cross_system','concurrency_sensitive'):
            candidate=deepcopy(role);candidate['facts'][key]=True
            assert preview(candidate)['policy_combo']=='Medium'
        for scope in [[],['*.py'],['dir/'],['../out.py'],['/out.py'],['C:\\out.py'],['a','b','c','d'],['check.py']]:
            candidate=deepcopy(role);candidate['scope']=scope
            assert not a.bounded_small(candidate,str(project)),scope
        (project/'dir').mkdir();candidate=deepcopy(role);candidate['scope']=['dir']
        assert not a.bounded_small(candidate,str(project))
        for field,value in [('input','missing.py'),('command','python other.py')]:
            candidate=deepcopy(role);candidate['bounded_check'][field]=value
            assert preview(candidate)['policy_combo']=='Medium'
        sibling={**role,'name':'sibling','scope':['check.py']}
        assert not a.bounded_small(role,str(project),[role,sibling])
        sibling['scope']=['.'];assert not a.bounded_small(role,str(project),[role,sibling])
        candidate=deepcopy(role);candidate['answers']={'divisible':0,'specific':1};candidate['classification']=True
        classified=classify_role(candidate,str(project))
        assert classified['answers']['need']=='everyday_implementation' and classified['answers']['difficulty']==1
        assert classified['policy_combo']=='Small' and classified['outcome']=='deterministic'
        candidate['answers'].update(need='everyday_implementation',difficulty=1.501)
        assert classify_role(candidate,str(project))['policy_combo']=='Medium'
        for model,value in [(ClassificationFacts,{'behavior_fixed':1}),(BoundedCheck,{'input':'check.py','command':'python check.py','other':True})]:
            try:model.model_validate(value)
            except ValueError:pass
            else:raise AssertionError('strict schema accepted invalid value')
        plan=a.build_plan({'task':'Implement fixed behavior','roles':[role]},task_answers('everyday_implementation',1),str(project),'bounded',folder)
        call=plan['waves'][0]['calls'][0]
        assert (call['requested_combo'],call['effective_combo'],call['bounded_small'])==('Medium','Small',True)
        fail(folder,plan,call);repaired=escalate(folder,plan,call,True)
        assert repaired['policy_combo']=='Small' and a.validate_model(repaired,folder)=='Small'
        fail(folder,plan,repaired);raised=escalate(folder,plan,repaired)
        assert raised['effective_combo']=='Medium' and raised['requested_combo']=='Medium' and raised['bounded_small']
        assert a.validate_model(raised,folder)=='Medium'
        a.admit(plan['run_id'],raised['role_id'],raised['prompt'],plan['project'],plan['session'],folder)
        a.record(plan['run_id'],raised['role_id'],{'status':'COMPLETE','verification':['Independent checker passes'],'native':{'usage':{'input':9,'output':3}}},plan['project'],plan['session'],folder)
        db=project/'runs.sqlite';before=(db.stat().st_size,db.stat().st_mtime_ns)
        report=a.routing_report(str(project),folder)
        assert report['by_combo']=={'Medium':1} and report['by_status']=={'completed':1}
        assert report['attempts']=={'repairs':1,'escalations':1} and report['native_usage']=={'input':9,'output':3}
        assert (db.stat().st_size,db.stat().st_mtime_ns)==before
        assert 'prompt' not in json.dumps(report) and 'command' not in json.dumps(report)
        assert crew_catalog()['classification_policy']['bounded_implementation']['missing']=='unknown; retain Medium'
    print('PASS: bounded Small boundaries, strict facts, unsafe scopes, seams, independent checker, repair/escalation and read-only report')


if __name__=='__main__':run()
