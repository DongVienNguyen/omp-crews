"""Dead reservation recovery never replays admitted or completed work."""
import tempfile
import subprocess,sys
from pathlib import Path
from unittest.mock import patch
from check_effort_policy import isolated_home, rejects
from check_workflow import spec,request,complete
from crews import omp_adapter as a,runner


def run():
    for orphan in (False,True):
        with tempfile.TemporaryDirectory() as folder,isolated_home(folder):
            p=Path(folder);(p/'fixture.txt').write_text('fixed source')
            original=a.prepare_plan
            def crash(*args,**kwargs):
                if orphan:original(*args,**kwargs)
                raise RuntimeError('simulated host crash')
            with patch.object(a,'prepare_plan',side_effect=crash):
                try:runner.dispatch(request(spec()),folder,folder)
                except RuntimeError:pass
                else:raise AssertionError('crash not reached')
            dead=subprocess.Popen([sys.executable,'-c','pass']);dead.wait()
            with a.database(folder) as db:
                wid=db.execute('SELECT id FROM workflows').fetchone()[0]
                db.execute('UPDATE workflow_reservations SET owner=?',(dead.pid,))
                runs=list(db.execute('SELECT id FROM runs'))
            unrelated=spec()['nodes'][0]['roles'][0].copy();unrelated['name']='unrelated'
            a.prepare_plan(dict(task='Unrelated policy lookup',roles=[unrelated]),spec()['nodes'][0]['answers'],folder,'session',folder)
            req=dict(operation='workflow_recover',slot='workflow',session='session',node='discovery',confirmed=True)
            if orphan:req['run']=runs[0][0]
            status=runner.dispatch(req,folder,folder)
            assert status['next'][0]['role']=='inspect-policy-source',status
            if orphan:assert status['next'][0]['run']==runs[0][0]
            assert status['budget']['planned']==1
            complete(status['next'][0],p,folder)
            rejects(lambda:runner.dispatch(req,folder,folder),'dead reservation owner')
    print('PASS dead reservation recovery before/after canonical plan creation, orphan reattachment, one debit and no completed replay')

if __name__=='__main__':run()
