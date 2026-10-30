"""Non-authoritative opportunity funnel. Medium proof never becomes Small evidence."""
import json
import time
from crews import outcomes

SCHEMA = '''CREATE TABLE IF NOT EXISTS capability_opportunities(
 id TEXT PRIMARY KEY,project TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,
 body TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS capability_blockers(project TEXT NOT NULL,reason TEXT NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(project,reason));'''


def blocked(project, reason, state=None):
    from crews.automation import database
    with database(state) as db:
        db.executescript(SCHEMA)
        db.execute('INSERT INTO capability_blockers VALUES(?,?,1) ON CONFLICT(project,reason) DO UPDATE SET count=count+1', (project, reason))


def discover(run, producer, checker, project, state=None):
    from crews.omp_adapter import database as runs, home, canonical
    from crews.automation import database
    project = canonical(project)
    proof = outcomes.verified_pair(run, producer, checker, project, state)
    if not proof['verified'] or proof['learned'] or proof.get('combo') not in ('Medium', 'Small'):
        blocked(project, 'not_independent_success', state)
        return dict(discovered=False, label_created=False)
    with runs(state or home()) as db:
        plan = json.loads(db.execute('SELECT plan FROM runs WHERE id=?', (run,)).fetchone()[0])
    role = next(r for r in plan['automation_context'] if r['name'] == producer)
    features = role.get('recipe_features')
    exclusions = []
    if not features: exclusions.append('semantic_family_review_required')
    if not proof.get('model_revision'): exclusions.append('unknown_revision')
    kind = 'medium_baseline_evidence' if proof['combo'] == 'Medium' else 'small_competence_evidence'
    body = dict(reference=proof['reference'], source_group=proof['source_group'], unit_hash=proof['unit_hash'],
                acceptance_hash=proof['execution']['acceptance_hash'], before_hash=proof['execution']['before_hash'],
                profile_hash=proof['profile_hash'], model_binding=proof['model_binding'],
                model_revision=proof.get('model_revision'), features=features, exclusions=exclusions,
                artifact_contract=outcomes.digest(sorted(proof['artifacts'])), label_created=False)
    body['producer_contract'] = outcomes.digest({k:role.get(k) for k in ('facts','scope','acceptance','answers','risk')})
    body['review'] = None
    oid = outcomes.digest(dict(project=project, reference=proof['reference']))
    with database(state) as db:
        db.executescript(SCHEMA)
        changed = db.execute('INSERT OR IGNORE INTO capability_opportunities VALUES(?,?,?,?,?,?)',
                             (oid, project, kind, 'review_required', json.dumps(body), time.time())).rowcount
    return dict(discovered=bool(changed), opportunity_id=oid, kind=kind, exclusions=exclusions, label_created=False)


def report(project, state=None):
    from pathlib import Path
    from contextlib import closing
    import sqlite3
    from crews.omp_adapter import home, canonical
    project = canonical(project); target = Path(state or home()) / 'learning.sqlite'
    result = dict(opportunities=[], blockers={}, labels_created=0, authority=False)
    if not target.is_file(): return result
    with closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='capability_opportunities'").fetchone():
            result['opportunities'] = [dict(id=r[0], kind=r[1], state=r[2], **json.loads(r[3])) for r in db.execute('SELECT id,kind,state,body FROM capability_opportunities WHERE project=?', (project,))]
            result['blockers'] = dict(db.execute('SELECT reason,count FROM capability_blockers WHERE project=?', (project,)))
    return result


def dispatch(request, project, state):
    from crews import approval, recipes, omp_adapter as a
    from crews.automation import database
    project=a.canonical(project)
    if not isinstance(request,dict) or request.get('version')!=1:
        raise ValueError('opportunity version 1 required')
    if request.get('operation')=='report':return report(project,state)
    if set(request)!={'version','operation','opportunity_id','features','version_strategy','approval','confirmed'} or request['operation']!='review' or request['confirmed'] is not True:
        raise ValueError('signed opportunity review required')
    nonce=approval.authorize(request,project,state)
    features=recipes._features(request['features'])
    strategy=request['version_strategy']
    if not isinstance(strategy,dict) or set(strategy)!={'kind','identity','expires','policy_binding'} or strategy['kind'] not in ('provider_revision','operator_deployment') or not isinstance(strategy['identity'],str) or not strategy['identity'].strip() or type(strategy['expires']) not in (int,float) or not time.time()<strategy['expires']<=time.time()+90*86400 or strategy['policy_binding']!=a.policy_binding(state):
        raise ValueError('reviewed finite version strategy required')
    with database(state) as db:
        db.executescript(SCHEMA);db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body,state FROM capability_opportunities WHERE id=? AND project=?',(request['opportunity_id'],project)).fetchone()
        if not row or row['state']!='review_required':raise ValueError('opportunity missing or already reviewed')
        body=json.loads(row['body'])
        outcomes.verified_reference(body['reference'],project,state)
        body['features']=features
        from crews.capability_trials import deployment_digest
        body['review']=dict(version_strategy=strategy,policy_binding=a.policy_binding(state),deployment_digest=deployment_digest(state))
        approval.consume(db,nonce)
        db.execute("UPDATE capability_opportunities SET body=?,state='reviewed' WHERE id=?",(json.dumps(body),request['opportunity_id']))
    return dict(reviewed=True,opportunity_id=request['opportunity_id'],authority=False,label_created=False)
