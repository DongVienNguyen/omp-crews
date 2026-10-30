"""Signed isolated trials use existing workflow admission, never a second executor."""
import json
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import closing
from crews import outcomes, approval

FRONTIER = 'everyday-cross-node-1.5-v1'
SCHEMA = '''CREATE TABLE IF NOT EXISTS capability_trials(
 id TEXT PRIMARY KEY,project TEXT NOT NULL,snapshot TEXT NOT NULL UNIQUE,session TEXT NOT NULL,
 opportunity TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL,
 UNIQUE(project,session));
CREATE TABLE IF NOT EXISTS capability_trial_results(trial TEXT PRIMARY KEY,proof TEXT NOT NULL,created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS capability_trial_results_no_update BEFORE UPDATE ON capability_trial_results BEGIN SELECT RAISE(ABORT,'trial result immutable'); END;
CREATE TRIGGER IF NOT EXISTS capability_trial_results_no_delete BEFORE DELETE ON capability_trial_results BEGIN SELECT RAISE(ABORT,'trial result immutable'); END;'''


def deployment_digest(state=None):
    import os,hashlib
    from crews.omp_adapter import model_policy
    agent=Path(os.environ.get('CREWS_OMP_AGENT_DIR') or os.environ.get('PI_CODING_AGENT_DIR') or Path.home()/'.omp/agent')
    hashes={name:hashlib.sha256((agent/name).read_bytes()).hexdigest() if (agent/name).is_file() else None for name in ('config.yml','models.yml')}
    return outcomes.digest(dict(config=hashes,model_policy=model_policy(state)))


def validate_ticket(cell,project,state):
    from crews import omp_adapter as a,workflow,automation
    if not cell.get('workflow_id'):return
    with a.database(state) as db:
        manifest=workflow._manifest(db,cell['workflow_id'])
        if not manifest['slot'].startswith('trial-'):return
        row=db.execute('SELECT body,state,project FROM capability_trials WHERE id=?',(manifest['slot'][6:],)).fetchone()
        if not row or row[1]!='reserved':raise ValueError('trial ticket authority inactive')
        body=json.loads(row[0])
        automation.validate_snapshot(body['owner_policy']['local'],row[2],state)
        if time.time()>=body['expires'] or workflow._policy(row[2],state)!=body['owner_policy'] or workflow._policy(project,state)!=body['policy'] or body['opportunity']['review'].get('deployment_digest')!=deployment_digest(state):raise ValueError('trial ticket lease/policy/deployment drift')


def eligible(role, roles, project):
    from crews.omp_adapter import small_eligibility, BOUNDED_ROUTE
    blockers = small_eligibility(role, project, roles, True)['blockers']
    difficulty = (role.get('answers') or {}).get('difficulty')
    if type(difficulty) in (int, float) and 1 < difficulty <= 1.5:
        blockers = [b for b in blockers if b != 'difficulty_above_limit']
    else: blockers.append('frontier_difficulty')
    if role.get('commands'): blockers.append('frontier_writer_commands')
    for fact in BOUNDED_ROUTE['true_facts']:
        if (role.get('facts') or {}).get(fact) is not True: blockers.append('required_true:'+fact)
    if any(v is not False for v in (role.get('risk') or {}).values()): blockers.append('frontier_risk')
    return sorted(set(blockers))


def _schema(db): db.executescript(SCHEMA)


def route(role, project, state=None):
    from crews.omp_adapter import home, canonical
    target = Path(state or home()) / 'runs.sqlite'
    if not target.is_file(): return None
    with closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='capability_trials'").fetchone(): return None
        row = db.execute("SELECT id,body FROM capability_trials WHERE snapshot=? AND state='reserved'", (canonical(project),)).fetchone()
    if not row: return None
    body = json.loads(row[1]); expected = body['producer']
    if role.get('name') != expected['name']: return None
    # Public role normalizers may supply defaults; every frozen authority field remains exact.
    if any(role.get(k) != v for k, v in expected.items()): raise ValueError('trial role differs from frozen authority')
    if time.time() >= body['expires']: raise ValueError('trial consent expired')
    return dict(effective_small=True, trial_id=row[0], route='experimental_trial')


