"""Keyless local policy lifecycle; synthetic model receipts, real host ledger."""
import copy,json,tempfile,time,sys
from pathlib import Path
from check_effort_policy import isolated_home
from crews import automation as auto, omp_adapter as a


def rejects(fn):
    try:fn()
    except (ValueError,TypeError):return
    raise AssertionError('expected refusal')


def review(ref,folder,decision=None,status='COMPLETE',authenticated=True):
    ticket=a.dispatch(ref['run'],ref['role'],folder,ref['session'],folder);cell=ticket['call'];token=ticket['token']
    wire=dict(token=token,role=cell['role_id'],provider=cell['provider'],model=cell['model'],effort=cell['reasoning_effort'])
    a.store_receipt(token,folder,wire,folder)
    result=dict(status=status,producer_claim=status,policy_decision=decision,verification=['fixture independent Large aggregate review'],native=dict(exitCode=0,resolvedModel=cell['provider']+'/'+cell['model']+':'+cell['reasoning_effort'],resolvedThinkingLevel=cell['reasoning_effort']),wire=wire)
    a.record(ref['run'],ref['role'],result,folder,ref['session'],folder,host_key=ticket['host_key'] if authenticated else None)


def floor_transitions():
    from crews import governance
    floor=dict(mode='floor',combo='Medium')
    baseline=dict(mode='baseline',combo='Medium')
    lower=dict(mode='floor',combo='Small')
    original={'bounded_retrieval':floor,'specialist':dict(mode='floor',combo='Large')}
    cases=[]
    for changed in (None,baseline,lower):
        routing=copy.deepcopy(original)
        if changed is None:del routing['bounded_retrieval']
        else:routing['bounded_retrieval']=changed
        cases.extend([(routing,None,False),(routing,routing,True)])
    unrelated={**original,'bounded_retrieval':baseline,'specialist':dict(mode='baseline',combo='Large')}
    cases.extend([(original,None,True),
                  ({**original,'bounded_retrieval':lower},{**original,'bounded_retrieval':baseline},False),
                  (unrelated,{**original,'bounded_retrieval':baseline},False),
                  ({**original,'bounded_retrieval':baseline},original,False)])
    for legacy in (False,True):
        for approved,proposed,allowed in cases:
            with tempfile.TemporaryDirectory(prefix='crews-floor-') as folder,isolated_home(folder):
                auto.install(folder);auto.ensure(folder,folder)
                policy=copy.deepcopy(governance.DEFAULTS)
                policy.update(lease_seconds=3600,max_reviews=20,routing=copy.deepcopy(original))
                ref=auto.next_review(folder,folder)
                review(ref,folder,dict(decision='approve',policy=policy,reason='seed explicit floors'))
                assert auto.next_review(folder,folder) is None
                with auto.database(folder) as db:
                    grant=db.execute('SELECT * FROM automation_grants').fetchone()
                    gid=grant['id'];limits=json.loads(grant['request'])
                    if legacy:
                        limits['routing']={need:entry['combo'] for need,entry in original.items()}
                        auto._save_grant(db,gid,limits)
                    prior=copy.deepcopy(limits['routing'])
                    if proposed is None:db.execute('UPDATE automation_grants SET used=20 WHERE id=?',(gid,))
                if proposed is not None:
                    packet=auto.dispatch(dict(operation='export',kind='policy'),folder,folder)
                    packet['proposal']['routing']=copy.deepcopy(proposed)
                    rejects(lambda:auto.dispatch(dict(operation='import',packet=packet,confirmed=False),folder,folder))
                    queued=auto.dispatch(dict(operation='import',packet=packet,confirmed=True),folder,folder)
                    assert queued['applied'] is False
                ref=auto.next_review(folder,folder)
                assert ref and ref.get('role')=='approve-automation',ref
                with auto.database(folder) as db:
                    job=db.execute('SELECT id,request FROM automation_jobs WHERE run=?',(ref['run'],)).fetchone()
                    job_id=job['id'];frozen=json.loads(job['request'])
                    if proposed is not None:
                        assert frozen['external_proposal']['routing']==proposed
                        assert job_id==queued['job_id']
                review(ref,folder,dict(decision='approve',policy={**policy,'routing':approved},reason='review frozen floor transition'))
                result=auto.finish(job_id,folder,folder)
                assert result['state']==('applied' if allowed else 'blocked'),(legacy,approved,proposed,result)
                with auto.database(folder) as db:
                    current=json.loads(db.execute('SELECT request FROM automation_grants WHERE id=?',(gid,)).fetchone()[0])
                assert current['routing']==(approved if allowed else prior)
                assert current['epoch']==(2 if allowed else 1)
                if not allowed:
                    assert 'exact frozen operator proposal' in result['result']
                    assert current['paused'] is True
    print('PASS: explicit/legacy floor removal, baseline and lowering refused; exact frozen imports allowed; mismatched/unrelated migrations refused; unchanged floors retained')


