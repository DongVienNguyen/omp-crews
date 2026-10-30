"""Signed isolated trial lifecycle with real host checks, synthetic model receipts."""
import copy
import shutil
import tempfile
import time
from pathlib import Path
from approval_fixture import Signer
from check_effort_policy import isolated_home, rejects
from check_cross_node_proof import setup, complete
from crews import omp_adapter as a, workflow, outcomes, opportunities, capability_trials as trials


def main():
    with tempfile.TemporaryDirectory() as folder, isolated_home(folder):
        root=Path(folder);project=root/'project';project.mkdir();state=root/'state';signer=Signer()
        spec=setup(project,1.5)
        starting={p.name:p.read_bytes() for p in project.iterdir() if p.is_file()}
        first=workflow.dispatch(dict(operation='prepare',slot='baseline',session='baseline',workflow=spec,confirmed=True),str(project),state)
        writer=first['next'][0];cell=complete(writer,project,state,True)
        assert cell['policy_combo']=='Medium'
        second=workflow.dispatch(dict(operation='next',slot='baseline',session='baseline',confirmed=True),str(project),state)
        complete(second['next'][0],project,state)
        items=opportunities.report(str(project),state)['opportunities']
        assert len(items)==1 and items[0]['kind']=='medium_baseline_evidence'
        strategy=dict(kind='operator_deployment',identity='fixture-revision',expires=time.time()+900,policy_binding=a.policy_binding(state))
        review=dict(version=1,operation='review',opportunity_id=items[0]['id'],features=dict(domain='integer',language='python',operation='double',invariant='exact',dependency_shape='single'),version_strategy=strategy,confirmed=True)
        opportunities.dispatch(signer.approve(review,str(project),state),str(project),state)
        snapshot=project/'trial';snapshot.mkdir()
        for name,content in starting.items():(snapshot/name).write_bytes(content)
        request=dict(version=1,operation='prepare',opportunity_id=items[0]['id'],snapshot=str(snapshot),session='trial',workflow={**spec,'max_calls':2},expires=time.time()+900,frontier=trials.FRONTIER,confirmed=True)
        rejects(lambda:trials.dispatch(request,str(project),state),'signed')
        signed=signer.approve(request,str(project),state)
        prepared=trials.dispatch(signed,str(project),state)
        tid=prepared['trial_id'];ref=prepared['workflow']['next'][0]
        with a.database(state) as db:
            plan=a.load_run(db,ref['run'],str(snapshot),ref['session'])
            original=next(c for w in plan['waves'] for c in w['calls'] if c['role_id']=='writer')
            altered={**original,'workflow_id':None}
            rejects(lambda:trials.guard(db,altered,a.canonical(str(snapshot)),state),'frozen workflow')
        cell=complete(ref,snapshot,state,True)
        assert cell['policy_combo']=='Small' and cell['trial_id']==tid
        next_node=trials.dispatch(dict(version=1,operation='next',trial_id=tid),str(project),state)
        checker=next_node['next'][0]
        with a.database(state) as db:
            planned=a.load_run(db,checker['run'],str(snapshot),checker['session'])
            checker_cell=next(c for w in planned['waves'] for c in w['calls'])
            from unittest.mock import patch
            with patch('crews.capability_trials.deployment_digest',return_value='drift'):
                rejects(lambda:trials.guard(db,checker_cell,a.canonical(str(snapshot)),state),'deployment drift')
        complete(checker,snapshot,state)
        proof=outcomes.verified_pair(ref['run'],'writer',dict(run=checker['run'],role='checker'),str(snapshot),state)
        result=trials.dispatch(dict(version=1,operation='finish',trial_id=tid,reference=proof['reference'],confirmed=True),str(project),state)
        assert result['behavior']=='pass' and not result['label_created'] and not result['activated']
        from crews import recipes
        features=dict(domain='integer',language='python',operation='double',invariant=spec['invariants'][0],dependency_shape='single')
        roles=[r for n in spec['nodes'] for r in n['roles']]
        profile=roles[1]['checker_profile']
        recipe=dict(features=features,version=1,cue='fixed integer mapping',lesson='Preserve independently checked integer behavior',evidence=['Actual isolated Small proof'],negative_examples=['unknown risk'],applicability=features,exclusions=[],profile={k:profile[k] for k in ('input','command')},recipe_steps=['Preserve original mapping'],max_difficulty=1.5,model_binding=proof['model_binding'],frontier=trials.FRONTIER,version_strategy=strategy)
        register=dict(operation='register',recipe=recipe,role=roles[0],roles=roles,machine_consent=True)
        rid=recipes.dispatch(signer.approve(register,str(project),state),str(project),state)['recipe_id']
        evidence=dict(operation='evidence',recipe_id=rid,project=str(snapshot),reference=proof['reference'],split='train')
        accepted=recipes.dispatch(signer.approve(evidence,str(project),state),str(project),state)
        assert accepted['accepted'] and accepted['train']==1 and accepted['holdout']==0
        another=project/'another';another.mkdir()
        for name,content in starting.items():(another/name).write_bytes(content)
        duplicate_session={**request,'snapshot':str(another)}
        rejects(lambda:trials.dispatch(signer.approve(duplicate_session,str(project),state),str(project),state),'session cap')
        cancel_request={**request,'snapshot':str(another),'session':'cancel-trial'}
        cancel=trials.dispatch(signer.approve(cancel_request,str(project),state),str(project),state)
        active=cancel['workflow']['next'][0]
        ticket=a.dispatch(active['run'],active['role'],str(another),active['session'],state)
        settled=trials.dispatch(dict(version=1,operation='cancel',trial_id=cancel['trial_id'],confirmed=True),str(project),state)
        assert settled['behavior']=='unknown' and not settled['activated']
        rejects(lambda:a.ticket(ticket['token'],str(another),state),'trial ticket authority inactive')
        a.record(active['run'],active['role'],dict(status='FAILED',failure_kind='cancelled',verification=['Cancelled isolated trial']),str(another),active['session'],state,host_key=ticket['host_key'])
        third=project/'third';third.mkdir()
        for name,content in starting.items():(third/name).write_bytes(content)
        capped={**request,'snapshot':str(third),'session':'third-trial'}
        rejects(lambda:trials.dispatch(signer.approve(capped,str(project),state),str(project),state),'day cap')
        rejects(lambda:trials.dispatch(dict(version=1,operation='next',trial_id=tid),str(project),state),'replay')
        for name,content in starting.items():(snapshot/name).write_bytes(content)
        rejects(lambda:trials.dispatch(signed,str(project),state),'executed')
    print('PASS signed Medium opportunity -> isolated Small trial -> independent split-node proof -> immutable settlement; synthetic model receipts only')

if __name__=='__main__':main()
