"""Exercise real plan/profile/receipt/learning/intake boundaries in isolated state."""
import json,sys,tempfile
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home,task_answers
from crews import omp_adapter as a,outcomes,recipes


def run():
 with tempfile.TemporaryDirectory(prefix='crews-recipe-intake-') as directory,isolated_home(directory):
  p=Path(directory);signer=Signer();criterion='result doubles immutable input, preserving integer type'
  command=sys.executable.replace('\\','/')+' -B verify.py'
  (p/'verify.py').write_text('import json\nfrom target import result\nvalue=json.load(open("input.json"))["value"]\nassert type(result) is int and result==value*2\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
  facts={**dict.fromkeys(recipes.TRUE_FACTS,True),**dict.fromkeys(recipes.FALSE_FACTS,False)}
  features=dict(domain='mapping',language='python',operation='double',invariant=criterion,dependency_shape='single_component')
  writer=dict(name='double-writer',kind='produce',mission='Implement integer result doubles input',deliverable='target.py',scope=['target.py'],inputs=['input.json','target.py'],commands=[],acceptance=[criterion],routine_check='double-check',model_revision='fixture-revision-1',facts=facts,recipe_features=features,recipe_profile={'input':'verify.py','command':command},answers=dict(need='everyday_implementation',difficulty=1,divisible=0,specific=1))
  checker=dict(name='double-check',kind='check',mission='Verify integer result doubles input',deliverable='verdict',scope=[],inputs=['target.py','input.json','verify.py'],commands=[command],criteria=[criterion],verify_targets=['double-writer'],checker_profile=dict(input='verify.py',command=command,version='1'),answers=dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1))
  roles=[writer,checker]
  (p/'input.json').write_text('{"value":0}');(p/'target.py').write_text('result=-1\n')
  from crews.classification import policy_version
  binding=outcomes.digest({'provider':'9router','model':'code-seek','effort':'medium','policy':policy_version(),'revision':'fixture-revision-1'})
  writer['model_binding']=binding
  body=dict(features=features,version=1,cue='fixed integer mapping',lesson='preserve exact input/output invariant',evidence=['independent fixture contract'],negative_examples=['unknown behavior or concurrency'],applicability={'domain':'mapping'},exclusions=[],profile=writer['recipe_profile'],recipe_steps=['Read immutable input and map result; independent checker gates acceptance'],max_difficulty=1,model_binding=binding)
  def admin(request):return recipes.dispatch(signer.approve(request,directory,directory),directory,directory)
  rid=admin(dict(operation='register',recipe=body,role=writer,roles=roles,machine_consent=True))['recipe_id']
  for value in range(5):
   (p/'input.json').write_text(json.dumps({'value':value}));(p/'target.py').write_text('result=-1\n')
   session='fixture-'+str(value)
   plan=a.build_plan({'task':'Implement integer result doubles input','roles':roles},task_answers('everyday_implementation',1,True),directory,session,directory)
   (p/'target.py').write_text('result='+str(value*2)+'\n')
   for role in ['double-writer','double-check']:
    admitted=a.dispatch(plan['run_id'],role,directory,session,directory);cell=admitted['call'];token=admitted['token']
    proof=dict(token=token,role=role,provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort']);a.store_receipt(token,directory,proof,directory)
    if cell.get('checker_profile'):a.verify_profile(token,directory,directory,host_key=admitted['host_key'])
    result=dict(status='COMPLETE',producer_claim='COMPLETE',verification=['fixture model output, independently executable acceptance'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']),wire=proof)
    a.record(plan['run_id'],role,result,directory,session,directory,host_key=admitted['host_key'])
   accepted=admin(dict(operation='evidence',recipe_id=rid,run=plan['run_id'],producer='double-writer',checker='double-check',split='train' if value<3 else 'holdout'))
   assert accepted['accepted']
  admin(dict(operation='activate',recipe_id=rid));admin(dict(operation='configure',mode='on'))
  writer['recipe_confirmed']=True
  proposal=a.build_plan({'task':'Implement integer result doubles input','roles':roles},task_answers('everyday_implementation',1,True),directory,'active-intake',directory)
  cell=next(c for w in proposal['waves'] for c in w['calls'] if c['role_id']=='double-writer')
  assert cell['recipe_id']==rid and cell['recipe_evidence']['effective_small'] and 'Read immutable input' in cell['prompt']
  unsafe={**writer,'facts':{**facts,'concurrency_sensitive':True}}
  assert not recipes.match(unsafe,directory,[unsafe,checker],directory)['effective_small']
  assert recipes.dispatch({'operation':'status'},directory,directory)['recipes'][0]['hits']==1
  assert recipes.dispatch({'operation':'status'},directory,directory)['captures']==5
  from unittest.mock import patch
  with patch('crews.automation.audit_interval',return_value=1):
   for index in (10,11,12):
    (p/'input.json').write_text(json.dumps({'value':index}));(p/'target.py').write_text('result=-1\n')
    audit=a.build_plan({'task':'Implement integer result doubles input','roles':roles},task_answers('everyday_implementation',1,True),directory,'audit-'+str(index),directory)
    current=next(c for w in audit['waves'] for c in w['calls'] if c['role_id']=='double-writer')
    assert current['policy_combo']=='Small' and current['audit_delivery_token']
    assert not recipes.dispatch(dict(operation='lookup',role=writer,roles=roles,confirmed=True),directory,directory)['effective_small']
    for name in ['double-writer','double-check']:
     ticket=a.dispatch(audit['run_id'],name,directory,audit['session'],directory);cell=ticket['call'];token=ticket['token']
     if name=='double-writer':(p/'target.py').write_text('result='+str(index*2)+'\n')
     wire=dict(token=token,role=name,provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort']);a.store_receipt(token,directory,wire,directory)
     if cell.get('checker_profile') and index!=12:a.verify_profile(token,directory,directory,host_key=ticket['host_key'])
     result=dict(status='COMPLETE',verification=['Isolated audit fixture'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']),wire=wire)
     if index==12 and name=='double-check':result=dict(status='COMPLETE',verification=['Fixture unverifiable completion without native exit receipt'])
     a.record(audit['run_id'],name,result,directory,audit['session'],directory,host_key=ticket['host_key'])
    row=recipes.dispatch(dict(operation='status'),directory,directory)['recipes'][0]
    if index==12:assert row['state']=='suspended' and not row['audit_pending'] and row['audits']==2
    else:assert row['audits']==index-9 and not row['audit_pending'] and row['train']+row['holdout']==5
 print('PASS real intake: verified script results -> consented evidence -> holdout activation -> approved recipe -> fresh Small plan; unsafe abstains')


if __name__=='__main__':run()