def run():
    with tempfile.TemporaryDirectory(prefix='crews-keyless-') as folder,isolated_home(folder):
        assert auto.dispatch({'operation':'status'},folder,folder)['enabled'] is False
        installed=auto.install(folder)
        assert not (Path(folder)/'operator-public.pem').exists()
        assert not any('private' in p.name for p in Path(folder).iterdir())
        auto.ensure(folder,folder)
        status=auto.dispatch({'operation':'status'},folder,folder)
        gid=status['grants'][0]['id']
        ref=auto.next_review(folder,folder)
        assert ref and ref['role']=='approve-automation',ref
        with a.database(folder) as db:plan=a.load_run(db,ref['run'],folder,ref['session'])
        cell=plan['waves'][0]['calls'][0]
        assert cell.get('automation_governance') and cell['policy_combo']=='Large' and not cell['write_scope'] and not cell['commands']
        from crews import governance
        policy=copy.deepcopy(governance.DEFAULTS)
        policy.update(lease_seconds=3600,max_reviews=20,audit_every=3,routing={'bounded_retrieval':{'mode':'floor','combo':'Medium'}})
        decision=dict(decision='approve',policy=policy,reason='fixture evidence supports conservative local policy')
        review(ref,folder,decision)
        assert auto.next_review(folder,folder) is None
        assert auto.routing_policy(folder,folder)=={'bounded_retrieval':{'mode':'floor','combo':'Medium'}}
        assert auto.audit_interval(folder,folder)==3
        from check_effort_policy import task_answers
        role=dict(name='lookup',kind='research',mission='Read existing project policy',deliverable='facts',scope=[],commands=[],acceptance=['Report existing project policy'],answers=dict(need='bounded_retrieval',difficulty=1,divisible=0,specific=1))
        ordinary=a.build_plan(dict(task='Read existing project policy',roles=[role]),task_answers('bounded_retrieval',1),folder,'ordinary-before-expiry',folder)
        ticket=a.dispatch(ordinary['run_id'],'lookup',folder,ordinary['session'],folder)
        with auto.database(folder) as db:
            row,limits=auto.live(db,gid,a.canonical(folder),folder)
            assert limits['epoch']==1 and row['used']==0
            limits['expires']=time.time()-1
            auto._save_grant(db,gid,limits)
        assert auto.routing_policy(folder,folder)=={}
        rejects(lambda:a.ticket(ticket['token'],folder,folder))
        fresh=a.build_plan(dict(task='Read existing project policy',roles=[role]),task_answers('bounded_retrieval',1),folder,'fresh-after-expiry',folder)
        rejects(lambda:a.dispatch(fresh['run_id'],'lookup',folder,fresh['session'],folder))
        rejects(lambda:a.build_plan(dict(task='Read existing project policy',roles=[{**role,'automation_governance':True}]),task_answers('bounded_retrieval',1),folder,'forged-governance',folder))
        renewed=auto.next_review(folder,folder)
        assert renewed and renewed['run']!=ref['run']
        # Old expired governance job is blocked; a distinct generation must resume.
        with a.database(folder) as db:db.execute('UPDATE runs SET created=? WHERE id=?',(time.time()-86401,renewed['run']))
        replacement=auto.next_review(folder,folder)
        assert replacement and replacement['run']!=renewed['run'],replacement
        renewed=replacement
        review(renewed,folder,decision)
        assert auto.next_review(folder,folder) is None
        assert auto.dispatch({'operation':'status'},folder,folder)['grants'][0]['id']==gid
        # A reserved last ordinary automatic review can admit even when used reaches quota.
        with auto.database(folder) as db:
            db.execute('UPDATE automation_grants SET used=20 WHERE id=?',(gid,))
            assert auto.live(db,gid,a.canonical(folder),folder,reserved=True)[0]['used']==20
            rejects(lambda:auto.live(db,gid,a.canonical(folder),folder))
            db.execute('UPDATE automation_grants SET used=0 WHERE id=?',(gid,))
        rejects(lambda:a.ticket(ticket['token'],folder,folder))
        from unittest.mock import patch
        original=a.remap_seat
        def changed_epoch(*args,**kwargs):
            selected=original(*args,**kwargs)
            with auto.database(folder) as db:
                current=json.loads(db.execute('SELECT request FROM automation_grants WHERE id=?',(gid,)).fetchone()[0]);current['epoch']+=1;auto._save_grant(db,gid,current)
            return selected
        with patch.object(a,'remap_seat',changed_epoch):
            rejects(lambda:a.build_plan(dict(task='Read existing project policy',roles=[role]),task_answers('bounded_retrieval',1),folder,'racing-policy',folder))
        pending=a.build_plan(dict(task='Read existing project policy',roles=[role]),task_answers('bounded_retrieval',1),folder,'before-disable',folder)
        with auto.database(folder) as db:db.execute('UPDATE automation_grants SET used=20 WHERE id=?',(gid,))
        quota=auto.next_review(folder,folder)
        assert quota
        review(quota,folder,dict(decision='deny',policy=None,reason='fixture aggregate regression'),status='COMPLETE')
        with a.database(folder) as db:db.execute('UPDATE runs SET created=? WHERE id=?',(time.time()-86401,quota['run']))
        fresh=a.build_plan(dict(task='Read existing project policy',roles=[role]),task_answers('bounded_retrieval',1),folder,'fresh-during-pause',folder)
        rejects(lambda:a.dispatch(fresh['run_id'],'lookup',folder,fresh['session'],folder))
        assert 'blocked' in auto.next_review(folder,folder)
        assert auto.next_review(folder,folder) is None,'denied governance retried without new evidence'
        auto.dispatch({'operation':'enable','confirmed':True},folder,folder)
        retry=auto.next_review(folder,folder)
        assert retry
        malformed=dict(decision='approve',policy={**policy,'write_scope':['anywhere']},reason='invalid expansion')
        review(retry,folder,malformed)
        with a.database(folder) as db:db.execute('UPDATE runs SET created=? WHERE id=?',(time.time()-86401,retry['run']))
        assert 'blocked' in auto.next_review(folder,folder)
        auto.dispatch({'operation':'disable','confirmed':True},folder,folder)
        rejects(lambda:a.dispatch(pending['run_id'],'lookup',folder,pending['session'],folder))
        auto.install(folder);auto.ensure(folder,folder)
        assert not auto.dispatch({'operation':'status'},folder,folder)['enabled']
        assert auto.next_review(folder,folder) is None
        rejects(lambda:auto.dispatch({'operation':'enable','confirmed':True,'policy':policy},folder,folder))
        auto.install(folder,enabled=False)
        auto.install(folder)
        assert not governance.installation(folder)['enabled']
        # New machine/state installation needs no old key and cannot import authority.
        with tempfile.TemporaryDirectory(prefix='crews-keyless-other-') as other:
            import shutil
            shutil.copyfile(Path(folder)/'automation-local.json',Path(other)/'automation-local.json')
            rejects(lambda:governance.installation(other))
        assert not (Path(folder)/'operator-public.pem').exists()
    print('PASS: keyless install, typed Large policy, lease/quota renewal, denial pause, malformed authority refusal, sticky disable and copied-state rejection')


if __name__=='__main__':
    run()
    floor_transitions()
