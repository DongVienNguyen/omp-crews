"""Isolated directory freshness and cross-run nested-scope behavior checks."""
import tempfile
from pathlib import Path
from crews import omp_adapter as a, outcomes
from check_effort_policy import isolated_home, task_answers, rejects


def run():
    with tempfile.TemporaryDirectory(prefix='crews-authority-') as folder, isolated_home(folder):
        root=Path(folder);(root/'src').mkdir();source=root/'src'/'file.py';source.write_text('value=1\n')
        def snapshot():return outcomes.fingerprints(folder,['src'])
        first=snapshot();assert first['src'] is not None and first==snapshot()
        source.write_text('value=2\n');assert snapshot()!=first
        changed=snapshot();(root/'src'/'new.py').write_text('new\n');assert snapshot()!=changed
        (root/'src'/'new.py').unlink();assert snapshot()==changed
        def writer(name,scope):
            return {'name':name,'kind':'produce','mission':'Update declared source','deliverable':'source change','scope':scope,'inputs':[], 'acceptance':['Declared source updated'],'answers':{'need':'everyday_implementation','difficulty':1,'divisible':0,'specific':1}}
        def plan(roles,session):
            answers=task_answers('everyday_implementation',1);answers['divisible']['noul']=int(len(roles)>1)
            return a.build_plan({'task':'Update declared source','roles':roles},answers,folder,session,folder)
        parent=plan([writer('parent',['src'])],'parent');child=plan([writer('child',['src/file.py'])],'child')
        admitted=a.dispatch(parent['run_id'],'parent',folder,'parent',folder)
        rejects(lambda:a.dispatch(child['run_id'],'child',folder,'child',folder),'read/write conflict')
        a.record(parent['run_id'],'parent',{'status':'COMPLETE','verification':['fixture directory recorded']},folder,'parent',folder,host_key=admitted['host_key'])
        stored=a.results(parent['run_id'],folder,'parent',folder)[0]['result']['fingerprints']
        assert stored==snapshot()
        admitted=a.dispatch(child['run_id'],'child',folder,'child',folder)
        reader={'name':'reader','kind':'research','mission':'Read declared source','deliverable':'source facts','scope':[],'inputs':['src'],'answers':{'need':'bounded_retrieval','difficulty':1,'divisible':0,'specific':1}}
        reader['acceptance']=['Report declared source facts']
        reading=plan([reader],'reader')
        rejects(lambda:a.dispatch(reading['run_id'],'reader',folder,'reader',folder),'read/write conflict')
        a.record(child['run_id'],'child',{'status':'COMPLETE','verification':['fixture file recorded']},folder,'child',folder,host_key=admitted['host_key'])
        staged=plan([reader,writer('later',['later.txt'])],'staged')
        active=a.dispatch(staged['run_id'],'reader',folder,'staged',folder)
        a.record(staged['run_id'],'reader',{'status':'COMPLETE','verification':['fixture input recorded']},folder,'staged',folder,host_key=active['host_key'])
        source.write_text('value=3\n')
        rejects(lambda:a.dispatch(staged['run_id'],'later',folder,'staged',folder),'prior role evidence stale: src')
        with tempfile.TemporaryDirectory(prefix='crews-outside-') as outside:
            try:(root/'src'/'escape').symlink_to(outside,target_is_directory=True)
            except OSError:print('SKIP: symlink privilege unavailable')
            else:rejects(snapshot,'escapes project')
    print('PASS: recursive content/membership fingerprints, record consistency, earlier-wave stale input, nested cross-run writer/read conflicts')


if __name__=='__main__':run()