def guard(db, cell, project, state):
    if not cell.get('trial_id'):
        if cell.get('workflow_id'):
            from crews.workflow import _manifest
            manifest=_manifest(db,cell['workflow_id'])
            if manifest['slot'].startswith('trial-'):
                row=db.execute('SELECT body,state,project FROM capability_trials WHERE id=?',(manifest['slot'][6:],)).fetchone()
                if not row or row[1]!='reserved' or time.time()>=json.loads(row[0])['expires']:raise ValueError('trial checker authority inactive')
                body=json.loads(row[0])
                from crews.workflow import _policy
                if _policy(row[2],state)!=body['owner_policy'] or _policy(project,state)!=body['policy']:raise ValueError('trial checker owner policy drift')
                from crews.automation import validate_snapshot
                validate_snapshot(body['owner_policy']['local'],row[2],state)
                if body['opportunity']['review'].get('deployment_digest')!=deployment_digest(state):raise ValueError('trial checker deployment drift')
                if manifest['spec']!=body['spec']:raise ValueError('trial checker signed workflow drift')
        return
    row = db.execute('SELECT snapshot,body,state FROM capability_trials WHERE id=?', (cell['trial_id'],)).fetchone()
    if not row or row[0] != project or row[2] != 'reserved': raise ValueError('trial authority inactive')
    body = json.loads(row[1])
    from crews.workflow import _policy
    if time.time() >= body['expires'] or _policy(project,state) != body['policy']: raise ValueError('trial consent/policy drift')
    owner=db.execute('SELECT project FROM capability_trials WHERE id=?',(cell['trial_id'],)).fetchone()[0]
    if _policy(owner,state)!=body['owner_policy']:raise ValueError('trial owner policy drift')
    from crews.automation import validate_snapshot
    validate_snapshot(body['owner_policy']['local'],owner,state)
    if body['opportunity']['review'].get('deployment_digest')!=deployment_digest(state):raise ValueError('trial deployment drift')
    if cell.get('workflow_id'):
        from crews.workflow import _manifest
        manifest=_manifest(db,cell['workflow_id'])
        if manifest['slot']!='trial-'+cell['trial_id'] or manifest['spec']!=body['spec']:raise ValueError('trial workflow differs from signed authority')
    else:raise ValueError('trial requires frozen workflow admission')
    if db.execute('SELECT 1 FROM execution_attempts WHERE project=? AND role=?',(project,cell['role_id'])).fetchone():raise ValueError('trial snapshot attempt already consumed')
    if db.execute('SELECT 1 FROM execution_attempts WHERE run=? AND role=?', (cell['trial_run'], cell['role_id'])).fetchone(): raise ValueError('trial retry forbidden; attempt cap consumed')
    if cell['policy_combo'] != 'Small': raise ValueError('trial requires frozen Small binding')


