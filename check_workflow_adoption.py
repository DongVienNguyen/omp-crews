"""Legacy adoption grants current authority, never invents historical provenance."""
import json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
from crews import workflow,runner,omp_adapter as a
from crews.governance import install
from crews.outcomes import digest
from check_effort_policy import isolated_home,rejects
from check_workflow import spec,request

def run():
 with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
  Path(folder,'fixture.txt').write_text('fixed source');identity=install(folder)['identity']
  old=dict(model='fixed-model',routing='fixed-routing',local=None)
  current=dict(old,local=dict(installation_id=identity,policy_binding='fixed-model',epoch=1))
  with patch.object(workflow,'_policy',return_value=old):prepared=runner.dispatch(request(spec()),folder,folder)
  with a.database(folder) as db:
   legacy=workflow._manifest(db,prepared['workflow_id']);legacy.pop('installation_id');legacy.pop('routes');db.execute('UPDATE workflows SET manifest=?',(json.dumps(legacy),))
   counters=db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()
  snapshot=dict(old_policy=digest(old),new_policy=digest(current),old_sources=digest(legacy['sources']),new_sources=digest(legacy['sources']))
  req=dict(operation='workflow_recover',slot='workflow',session='session',confirmed=True,snapshot=snapshot,adoption=dict(manifest=digest(legacy),provenance_unknown=True))
  with patch.object(workflow,'_policy',return_value=current):
   rejects(lambda:runner.dispatch(dict(req,adoption=dict(manifest='wrong',provenance_unknown=True)),folder,folder),'exact original manifest')
   rejects(lambda:runner.dispatch(dict(req,adoption=dict(manifest=digest(legacy),provenance_unknown=False)),folder,folder),'unknown-provenance')
   for invalid in [1,1.0,'true',None,False]:
    rejects(lambda:runner.dispatch(dict(req,adoption=dict(manifest=digest(legacy),provenance_unknown=invalid)),folder,folder),'unknown-provenance')
   rejects(lambda:runner.dispatch(dict(req,adoption=dict(manifest=digest(legacy))),folder,folder),'unknown-provenance')
   restored=runner.dispatch(req,folder,folder)
   assert restored['next']==prepared['next'] and restored['budget']==prepared['budget']
   rejects(lambda:runner.dispatch(req,folder,folder),'exact old/new')
  with a.database(folder) as db:
   adopted=workflow._manifest(db,prepared['workflow_id']);archive=json.loads(db.execute('SELECT previous_manifest FROM workflow_adoptions').fetchone()[0])
   assert archive==legacy and adopted['adoption']['provenance_unknown'] is True
   assert adopted['spec']==legacy['spec'] and adopted['acceptance']==legacy['acceptance']
   assert db.execute('SELECT used,repairs,escalations FROM workflows').fetchone()==counters
   for sql in ['DELETE FROM workflow_adoptions','UPDATE workflow_adoptions SET previous_manifest="changed"']:
    try:db.execute(sql)
    except sqlite3.IntegrityError:pass
    else:raise AssertionError('adoption history mutated')
 print('PASS explicit legacy adoption CAS, immutable original manifest, same IDs/counters, no replay')
if __name__=='__main__':run()
