"""Explicit snapshot refresh keeps identity/counters and refuses any execution."""
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from crews import workflow,runner,omp_adapter as a
from crews.outcomes import digest
from check_effort_policy import isolated_home,rejects
from check_workflow import spec,request

def run():
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  Path(folder,'fixture.txt').write_text('fixed source')
  from crews.governance import install
  identity=install(folder)['identity']
  old=dict(model='fixed-model',routing='fixed-routing',local=dict(installation_id=identity,policy_binding='fixed-model',epoch=1))
  new=dict(old,routing='renewed-routing-code',local=dict(old['local'],epoch=2))
  with patch.object(workflow,'_policy',return_value=old):prepared=runner.dispatch(request(spec()),folder,folder)
  ref=prepared['next'][0]
  with a.database(folder) as db:
   manifest=workflow._manifest(db,prepared['workflow_id'])
   before=db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()
  expected=dict(old_policy=digest(old),new_policy=digest(new),old_sources=digest(manifest['sources']),new_sources=digest(manifest['sources']))
  Path(folder,'fixture.txt').write_text('operator-reviewed changed source')
  updated_sources=workflow._sources(folder,manifest['spec'])
  expected['new_sources']=digest(updated_sources)
  req=dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=expected)
  with patch.object(workflow,'_policy',return_value=new):
   rejects(lambda:runner.dispatch(dict(req,snapshot=dict(expected,new_policy='wrong')),folder,folder),'exact old/new')
   with patch.object(a,'effective_combo',return_value=('Large','code-astra','high')):
    rejects(lambda:runner.dispatch(req,folder,folder),'frozen routes')
   route=a.effective_combo
   def pending_changed(role,*args):return ('Large','code-astra','high') if role['name']=='inspect-policy-next' else route(role,*args)
   with patch.object(a,'effective_combo',side_effect=pending_changed):rejects(lambda:runner.dispatch(req,folder,folder),'frozen routes')
   restored=runner.dispatch(req,folder,folder)
   assert restored['next']==prepared['next'] and restored['budget']==prepared['budget']
   rejects(lambda:runner.dispatch(req,folder,folder),'exact old/new')
  with a.database(folder) as db:
   assert db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()==before
   plan=a.load_run(db,ref['run'],a.canonical(folder),'session')
   assert plan['waves'][0]['calls'][0]['workflow_policy_snapshot']==new
   assert plan['waves'][0]['calls'][0]['routing_policy_version']==new['routing']
   refreshed=workflow._manifest(db,prepared['workflow_id'])
   assert refreshed['sources']==updated_sources and refreshed['spec']==manifest['spec']
   assert refreshed['acceptance']==manifest['acceptance'] and refreshed['profile']==manifest['profile']
   assert len(refreshed['snapshot_recoveries'])==1
   db.execute("UPDATE calls SET status='admitted' WHERE run=?",(ref['run'],))
  newer=dict(new,local=dict(new['local'],epoch=3))
  req['snapshot']=dict(expected,old_policy=digest(new),new_policy=digest(newer),old_sources=digest(updated_sources))
  with patch.object(workflow,'_policy',return_value=newer):rejects(lambda:runner.dispatch(req,folder,folder),'executed or admitted')
  with a.database(folder) as db:
   assert workflow._manifest(db,prepared['workflow_id'])['policy']==new
   assert db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()==before
  with a.database(folder) as db:
   db.execute("UPDATE calls SET status='planned',result=NULL WHERE run=?",(ref['run'],))
   db.execute('INSERT INTO attempts VALUES(?,?,?,?)',(ref['run'],ref['role'],0,1))
  with patch.object(workflow,'_policy',return_value=newer):rejects(lambda:runner.dispatch(req,folder,folder),'retry history')
  with a.database(folder) as db:
   assert workflow._manifest(db,prepared['workflow_id'])['policy']==new
   assert db.execute('SELECT repairs FROM attempts WHERE run=?',(ref['run'],)).fetchone()==(1,)
  changed=dict(new,model='different')
  req['snapshot']=dict(expected,old_policy=digest(new),new_policy=digest(changed),old_sources=digest(updated_sources))
  with patch.object(workflow,'_policy',return_value=changed):rejects(lambda:runner.dispatch(req,folder,folder),'model policy')
  disabled=dict(new,local=None)
  req['snapshot']=dict(expected,old_policy=digest(new),new_policy=digest(disabled),old_sources=digest(updated_sources))
  with patch.object(workflow,'_policy',return_value=disabled):rejects(lambda:runner.dispatch(req,folder,folder),'same-installation')
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  Path(folder,'fixture.txt').write_text('fixed source')
  identity=install(folder)['identity']
  old=dict(model='fixed-model',routing='fixed-routing',local=None)
  new=dict(old,local=dict(installation_id=identity,policy_binding='fixed-model',epoch=1))
  with patch.object(workflow,'_policy',return_value=old):prepared=runner.dispatch(request(spec()),folder,folder)
  with a.database(folder) as db:manifest=workflow._manifest(db,prepared['workflow_id'])
  snapshots=dict(old_policy=digest(old),new_policy=digest(new),old_sources=digest(manifest['sources']),new_sources=digest(manifest['sources']))
  foreign=dict(new,local=dict(new['local'],installation_id='f'*32))
  with patch.object(workflow,'_policy',return_value=foreign):rejects(lambda:runner.dispatch(dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=dict(snapshots,new_policy=digest(foreign))),folder,folder),'same-installation')
  with a.database(folder) as db:
   legacy=json.loads(json.dumps(manifest));legacy.pop('installation_id');db.execute('UPDATE workflows SET manifest=?',(json.dumps(legacy),))
  with patch.object(workflow,'_policy',return_value=new):rejects(lambda:runner.dispatch(dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=snapshots),folder,folder),'explicit current-authority adoption')
  with a.database(folder) as db:db.execute('UPDATE workflows SET manifest=?',(json.dumps(manifest),))
  with patch.object(workflow,'_policy',return_value=new):restored=runner.dispatch(dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=snapshots),folder,folder)
  assert restored['next']==prepared['next'] and restored['budget']==prepared['budget']
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  Path(folder,'fixture.txt').write_text('fixed source');identity=install(folder)['identity']
  old=dict(model='fixed-model',routing='fixed-routing',local=dict(installation_id=identity,policy_binding='fixed-model',epoch=1));new=dict(old,local=dict(old['local'],epoch=2))
  with patch.object(workflow,'_policy',return_value=old),patch.object(workflow,'_advance'):
   pending=runner.dispatch(request(spec()),folder,folder)
  with a.database(folder) as db:
   manifest=workflow._manifest(db,pending['workflow_id']);before=db.execute('SELECT used,repairs,escalations FROM workflows').fetchone();runs=db.execute('SELECT count(*) FROM runs').fetchone()
  snapshots=dict(old_policy=digest(old),new_policy=digest(new),old_sources=digest(manifest['sources']),new_sources=digest(manifest['sources']))
  with patch.object(workflow,'_policy',return_value=new):restored=runner.dispatch(dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=snapshots),folder,folder)
  assert not restored['next'] and all(node['state']=='pending' for node in restored['nodes'])
  with a.database(folder) as db:
   assert db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()==before
   assert db.execute('SELECT count(*) FROM runs').fetchone()==runs
 print('PASS snapshot CAS, unchanged run/counters, stale recovery and admitted/model-change refusal')
if __name__=='__main__':run()