def dispatch(request, project, state):
    from crews import omp_adapter as a, workflow, opportunities
    project = a.canonical(project); state = Path(state or a.home())
    op = request.get('operation')
    if request.get('version') != 1: raise ValueError('capability trial version 1 required')
    if op == 'status':
        with a.database(state) as db:
            _schema(db)
            return dict(version=1, trials=[dict(id=r[0], state=r[1], snapshot=r[2]) for r in db.execute('SELECT id,state,snapshot FROM capability_trials WHERE project=?', (project,))])
    if op == 'prepare':
        fields={'version','operation','opportunity_id','snapshot','session','workflow','expires','frontier','approval','confirmed'}
        if set(request)!=fields or request['confirmed'] is not True or request['frontier']!=FRONTIER: raise ValueError('strict signed frontier trial request required')
        nonce=approval.authorize(request,project,state)
        snapshot=a.canonical(request['snapshot'])
        if snapshot==project or not Path(snapshot).is_relative_to(Path(project)): raise ValueError('trial requires isolated child snapshot')
        if type(request['expires']) not in (int,float) or not time.time()<request['expires']<=time.time()+3600: raise ValueError('trial finite lease required')
        opportunity=next((r for r in opportunities.report(project,state)['opportunities'] if r['id']==request['opportunity_id']),None)
        if not opportunity or opportunity['state']!='reviewed' or not opportunity.get('review'): raise ValueError('reviewed opportunity missing')
        outcomes.verified_reference(opportunity['reference'],project,state)
        spec,counts,acceptance,checks=workflow._validate(request['workflow'],snapshot)
        roles=[r for n in spec['nodes'] for r in n['roles']]
        if len(roles)!=2 or len(spec['nodes'])!=2 or sum(counts.values())!=2 or spec['max_calls']!=2: raise ValueError('trial requires exactly producer plus later independent checker; no retry')
        producers=[r for r in roles if r['kind']=='produce'];checkers=[r for r in roles if r['kind']=='check']
        if len(producers)!=1 or len(checkers)!=1: raise ValueError('trial producer/checker required')
        producer=producers[0];checker=checkers[0]
        original=opportunity['producer_contract']
        if outcomes.digest({k:producer.get(k) for k in ('facts','scope','acceptance','answers','risk')})!=original:
            raise ValueError('trial original producer contract changed')
        strategy=opportunity['review']['version_strategy']
        if strategy['policy_binding']!=a.policy_binding(state) or time.time()>=strategy['expires'] or producer.get('model_revision')!=strategy['identity'] or opportunity['review'].get('deployment_digest')!=deployment_digest(state):
            raise ValueError('trial reviewed version strategy drift')
        blockers=eligible(producer,roles,snapshot)
        if blockers: raise ValueError('trial frontier: '+', '.join(blockers))
        profile=outcomes.profile(checker,snapshot,roles)
        if outcomes.digest(profile)!=opportunity['profile_hash'] or outcomes.digest(producer.get('acceptance',[]))!=opportunity['acceptance_hash']: raise ValueError('trial original checker/acceptance changed')
        before=outcomes.digest(dict(acceptance=producer.get('acceptance',[]),before=outcomes.fingerprints(snapshot,list(dict.fromkeys(producer.get('inputs',[])+producer['scope'])))))
        if before!=opportunity['before_hash']: raise ValueError('trial must restore original starting artifacts')
        decision=a.routing_decision(producer,state,snapshot,roles)
        # Signed trial is separate from baseline, but never overrides an explicit floor.
        from crews.automation import routing_policy
        from crews.automation import validate_snapshot,policy_snapshot
        validate_snapshot(policy_snapshot(project,state),project,state)
        entry=routing_policy(project,state).get('everyday_implementation')
        if isinstance(entry,str) and entry!='Small' or isinstance(entry,dict) and entry.get('mode')=='floor' and entry.get('combo')!='Small': raise ValueError('trial explicit project floor')
        if decision['blocked_by']: raise ValueError('trial routing floor')
        body=dict(producer=producer,policy=workflow._policy(snapshot,state),owner_policy=workflow._policy(project,state),expires=request['expires'],spec=spec,opportunity=opportunity,frontier=FRONTIER)
        tid=uuid.uuid4().hex
        with a.database(state) as db:
            _schema(db);db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM runs WHERE project=?',(snapshot,)).fetchone(): raise ValueError('trial snapshot already executed; never replay')
            if db.execute('SELECT count(*) FROM capability_trials WHERE project=? AND created>=?',(project,int(time.time()//86400)*86400)).fetchone()[0]>=2: raise ValueError('trial project day cap exhausted')
            if db.execute('SELECT 1 FROM capability_trials WHERE project=? AND session=?',(project,request['session'])).fetchone(): raise ValueError('trial session cap exhausted')
            approval.consume(db,nonce)
            db.execute('INSERT INTO capability_trials VALUES(?,?,?,?,?,?,?,?)',(tid,project,snapshot,request['session'],request['opportunity_id'],json.dumps(body),'reserved',time.time()))
        result=workflow.dispatch(dict(operation='prepare',workflow=spec,slot='trial-'+tid,session=request['session'],confirmed=True),snapshot,state)
        return dict(version=1,trial_id=tid,workflow=result)
    with a.database(state) as db:
        _schema(db)
        row=db.execute('SELECT snapshot,session,body,state FROM capability_trials WHERE id=? AND project=?',(request.get('trial_id'),project)).fetchone()
    if not row: raise ValueError('trial project/identity missing')
    snapshot,session,raw,status=row;body=json.loads(raw)
    if op=='next':
        if status!='reserved': raise ValueError('trial settled; replay forbidden')
        return workflow.dispatch(dict(operation='next',slot='trial-'+request['trial_id'],session=session,confirmed=True),snapshot,state)
    if op not in ('finish','cancel'): raise ValueError('trial operation invalid')
    if request.get('confirmed') is not True: raise ValueError('trial completion confirmation required')
    if status!='reserved': raise ValueError('trial already settled')
    proof=None
    if op=='finish':
        proof=outcomes.verified_reference(request.get('reference'),snapshot,state)
        with a.database(state) as db:
            manifest=workflow._manifest(db,proof['reference']['workflow'])
        if manifest['slot']!='trial-'+request['trial_id'] or proof['combo']!='Small' or proof['learned']: raise ValueError('trial proof identity mismatch')
    verdict=proof['behavior'] if proof else 'unknown'
    with a.database(state) as db:
        db.execute('BEGIN IMMEDIATE')
        changed=db.execute("UPDATE capability_trials SET state=? WHERE id=? AND state='reserved'",('passed' if proof and proof['verified'] else 'suspended',request['trial_id']))
        if changed.rowcount!=1: raise ValueError('trial concurrently consumed')
        db.execute('INSERT INTO capability_trial_results VALUES(?,?,?)',(request['trial_id'],json.dumps(dict(behavior=verdict,proof=proof)),time.time()))
    return dict(version=1,behavior=verdict,proof=proof,activated=False,label_created=False)
