"""Failed-workflow renewal retains identity, counters and immutable attempt evidence."""
import json,tempfile,time
from pathlib import Path
from unittest.mock import patch
from crews import workflow,runner,omp_adapter as a
from crews.outcomes import digest,fingerprints
from check_effort_policy import isolated_home,rejects
from check_workflow import spec,request

def run():
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  Path(folder,'fixture.txt').write_text('original')
  from crews.governance import install
  identity=install(folder)['identity']
  old=dict(model=a.policy_binding(folder),routing='old-routing',local=dict(installation_id=identity,policy_binding=a.policy_binding(folder),epoch=1))
  new=dict(old,routing='renewed-routing',local=dict(old['local'],epoch=2))
  with patch.object(workflow,'_policy',return_value=old):prepared=runner.dispatch(request(spec()),folder,folder)
  ref=prepared['next'][0]
  with a.database(folder) as db:
   plan=json.loads(db.execute('SELECT plan FROM runs WHERE id=?',(ref['run'],)).fetchone()[0]);cell=plan['waves'][0]['calls'][0]
   result=dict(status='FAILED',verification=['recorded fixture failure'],fingerprints=fingerprints(folder,cell['read_scope']),host_authenticated=True)
   db.execute("UPDATE calls SET status='failed',result=? WHERE run=?",(json.dumps(result),ref['run']))
   from crews.attempt_ledger import record
   record(db,ref['run'],ref['role'],a.canonical(folder),cell,result)
   db.execute('UPDATE runs SET created=? WHERE id=?',(time.time()-90000,ref['run']))
   manifest=workflow._manifest(db,prepared['workflow_id']);before=db.execute('SELECT used,repairs,escalations FROM workflows').fetchone();created=db.execute('SELECT created FROM runs WHERE id=?',(ref['run'],)).fetchone()[0]
  Path(folder,'fixture.txt').write_text('operator reviewed source')
  snapshot=dict(old_policy=digest(old),new_policy=digest(new),old_sources=digest(manifest['sources']),new_sources=digest(workflow._sources(folder,manifest['spec'])))
  recover=dict(operation='workflow_recover',slot='workflow',session='session',node='discovery',run=ref['run'],confirmed=True,snapshot=snapshot)
  with patch.object(workflow,'_policy',return_value=new):
   rejects(lambda:runner.dispatch(dict(recover,snapshot=dict(snapshot,new_sources='wrong')),folder,folder),'exact old/new')
   rejects(lambda:runner.dispatch(dict(recover,run='wrong'),folder,folder),'exact recorded failed')
   rejects(lambda:runner.dispatch(dict(recover,confirmed=False),folder,folder),'explicit confirmation')
   with a.database(folder) as db:db.execute('UPDATE workflows SET repairs=2')
   rejects(lambda:runner.dispatch(recover,folder,folder),'exhausted repair')
   with a.database(folder) as db:db.execute('UPDATE workflows SET repairs=0');db.execute("UPDATE workflow_nodes SET state='reserved' WHERE node='architecture'")
   rejects(lambda:runner.dispatch(recover,folder,folder),'active or unknown')
   with a.database(folder) as db:db.execute("UPDATE workflow_nodes SET state='pending' WHERE node='architecture'")
   with a.database(folder) as db:db.execute('UPDATE workflows SET used=3')
   rejects(lambda:runner.dispatch(recover,folder,folder),'exhausted repair')
   with a.database(folder) as db:db.execute('UPDATE workflows SET used=1');db.execute("UPDATE workflow_nodes SET state='completed' WHERE node='architecture'")
   rejects(lambda:runner.dispatch(recover,folder,folder),'completed evidence')
   with a.database(folder) as db:db.execute("UPDATE workflow_nodes SET state='pending' WHERE node='architecture'")
   with a.database(folder) as db:db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',(ref['run'],'mixed-sibling','fixture','completed',json.dumps(result)))
   rejects(lambda:runner.dispatch(recover,folder,folder),'completed evidence')
   with a.database(folder) as db:db.execute("UPDATE calls SET status='unknown' WHERE role='mixed-sibling'")
   rejects(lambda:runner.dispatch(recover,folder,folder),'unknown call ownership')
   with a.database(folder) as db:db.execute("DELETE FROM calls WHERE role='mixed-sibling'")
   with patch.object(workflow,'_route_snapshot',return_value={}):rejects(lambda:runner.dispatch(recover,folder,folder),'frozen routes')
   renewed=runner.dispatch(recover,folder,folder)
   assert renewed.get('blocked')=='failed_node_requires_explicit_recovery' and not renewed['next']
   rejects(lambda:runner.dispatch(recover,folder,folder),'exact old/new')
   unchanged=dict(old_policy=digest(new),new_policy=digest(new),old_sources=snapshot['new_sources'],new_sources=snapshot['new_sources'])
   rejects(lambda:runner.dispatch(dict(recover,snapshot=unchanged),folder,folder),'changed policy or source')
  with a.database(folder) as db:
   assert db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()==before
   assert db.execute('SELECT created FROM runs WHERE id=?',(ref['run'],)).fetchone()[0]==created
   assert db.execute('SELECT count(*) FROM execution_attempts').fetchone()==(1,)
   assert db.execute('SELECT status FROM calls WHERE run=?',(ref['run'],)).fetchone()==('failed',)
   assert a.load_run(db,ref['run'],folder,'session')['run_id']==ref['run']
   renewal=db.execute('SELECT expires FROM run_renewals WHERE run=?',(ref['run'],)).fetchone()[0]
   with patch.object(a.time,'time',return_value=renewal+1):rejects(lambda:a.load_run(db,ref['run'],folder,'session'),'expired')
  with a.database(folder) as db:
   try:db.execute('DELETE FROM run_renewals');raise AssertionError('renewal history was mutable')
   except a.sqlite3.IntegrityError:pass
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  from check_cross_node_proof import setup,complete
  from crews.governance import install
  project=Path(folder);value=setup(project);identity=install(folder)['identity']
  old=dict(model=a.policy_binding(folder),routing='old',local=dict(installation_id=identity,policy_binding=a.policy_binding(folder),epoch=1));new=dict(old,routing='new',local=dict(old['local'],epoch=2))
  with patch.object(workflow,'_policy',return_value=old):prepared=workflow.dispatch(dict(operation='prepare',slot='cross',session='cross',workflow=value,confirmed=True),folder,folder)
  ref=prepared['next'][0]
  with patch.object(a,'validate_model',return_value='Small'),patch('crews.automation.validate_snapshot'),patch.object(workflow,'_policy',return_value=old):cell=complete(ref,project,folder,status='FAILED')
  assert cell['policy_combo']=='Small'
  with a.database(folder) as db:manifest=workflow._manifest(db,prepared['workflow_id'])
  snapshot=dict(old_policy=digest(old),new_policy=digest(new),old_sources=digest(manifest['sources']),new_sources=digest(manifest['sources']))
  req=dict(operation='recover',slot='cross',session='cross',node='writer',run=ref['run'],confirmed=True,snapshot=snapshot)
  with patch.object(workflow,'_policy',return_value=new):renewed=workflow.dispatch(req,folder,folder)
  assert renewed['blocked']=='failed_node_requires_explicit_recovery'
  with a.database(folder) as db:
   plan=json.loads(db.execute('SELECT plan FROM runs WHERE id=?',(ref['run'],)).fetchone()[0]);assert plan['waves'][0]['calls'][0]['policy_combo']=='Small'
 print('PASS failed renewal CAS, same run/creation/counters, immutable failure, no replay, renewed expiry')
if __name__=='__main__':run()
