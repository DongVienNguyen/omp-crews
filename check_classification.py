"""No-provider classifier, safety, preview, persistence and history contracts."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from pydantic import ValidationError
import omp_server as server
from crews import omp_adapter as a
from crews.classification import classify_role, policy_version

UTF8_ENV={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'}

def rejects(fn, fragment):
    try:
        fn()
    except (ValueError, ValidationError) as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError('unsafe input accepted: ' + fragment)


def main():
    corpus = json.loads((Path(__file__).parent/'examples/routing-corpus.json').read_text(encoding='utf-8'))
    for case in corpus:
        role = {'kind':case['kind'],'mission':case['mission'],'facts':case['facts'],
                'classification':True,'answers':{'divisible':0,'specific':1}}
        before = deepcopy(role)
        result = a.preview(role)
        assert role == before
        if case['need'] is None:
            assert result['answers'] is None and result['outcome']=='requires_classification', case['id']
        else:
            assert result['answers']['need']==case['need'], (case['id'], result)
            assert result['answers']['difficulty']==case['difficulty'], case['id']
        assert result['model']==case['model'], (case['id'], result)
        assert result['policy_version']==policy_version()
    role={'kind':'research','mission':'Read configuration','answers':{'need':'bounded_retrieval','difficulty':1,'divisible':0,'specific':1}}
    assert classify_role(role)['outcome']=='declared'
    for score,model in [(1,'code-seek'),(1.001,'code-sol')]:
        assert a.preview({**role,'answers':{**role['answers'],'difficulty':score}})['model']==model
    for score,effort in [(2.49,'low'),(2.5,'medium')]:
        result=a.preview({**role,'kind':'produce','answers':{**role['answers'],'need':'everyday_implementation','difficulty':score}})
        assert result['reasoning_effort']==effort, result
    for facts in ([], False, 0, ''):
        rejects(lambda:a.preview({**role,'facts':facts}),'ClassificationFacts')
    for key in ('unknown_cause','consequential_judgment','behavior_undecided'):
        rejects(lambda:a.preview({**role,'facts':{key:True}}),'answers.need')
    rejects(lambda:a.preview({**role,'facts':{'unknown_cause':0}}),'unknown_cause')
    rejects(lambda:a.preview({**role,'facts':{'unknown_cause':'false'}}),'unknown_cause')
    rejects(lambda:a.preview({**role,'facts':{'invented':False}}),'invented')
    rejects(lambda:a.preview({**role,'classification':True,'answers':{'divisible':0}}),'specific')
    rejects(lambda:a.preview({**role,'answers':{**role['answers'],'difficulty':True}}),'difficulty')
    rejects(lambda:a.preview({**role,'answers':{**role['answers'],'difficulty':float('nan')}}),'difficulty')
    with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as state:
        old=os.environ.get('CREWS_OMP_HOME');os.environ['CREWS_OMP_HOME']=state
        try:
            assert server.crew_test(role,project)['model']=='code-seek'
            assert a.history(project)==[] and not (Path(state)/'runs.sqlite').exists()
            spec=server.minimal_example()['spec']; task=server.minimal_example()['answers']
            auto=deepcopy(spec); auto['roles'][0].update(classification=True,solution_space='read only',facts=corpus[4]['facts'],answers={'divisible':0,'specific':1})
            plan=a.prepare_plan(auto,task,project,'auto-contract')
            call=plan['waves'][0]['calls'][0]
            assert call['role_answers']['need']=='bounded_retrieval'
            assert call['solution_space']=='read only' and call['facts']==corpus[4]['facts']
            assert call['declared_role_answers']=={'divisible':0,'specific':1}
            assert call['classification']['outcome']=='deterministic'
            assert auto['roles'][0]['answers']=={'divisible':0,'specific':1}
            rows=server.crew_history(project,1)
            assert len(rows)==1 and rows[0]['roles'][0]['status']=='planned'
            assert set(rows[0])=={'run_id','project','session','created','roles'}
            assert set(rows[0]['roles'][0])=={'role_id','status','model','reasoning_effort','role_answers','routing_reason'}
            with tempfile.TemporaryDirectory() as other: assert a.history(other)==[]
            for limit in (0,201,True,1.5): rejects(lambda:a.history(project,limit),'limit')
            bad=deepcopy(spec);bad['roles'][0]['facts']={'unknown_cause':True}
            rejects(lambda:a.build_plan(bad,task,project,'unsafe'),'spec.roles.0.answers.need')
            try: server.PlanArguments.model_validate({'spec':bad,'answers':task,'project':project,'session':'typed'})
            except ValidationError as exc: assert ('spec','roles',0,'answers','need') in {e['loc'] for e in exc.errors()}
            else: raise AssertionError('canonical safety accepted')
            unresolved=deepcopy(auto);unresolved['roles'][0]['facts']={}
            rejects(lambda:a.prepare_plan(unresolved,task,project,'unresolved'),'requires_classification')
            rejects(lambda:server.PlanSpec.model_validate(unresolved),'need')
            payload={'op':'preview','role':role,'project':project}
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'omp_bridge.py')],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,check=True,env={**UTF8_ENV,'CREWS_OMP_HOME':state})
            assert json.loads(result.stdout)['model']=='code-seek'
            payload={'op':'plan','spec':bad,'answers':task,'project':project,'session':'unsafe-bridge'}
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'omp_bridge.py')],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,env={**UTF8_ENV,'CREWS_OMP_HOME':state})
            assert result.returncode==1 and 'spec.roles.0.answers.need' in json.loads(result.stdout)['error']
            original_version=policy_version()
            policy={'provider':'local-provider','models':{'haiku':'small-v2','sonnet':'medium-v2','opus':'large-v2'}}
            policy_path=Path(state)/'policy.json'
            policy_path.write_text(json.dumps(policy),encoding='utf-8')
            assert policy_version()!=original_version
            preview=a.preview(role,project)
            assert (preview['model'],preview['provider'],preview['policy_model'],preview['tier'])==('small-v2','local-provider','code-seek','mechanical')
            assert server.crew_catalog()['model_policy']==policy
            assert preview['classifier_model']=='local-provider/small-v2:high'
            assert a.policy()['classifier_model']==preview['classifier_model']
            payload={'op':'policy'}
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'omp_bridge.py')],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,check=True,env={**UTF8_ENV,'CREWS_OMP_HOME':state})
            assert json.loads(result.stdout)==a.policy()
            rejects(lambda:a.admit(plan['run_id'],call['role_id'],call['prompt'],project,'auto-contract'),'policy binding')
            mapped=a.prepare_plan(spec,task,project,'mapped-contract')
            mapped_call=mapped['waves'][0]['calls'][0]
            assert (mapped_call['model'],mapped_call['provider'],mapped_call['policy_model'],mapped_call['agent_type'])==('small-v2','local-provider','code-seek','crew-research-seek')
            a.admit(mapped['run_id'],mapped_call['role_id'],mapped_call['prompt'],project,'mapped-contract')
            a.record(mapped['run_id'],mapped_call['role_id'],{'status':'FAILED','verification':['synthetic failure']},project,'mapped-contract')
            elevated=a.escalate(mapped['run_id'],mapped_call['role_id'],'synthetic failure',project,'mapped-contract')['call']
            assert (elevated['model'],elevated['provider'],elevated['policy_model'],elevated['agent_type'],elevated['reasoning_effort'])==('medium-v2','local-provider','code-sol','crew-research-sol','low')
            a.admit(mapped['run_id'],elevated['role_id'],elevated['prompt'],project,'mapped-contract')
            a.record(mapped['run_id'],elevated['role_id'],{'status':'FAILED','verification':['synthetic failure']},project,'mapped-contract')
            repaired=a.escalate(mapped['run_id'],elevated['role_id'],'synthetic repair',project,'mapped-contract',repair=True)['call']
            assert repaired['model']=='medium-v2' and repaired['policy_model']=='code-sol'
            policy_path.write_text(json.dumps({**policy,'secret':'forbidden'}),encoding='utf-8')
            rejects(lambda:a.model_policy(),'provider and models only')
            policy_path.write_text(json.dumps({**policy,'models':{**policy['models'],'haiku':'bad model'}}),encoding='utf-8')
            rejects(lambda:a.model_policy(),'bounded model/provider identifier')
            policy_path.unlink()
        finally:
            if old is None: os.environ.pop('CREWS_OMP_HOME',None)
            else: os.environ['CREWS_OMP_HOME']=old
    print(f'PASS: {len(corpus)} bilingual corpus cases, precedence, boundaries, strict facts, pure preview, intake, safety, history and bridge')


if __name__=='__main__': main()
