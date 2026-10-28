"""Real frozen baseline/candidate accounting and acceptance; no caller score."""
import json,sys,tempfile
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home,task_answers
from crews import evaluation,omp_adapter as a,outcomes
from crews.accounting import attest


def run():
 with tempfile.TemporaryDirectory(prefix='crews-eval-positive-') as folder,isolated_home(folder):
  root=Path(folder);signer=Signer();criterion='target value equals two'
  before={'target.py':outcomes.digest('value=0'),'input.json':outcomes.digest('input')}
  # Real input hashes, same relative snapshots for both arms.
  for arm in ('baseline','candidate'):
   p=root/arm;p.mkdir();(p/'target.py').write_text('value=0\n');(p/'input.json').write_text('{}')
   (p/'verify.py').write_text('import json\nfrom target import value\nassert value==2\nprint(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
  before=outcomes.fingerprints(str(root/'baseline'),['input.json','target.py'])
  contract=outcomes.digest({'acceptance':[criterion],'before':before})
  spec={'units':[{'id':'u1','family':'mapping','source_group':'original-a','split':'holdout','expected_abstain':False,'before_hash':contract,'acceptance_hash':outcomes.digest([criterion])}],'noninferiority_margin':0,'max_latency_ratio':1.2,'min_cost_reduction':.15}
  freeze=signer.approve({'operation':'freeze','spec':spec},folder,folder);eid=evaluation.dispatch(freeze,folder,folder)['evaluation_id'];refs=[]
  for arm,cost in [('baseline',1.0),('candidate',.5)]:
   p=root/arm;command=sys.executable.replace('\\','/')+' -B verify.py'
   writer={'name':'value-writer','kind':'produce','mission':'Implement target value equals two','deliverable':'target.py','scope':['target.py'],'inputs':['input.json','target.py'],'commands':[],'acceptance':[criterion],'answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1}}
   check={'name':'value-check','kind':'check','mission':'Verify target value equals two','deliverable':'verdict','scope':[],'inputs':['input.json','target.py','verify.py'],'commands':[command],'criteria':[criterion],'verify_targets':['value-writer'],'checker_profile':{'input':'verify.py','command':command,'version':'1'},'answers':{'need':'mechanical_verification','difficulty':1,'divisible':0,'specific':1}}
   plan=a.build_plan({'task':criterion,'roles':[writer,check]},task_answers('everyday_implementation',1,True),str(p),arm,folder);(p/'target.py').write_text('value=2\n')
   for role in ('value-writer','value-check'):
    dispatch=a.dispatch(plan['run_id'],role,str(p),arm,folder);cell=dispatch['call'];token=dispatch['token'];wire={'token':token,'role':role,'provider':cell['provider'],'model':cell['model'],'effort':cell['reasoning_effort']};a.store_receipt(token,str(p),wire,folder)
    if cell.get('checker_profile'):a.verify_profile(token,str(p),folder,host_key=dispatch['host_key'])
    result={'status':'COMPLETE','verification':['independent executable acceptance'],'native':{'exitCode':0,'resolvedModel':cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],'resolvedThinkingLevel':cell['reasoning_effort']},'wire':wire}
    a.record(plan['run_id'],role,result,str(p),arm,folder,host_key=dispatch['host_key'])
   metrics={'cost':cost,'latency_ms':10,'pricing_reference':'independent fixture pricing','includes':['producer','checker','classifier','main','repairs']}
   attest(signer.approve({'run':plan['run_id'],'metrics':metrics},str(p),folder),str(p),folder)
   refs.append({'unit':'u1','arm':arm,'run':plan['run_id'],'producer':'value-writer','checker':'value-check','project':str(p)})
  report=evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':refs},folder,folder)
  assert report['rollout']=='GO' and report['selection']=='candidate' and report['accounting_complete']
  assert report['accepted_task_cost']=={'baseline':1.0,'candidate':.5}
  duplicate=[refs[0],{**refs[0],'arm':'candidate'}]
  try:evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':duplicate},folder,folder)
  except ValueError:pass
  else:raise AssertionError('same run reused as both evaluation arms')
  with a.database(folder) as db:
   result=json.loads(db.execute('SELECT result FROM calls WHERE run=? AND role=?',(refs[1]['run'],'value-check')).fetchone()[0])
   result['outcome']['behavior']='unknown'
   db.execute('UPDATE calls SET result=? WHERE run=? AND role=?',(json.dumps(result),refs[1]['run'],'value-check'))
  unknown=evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':refs},folder,folder)
  assert unknown['rollout']=='NO_GO' and any(len(x)>2 and x[2]=='independent_behavior_unknown' for x in unknown['missing'])
  with a.database(folder) as db:
   frozen=db.execute('SELECT created FROM evaluations WHERE id=?',(eid,)).fetchone()[0]
   db.execute('UPDATE runs SET created=? WHERE id=?',(frozen,refs[0]['run']))
  equal=evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':refs},folder,folder)
  assert equal['rollout']=='NO_GO' and any(v[2]=='run_precedes_frozen_holdout' for v in equal['violations'])
 print('PASS: frozen contract, real verifier receipts, full accounting and noninferiority select improved candidate')


if __name__=='__main__':run()
