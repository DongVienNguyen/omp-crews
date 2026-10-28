"""Source freshness, immutable attempt history, two-strike and accepted cost checks."""
import copy,json,tempfile
from pathlib import Path
from check_effort_policy import isolated_home
from crews import context_packets as context,attempt_ledger as ledger,omp_adapter as a
from crews.workflow_evaluation import summarize,compare,COMPONENTS


def reject(fn):
    try:fn()
    except (ValueError,__import__('sqlite3').IntegrityError):return
    raise AssertionError('expected refusal')


def run():
 with tempfile.TemporaryDirectory(prefix='sdlc-evidence-') as folder,isolated_home(folder):
  p=Path(folder);(p/'input.py').write_text('value=2\n')
  import hashlib
  packet=dict(version=1,sources=[dict(path='input.py',sha256=hashlib.sha256((p/'input.py').read_bytes()).hexdigest(),start=1,end=1)],observations=[dict(text='value is assigned2',sources=[0])],inferences=[],unresolved=[],needs_more_context=False)
  cell=dict(read_scope=['input.py'])
  assert context.validate(packet,cell,folder)==packet
  bad=copy.deepcopy(packet);bad['observations'][0]['sources']=[1];reject(lambda:context.validate(bad,cell,folder))
  (p/'input.py').write_text('value=3\n');reject(lambda:context.validate(packet,cell,folder))
  writer=dict(role_id='writer',policy_combo='Medium',write_scope=['out.py'],read_scope=[],acceptance=['output follows integer contract'],role_answers=dict(need='everyday_implementation'))
  checker=dict(role_id='checker',policy_combo='Small',write_scope=[],read_scope=['out.py'],acceptance=['output follows integer contract'],verify_targets=['writer'],role_answers=dict(need='mechanical_verification'))
  with a.database(folder) as db:
   for index in range(3):
    run='run'+str(index)
    db.execute('INSERT INTO attempts VALUES(?,?,?,?)',(run,'writer',0,index>0))
    ledger.record(db,run,'writer',a.canonical(folder),writer,dict(status='COMPLETE',native=dict(usage=dict(input=10,output=2)),outcome=dict(execution='completed')))
    ledger.record(db,run,'checker',a.canonical(folder),checker,dict(status='FAILED',host_authenticated=True,criterion_results=[dict(criterion='output follows integer contract',status='fail')],outcome=dict(behavior='fail',execution='task_failed')))
   assert ledger.strikes(db,a.canonical(folder),writer)==2
   reject(lambda:ledger.guard(db,a.canonical(folder),{**writer,'role_id':'renamed'}))
   ledger.guard(db,a.canonical(folder),{**writer,'policy_combo':'Large'})
   assert ledger.report(db,a.canonical(folder))['attempts']==6
   reject(lambda:db.execute('UPDATE execution_attempts SET combo=?',('Small',)))
   reject(lambda:db.execute('DELETE FROM execution_attempts'))
  def record(i,accepted,cost):return dict(id=i,family='integer',accepted=accepted,behavior='pass' if accepted else 'fail',false_complete=False,components={k:cost/len(COMPONENTS) for k in COMPONENTS},latency_ms=10,pricing_reference='isolated fixture, not real provider price')
  report=summarize([record('one',True,1),record('two',False,3)])
  assert report['cost_per_accepted']==4 and report['total_cost']==4
  bad=record('one',True,1);bad['components']['main']=None
  assert summarize([bad])['cost_per_accepted'] is None
  compared=compare([record('one',True,2)],[record('one',True,1)])
  assert compared['rollout']=='NO_GO' and compared['cost_gate'] and not compared['authenticated']
  swapped=compare([record('one',True,2),record('two',False,2)],[record('one',False,1),record('two',True,1)])
  assert not swapped['quality_gate'] and swapped['rollout']=='NO_GO'
  wrong=record('one',True,1);wrong['family']='other'
  reject(lambda:compare([record('one',True,2)],[wrong]))
 print('PASS source packet freshness/ref boundaries, immutable attempts/two-strike, failed task spend included, unknown costs preserved, caller rows never authorize rollout')


if __name__=='__main__':run()
