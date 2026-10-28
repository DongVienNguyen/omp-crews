"""Frozen evaluation unknown handling and duplicate-free restart behavior."""
import json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
from approval_fixture import Signer
from check_effort_policy import isolated_home,task_answers
from crews import evaluation,runner,omp_adapter as a


def run():
 with tempfile.TemporaryDirectory(prefix='crews-eval-') as folder,isolated_home(folder):
  p=Path(folder);signer=Signer()
  spec={'units':[{'id':'one','family':'parser','source_group':'original-task','split':'holdout','expected_abstain':False,'before_hash':'frozen','acceptance_hash':'accept'}],'noninferiority_margin':0,'max_latency_ratio':1.2,'min_cost_reduction':.15}
  signed=signer.approve({'operation':'freeze','spec':spec},folder,folder)
  eid=evaluation.dispatch(signed,folder,folder)['evaluation_id']
  out=evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':[]},folder,folder)
  assert out['selection']=='baseline' and out['rollout']=='NO_GO' and out['cost_gate'] is None and out['latency_gate'] is None and len(out['missing'])==2
  bad={**spec,'units':spec['units']+[{**spec['units'][0],'id':'two','split':'train'}]}
  try:evaluation.dispatch(signer.approve({'operation':'freeze','spec':bad},folder,folder),folder,folder)
  except ValueError:pass
  else:raise AssertionError('source-group leakage allowed')
  (p/'out.txt').write_text('before')
  role={'name':'bounded-out-writer','kind':'produce','mission':'Implement output text','deliverable':'out.txt','scope':['out.txt'],'inputs':['out.txt'],'commands':[],'acceptance':['output exact value'],'answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1}}
  request={'operation':'prepare','confirmed':True,'slot':'one','spec':{'task':'Implement output text','roles':[role]},'answers':task_answers('everyday_implementation',1),'session':'resume-proof'}
  first=runner.dispatch(request,folder,folder);second=runner.dispatch(request,folder,folder)
  assert first['run']==second['run'] and first['next']==second['next']
  with a.database(folder) as db:assert db.execute('SELECT count(*) FROM runs').fetchone()[0]==1
  ref=first['next'];admitted=a.dispatch(ref['run'],ref['role'],folder,ref['session'],folder)
  resumed=runner.dispatch({'operation':'status','slot':'one'},folder,folder)
  assert resumed['next'] is None and resumed['blocked']=='admitted_role_requires_explicit_recovery'
  assert (p/'out.txt').read_text()=='before'
  # Completed result remains completed, never offered for replay.
  a.record(ref['run'],ref['role'],{'status':'COMPLETE','verification':['observed output']},folder,ref['session'],folder,host_key=admitted['host_key'])
  assert runner.dispatch({'operation':'status','slot':'one'},folder,folder)['complete']
  incomplete=Path(folder)/'runner/crashed.json';incomplete.write_text(json.dumps({'project':a.canonical(folder),'run':None}))
  assert runner.dispatch({'operation':'status','slot':'crashed'},folder,folder)['next'] is None
  original_exists=Path.exists;original_open=Path.open;raced=Path(folder)/'runner/race.json'
  def open_race(path,*args,**kwargs):
   if path==raced and args and args[0]=='x':
    raced.write_text(json.dumps({'project':a.canonical(folder),'identity':'different-request','run':None}))
    raise FileExistsError()
   return original_open(path,*args,**kwargs)
  with patch.object(Path,'open',open_race):
   try:runner.dispatch({**request,'slot':'race'},folder,folder)
   except ValueError:pass
   else:raise AssertionError('concurrent different request reused runner slot')
  changed={**spec,'max_latency_ratio':2}
  with a.database(folder) as db:db.execute('UPDATE evaluations SET spec=? WHERE id=?',(json.dumps(changed),eid))
  try:evaluation.dispatch({'operation':'report','evaluation_id':eid,'results':[]},folder,folder)
  except ValueError:pass
  else:raise AssertionError('modified frozen manifest accepted')
 print('PASS: frozen holdout, no source leakage, unknown not zero, baseline abstention, restart does not duplicate/replay/overwrite')


if __name__=='__main__':run()
