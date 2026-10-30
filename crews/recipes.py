"""Project-local recipe learning, separate from exact user-labelled learning.

Public request schema: register accepts ``recipe`` with strict ``features``
(domain/language/operation/invariant/dependency_shape), version, cue, lesson,
evidence, negative_examples, applicability (feature predicates), exclusions
(list of feature predicates), profile {input, command}, recipe_steps,
max_difficulty and model_binding (authoritative model/policy SHA-256).
Evidence/audit accept recipe_id, run, producer, checker and split. Outcomes,
never caller scores or completion strings, supply proof. No commands run here.

match is read-only: approved_recipe is a proposal, not admission authority.
Explicit lookup with confirmed=True reserves an active hit before use. This
keeps preview/classification from mutating state or bypassing audit counters.
All persistent mutations, including hit reservation, require exact confirmation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shlex
import sqlite3
import time
import uuid
from contextlib import contextmanager
from threading import RLock

_EVIDENCE_LOCK=RLock()


@contextmanager
def evidence_lock(state=None):
    from crews.egress import _flock
    folder=Path(state) if state is not None else learning._root()
    folder.mkdir(parents=True,exist_ok=True)
    with _EVIDENCE_LOCK, (folder/'capability-evidence.lock').open('a+b') as handle:
        _flock(handle.fileno(),exclusive=True)
        try:yield
        finally:_flock(handle.fileno(),exclusive=False)

from crews import learning
from crews.omp_adapter import canonical, explicit_file, small_eligibility

FEATURES = {'domain', 'language', 'operation', 'invariant', 'dependency_shape'}
TRUE_FACTS = ('targets_fixed', 'behavior_fixed', 'scope_bounded')
FALSE_FACTS = ('behavior_undecided', 'unknown_cause', 'consequential_judgment',
               'cross_system', 'concurrency_sensitive')
AUDIT_EVERY = 10
_SCHEMA = """
CREATE TABLE IF NOT EXISTS recipe_v1_config(project TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recipe_v1_recipes(
 id TEXT PRIMARY KEY, project TEXT NOT NULL, family TEXT NOT NULL, version INTEGER NOT NULL,
 body TEXT NOT NULL, profile_hash TEXT NOT NULL, state TEXT NOT NULL,
 consent INTEGER NOT NULL, hits INTEGER NOT NULL DEFAULT 0,
 audit_pending INTEGER NOT NULL DEFAULT 0, audits INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL, UNIQUE(project,family,version));
CREATE TABLE IF NOT EXISTS recipe_v1_units(
 project TEXT NOT NULL, unit TEXT NOT NULL, split TEXT NOT NULL,
 PRIMARY KEY(project,unit));
CREATE TABLE IF NOT EXISTS recipe_v1_evidence(
 id TEXT PRIMARY KEY, recipe TEXT NOT NULL REFERENCES recipe_v1_recipes(id),
 unit TEXT NOT NULL, split TEXT NOT NULL, behavior TEXT NOT NULL,
 proof TEXT NOT NULL, source TEXT NOT NULL CHECK(source='independent_checker'),
 created REAL NOT NULL, UNIQUE(recipe,unit));
CREATE TABLE IF NOT EXISTS recipe_v1_events(
 id INTEGER PRIMARY KEY, recipe TEXT, project TEXT NOT NULL, operation TEXT NOT NULL,
 detail TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recipe_v1_probes(
 id TEXT PRIMARY KEY, recipe TEXT NOT NULL, project TEXT NOT NULL,
 result TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recipe_v1_captures(
 id INTEGER PRIMARY KEY,project TEXT NOT NULL,recipe TEXT NOT NULL,run TEXT NOT NULL,
 producer TEXT NOT NULL,checker TEXT NOT NULL,proof TEXT NOT NULL,created REAL NOT NULL,
 UNIQUE(project,recipe,run,producer,checker));
CREATE TABLE IF NOT EXISTS recipe_audit_deliveries(token TEXT PRIMARY KEY,recipe TEXT NOT NULL,project TEXT NOT NULL,snapshot TEXT NOT NULL,role_hash TEXT NOT NULL,state TEXT NOT NULL,run TEXT,role TEXT,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recipe_source_groups(project TEXT NOT NULL,source_group TEXT NOT NULL,unit TEXT NOT NULL,split TEXT NOT NULL,PRIMARY KEY(project,source_group));
INSERT OR IGNORE INTO recipe_source_groups SELECT r.project,coalesce(json_extract(e.proof,'$.source_group'),e.unit),e.unit,e.split FROM recipe_v1_evidence e JOIN recipe_v1_recipes r ON r.id=e.recipe;
"""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _text(value, name):
    return learning._text(value, name)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _features(value, partial=False):
    if not isinstance(value, dict) or not value or set(value) - FEATURES or (not partial and set(value) != FEATURES):
        raise ValueError('features: exact domain/language/operation/invariant/dependency_shape required')
    return {key: _text(item, 'features.' + key) for key, item in value.items()}


def _binding(value):
    # Opaque authoritative model/policy fingerprint; never infer from Combo name.
    value = _text(value, 'model_binding')
    if len(value) != 64 or any(char not in '0123456789abcdef' for char in value):
        raise ValueError('model_binding: pinned authoritative SHA-256 required')
    return value


def _profile(value, project):
    if not isinstance(value, dict) or set(value) != {'input', 'command'} or not explicit_file(value.get('input')):
        raise ValueError('profile: project-relative input and exact command required')
    command = _text(value.get('command'), 'profile.command')
    if any(char in command for char in ';|><`$&\n\r'):
        raise ValueError('profile: shell syntax forbidden')
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        raise ValueError('profile: invalid command') from error
    if not tokens:
        raise ValueError('profile: script command required')
    executable = Path(tokens[0]).name.lower().removesuffix('.exe')
    args = tokens[1:]
    while args and args[0] in ('-B', '-I', '-u'):
        args = args[1:]
    if executable not in ('python', 'python3', 'node', 'bun') or not args or args[0] != value['input']:
        raise ValueError('profile: native script command must name input')
    if any(token in ('-c', '-m', '-e', '--eval', '--import', '--require', '-r', '-l') or
           token.startswith(('--eval=', '--import=', '--require=')) for token in tokens):
        raise ValueError('profile: executable code flags forbidden')
    target = (Path(project) / value['input']).resolve()
    if not target.is_relative_to(Path(project)) or not target.is_file():
        raise ValueError('profile input must exist within project')
    return dict(value), hashlib.sha256(target.read_bytes()).hexdigest()


def _profile_hash(recipe, project):
    _, script_hash = _profile(recipe['profile'], project)
    checker = dict(recipe['_checker_profile'])
    checker['sha256'] = script_hash
    return _hash(checker)


def _recipe(value, project, state=None):
    required = {'features', 'version', 'cue', 'lesson', 'evidence', 'negative_examples',
                'applicability', 'exclusions', 'profile', 'recipe_steps', 'max_difficulty', 'model_binding'}
    optional = {'frontier','version_strategy'}
    if not isinstance(value, dict) or not required<=set(value) or set(value)-required-optional:
        raise ValueError('recipe: strict structured recipe fields required')
    result = dict(value)
    result['features'] = _features(value['features'])
    if type(value['version']) is not int or value['version'] < 1:
        raise ValueError('version: positive integer required')
    for name in ('cue', 'lesson'):
        _text(value[name], name)
    for name in ('evidence', 'negative_examples', 'recipe_steps'):
        if not isinstance(value[name], list) or not value[name]:
            raise ValueError(name + ': nonempty list required')
        for item in value[name]:
            _text(item, name)
    result['applicability'] = _features(value['applicability'], partial=True)
    if any(result['features'][key] != item for key, item in result['applicability'].items()):
        raise ValueError('applicability contradicts structured family')
    if not isinstance(value['exclusions'], list):
        raise ValueError('exclusions: list of feature predicates required')
    result['exclusions'] = [_features(item, partial=True) for item in value['exclusions']]
    difficulty = value['max_difficulty']
    if isinstance(difficulty, bool) or not isinstance(difficulty, (int, float)) or not math.isfinite(difficulty) or not 0 <= difficulty <= 1.5:
        raise ValueError('max_difficulty: finite number from 0 to 1.5 required')
    result['profile'], profile_hash = _profile(value['profile'], project)
    result['model_binding'] = _binding(value['model_binding'])
    if 'frontier' in value:
        from crews.capability_trials import FRONTIER
        if value['frontier']!=FRONTIER:raise ValueError('unsupported experimental frontier')
        strategy=value.get('version_strategy')
        if not isinstance(strategy,dict) or set(strategy)!={'kind','identity','expires','policy_binding'} or strategy['kind'] not in ('provider_revision','operator_deployment') or not isinstance(strategy['identity'],str) or not strategy['identity'].strip() or type(strategy['expires']) not in (int,float) or not time.time()<strategy['expires']<=time.time()+90*86400:raise ValueError('reviewed finite model version strategy required')
        from crews.omp_adapter import policy_binding
        if strategy['policy_binding']!=policy_binding(state):raise ValueError('version strategy model/config drift')
        from crews.capability_trials import deployment_digest
        result['_deployment_digest']=deployment_digest(state)
    elif 'version_strategy' in value:raise ValueError('version strategy requires explicit frontier')
    return result, profile_hash


def _config(db, project):
    row = db.execute('SELECT value FROM recipe_v1_config WHERE project=?', (project,)).fetchone()
    return json.loads(row[0]) if row else {'mode':'shadow','auto_promotion':None,'probe_budget':None,'auto_evidence':False}


def _delegation_live(db, project, state):
    grant_id = _config(db,project).get('delegation_id')
    if not grant_id:return True
    from crews.automation import effective
    return effective(db,grant_id,project,state)


def _row(db, project, rid):
    row = db.execute('SELECT * FROM recipe_v1_recipes WHERE project=? AND id=?',
                     (project, _text(rid, 'recipe_id'))).fetchone()
    if row is None:
        raise ValueError('recipe not found in project')
    return row


def _event(db, project, rid, operation, detail):
    db.execute('INSERT INTO recipe_v1_events(recipe,project,operation,detail,created) VALUES(?,?,?,?,?)',
               (rid, project, operation, _json(detail), time.time()))


def _state(db, row, state, reason):
    db.execute('UPDATE recipe_v1_recipes SET state=?,audit_pending=0 WHERE id=?', (state, row['id']))
    _event(db, row['project'], row['id'], state, {'reason': reason})


def _stats(db, row):
    rows = db.execute('SELECT split,behavior FROM recipe_v1_evidence WHERE recipe=?', (row['id'],)).fetchall()
    train = sum(r['split'] == 'train' and r['behavior'] == 'pass' for r in rows)
    holdout = sum(r['split'] == 'holdout' and r['behavior'] == 'pass' for r in rows)
    failures = sum(r['behavior'] == 'fail' for r in rows)
    failures += db.execute("SELECT count(*) FROM recipe_v1_events WHERE recipe=? AND operation='conflict'", (row['id'],)).fetchone()[0]
    failures += db.execute("SELECT count(*) FROM recipe_v1_events WHERE recipe=? AND operation='suspended' AND detail LIKE '%behavioral audit failed%'", (row['id'],)).fetchone()[0]
    failures += db.execute("SELECT count(*) FROM recipe_v1_events WHERE recipe=? AND operation='suspended' AND detail LIKE '%captured independent behavior failure%'", (row['id'],)).fetchone()[0]
    conflicts=db.execute("SELECT count(*) FROM (SELECT coalesce(json_extract(proof,'$.source_group'),unit) AS g FROM recipe_v1_evidence WHERE recipe=? GROUP BY g HAVING count(DISTINCT unit)>1 OR count(DISTINCT split)>1)",(row['id'],)).fetchone()[0]
    failures+=conflicts
    known = train + holdout + failures
    return {'train': train, 'holdout': holdout, 'failures': failures,
            'unknown': sum(r['behavior'] == 'unknown' for r in rows) + db.execute("SELECT count(*) FROM recipe_v1_events WHERE recipe=? AND operation='suspended' AND detail LIKE '%captured independent outcome unknown%'",(row['id'],)).fetchone()[0],
            'failure_bound': 1 - .05 ** (1 / known) if known and not failures else None}


def _proof(reference, project, state, recipe, profile_hash, audit=False):
    if not isinstance(reference, dict):
        raise ValueError('evidence reference: object required')
    from crews.outcomes import verified_pair, verified_reference
    evidence_project=canonical(reference.get('project',project))
    if not Path(evidence_project).resolve().is_relative_to(Path(project).resolve()):raise ValueError('evidence project must be caller project or isolated child snapshot')
    if reference.get('reference'):
        proof=verified_reference(reference['reference'],evidence_project,state)
        p=proof['reference']['producer'];c=proof['reference']['checker'];refs=[p['run'],p['role'],c]
    else:
        refs=[_text(reference.get('run'),'run'),_text(reference.get('producer'),'producer'),reference.get('checker')]
        if not isinstance(refs[2],(str,dict)):raise ValueError('checker reference required')
        proof=verified_pair(*refs,evidence_project,state)
    required = {'verified', 'behavior', 'unit_hash', 'artifacts', 'profile_hash', 'model_binding', 'execution'}
    if not isinstance(proof, dict) or not required <= set(proof) or type(proof['verified']) is not bool:
        raise ValueError('authoritative evidence missing proof fields')
    if proof['behavior'] not in ('pass', 'fail', 'unknown'):
        raise ValueError('authoritative behavior invalid')
    _text(proof['unit_hash'], 'unit_hash')
    _text(proof['profile_hash'], 'profile_hash')
    execution = proof['execution']
    if not isinstance(execution, (str, dict)) or not execution:
        raise ValueError('authoritative execution proof required')
    if (proof.get('learned') is not False and not audit) or proof.get('source') != 'independent_checker':
        raise ValueError('independent non-learned evidence proof required')
    if not audit and isinstance(execution, dict) and (execution.get('source') == 'learned' or execution.get('learned') is True or execution.get('recipe_id')):
        raise ValueError('learned evidence cannot self-train')
    if proof['behavior'] == 'pass' and (not proof['verified'] or not proof['artifacts']):
        raise ValueError('passing verdict requires verified artifact proof')
    if not isinstance(proof['artifacts'], (dict, list)):
        raise ValueError('authoritative artifacts required')
    _binding(proof['model_binding'])
    if proof.get('combo') is not None and proof['combo']!='Small':raise ValueError('Medium proof is opportunity only, never Small competence')
    if recipe.get('frontier'):
        strategy=recipe['version_strategy']
        if proof.get('model_revision')!=strategy['identity'] or time.time()>=strategy['expires']:raise ValueError('frontier model revision unknown or expired')
    proof={**proof,'run':refs[0],'producer':refs[1],'checker':refs[2]}
    # Drift is returned to caller so suspension commits, not rolled back by error.
    mismatch = proof['profile_hash'] != profile_hash or proof['model_binding'] != recipe['model_binding']
    return proof, mismatch


def _safe(role, roles, recipe, project):
    blockers = []
    facts = role.get('facts') or {}
    for name in TRUE_FACTS:
        if facts.get(name) is not True:
            blockers.append('required_true:' + name)
    for name in FALSE_FACTS:
        if facts.get(name) is not False:
            blockers.append('required_false:' + name)
    answers = role.get('answers') or {}
    if answers.get('need') != 'everyday_implementation':
        blockers.append('not_implementation')
    difficulty = answers.get('difficulty')
    if isinstance(difficulty, bool) or not isinstance(difficulty, (int, float)) or not 0 <= difficulty <= recipe['max_difficulty']:
        blockers.append('difficulty')
    # Existing route validator owns scope, independent checker and command rules.
    if recipe.get('frontier'):
        from crews.capability_trials import eligible
        blockers.extend(eligible(role,roles,project))
    else:
        checked = small_eligibility(role, project, roles, routine=True)
        blockers.extend(checked['blockers'])
    checker = next((item for item in roles or [] if item.get('name') == role.get('routine_check')), None)
    profile = recipe['profile']
    writers = [item for item in roles or [] if item.get('kind') in ('produce', 'integrate')]
    if role not in writers:
        writers.append(role)
    target = (Path(project) / profile['input']).resolve()
    for writer in writers:
        for scope in writer.get('scope') or []:
            path = (Path(project) / scope).resolve()
            if path == target or target.is_relative_to(path):
                blockers.append('profile_writable')
    if checker is None or profile['input'] not in (checker.get('inputs') or []) or profile['command'] not in (checker.get('commands') or []):
        blockers.append('profile_checker_mismatch')
    invariant = recipe['features']['invariant']
    if invariant not in (role.get('acceptance') or []) or checker is None or invariant not in (checker.get('criteria') or []):
        blockers.append('invariant_missing')
    return sorted(set(blockers))


def _lookup(db, project, p, state):
    role = p.get('role')
    if not isinstance(role, dict):
        raise ValueError('role: object required')
    features = _features(role.get('recipe_features'))
    config = _config(db, project)
    if not _delegation_live(db,project,state):
        return {'match':False,'effective_small':False,'mode':config['mode'],'reason':'delegation_inactive'}
    result = {'match': False, 'effective_small': False, 'mode': config['mode'], 'candidate': None,
              'approved_recipe': None, 'audit_due': False, 'reason': 'no_family'}
    if config['mode'] == 'off':
        result['reason'] = 'off'
        return result
    rows = db.execute('SELECT * FROM recipe_v1_recipes WHERE project=? AND family=? ORDER BY version DESC',
                      (project, _hash(features))).fetchall()
    if not rows:
        return result
    # Never fall back to older versions after drift/rollback of newest version.
    row = rows[0]
    recipe = json.loads(row['body'])
    if recipe.get('frontier'):
        strategy=recipe['version_strategy']
        from crews.omp_adapter import policy_binding
        from crews.capability_trials import deployment_digest
        if time.time()>=strategy['expires'] or strategy['policy_binding']!=policy_binding(state) or role.get('model_revision')!=strategy['identity'] or recipe.get('_deployment_digest')!=deployment_digest(state):
            if p.get('confirmed') is True:_state(db,row,'suspended','version strategy drift')
            result['reason']='version_strategy_drift'
            return result
    if time.time()>=recipe.get('_expires_at',0):
        if p.get('confirmed') is True:_state(db,row,'suspended','recipe validity expired')
        result['reason']='expired'
        return result
    if config.get('delegation_id'):
        from crews.automation import live
        _,limits=live(db,config['delegation_id'],project,state)
        if recipe.get('_delegation_id')!=config['delegation_id'] or recipe['max_difficulty']>limits['max_difficulty']:
            result['reason']='recipe_outside_current_delegation'
            return result
    result['candidate'] = {'recipe_id': row['id'], 'version': row['version'], 'state': row['state']}
    result['audit_due'] = bool(row['audit_pending'])
    try:
        profile, _ = _profile(recipe['profile'], project)
        current_hash = _profile_hash(recipe, project)
        binding = _binding(role.get('model_binding'))
    except (ValueError, OSError):
        result['reason'] = 'profile_or_binding_unknown'
        return result
    if current_hash != row['profile_hash'] or binding != recipe['model_binding'] or role.get('recipe_profile') != profile:
        if p.get('confirmed') is True:
            _state(db, row, 'suspended', 'profile/model drift')
        result['reason'] = 'profile_or_model_drift'
        return result
    if any(all(features[key] == value for key, value in exclusion.items()) for exclusion in recipe['exclusions']):
        result['reason'] = 'excluded'
        return result
    blockers = _safe(role, p.get('roles'), recipe, project)
    if blockers:
        result.update(reason='safety_revalidation', blockers=blockers)
        return result
    if config['mode'] != 'on':
        result['reason'] = 'shadow'
        return result
    if row['state'] != 'active':
        result['reason'] = row['state']
        return result
    result['approved_recipe'] = {'recipe_id': row['id'], **recipe, 'profile_hash': row['profile_hash']}
    if row['audit_pending']:
        pending=db.execute("SELECT state,created FROM recipe_audit_deliveries WHERE recipe=? AND state IN ('reserved','admitted') ORDER BY created DESC LIMIT 1",(row['id'],)).fetchone()
        if pending and time.time()-pending['created']>3600:
            if p.get('confirmed') is True:
                db.execute("UPDATE recipe_audit_deliveries SET state='expired' WHERE recipe=? AND state IN ('reserved','admitted')",(row['id'],))
                _state(db,row,'suspended','audit delivery expired')
            result['reason']='audit_delivery_expired'
        else:result['reason'] = 'fresh_behavioral_audit_required'
        return result
    if p.get('confirmed') is not True:
        result['reason'] = 'explicit_hit_reservation_required'
        return result
    hits = row['hits'] + 1
    from crews.automation import audit_interval
    due = hits % audit_interval(project,state) == 0
    token=None
    if due:
        if not row['consent']:
            result['reason']='audit_delivery_consent_required'
            return result
        from crews.outcomes import fingerprints
        token=uuid.uuid4().hex
        snapshot=fingerprints(project,list(dict.fromkeys((role.get('inputs') or [])+(role.get('scope') or [])+[recipe['profile']['input']])))
        db.execute('INSERT INTO recipe_audit_deliveries VALUES(?,?,?,?,?,?,?,?,?)',(token,row['id'],project,_json(snapshot),_hash(role),'reserved',None,None,time.time()))
    db.execute('UPDATE recipe_v1_recipes SET hits=?,audit_pending=? WHERE id=?', (hits, int(due), row['id']))
    _event(db, project, row['id'], 'audit_delivery' if due else 'hit', {'hits': hits, 'audit_due': due})
    result.update(match=True,effective_small=True,audit_due=due,audit_delivery_token=token,
                  reason='checked_audit_delivery' if due else 'approved')
    return result


def _policy(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'min_train', 'min_holdout', 'max_failure_bound'}:
        raise ValueError('auto_promotion: min_train/min_holdout/max_failure_bound required')
    if type(value['min_train']) is not int or value['min_train'] < 3 or type(value['min_holdout']) is not int or value['min_holdout'] < 5:
        raise ValueError('auto policy requires >=3 train and >=5 holdout')
    bound = value['max_failure_bound']
    if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not 0 < bound <= .05:
        raise ValueError('auto failure bound must be positive and <=5%')
    return value


def _budget(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'max_pairs', 'max_cost', 'max_latency_ms'}:
        raise ValueError('probe_budget: max_pairs/max_cost/max_latency_ms required')
    if type(value['max_pairs']) is not int or not 1 <= value['max_pairs'] <= 1000:
        raise ValueError('probe max_pairs: 1..1000 required')
    for key in ('max_cost', 'max_latency_ms'):
        if learning._number(value[key], key) <= 0:
            raise ValueError('probe budget must be positive')
    return value


def _auto_ready(db, row):
    stats = _stats(db, row)
    config = _config(db, row['project'])
    policy = config['auto_promotion']
    return bool(policy and row['state'] in ('candidate','shadow_ready') and row['consent'] and
                not stats['failures'] and not stats['unknown'] and stats['train'] >= policy['min_train'] and
                stats['holdout'] >= policy['min_holdout'] and stats['train'] + stats['holdout'] >= 59 and
                stats['failure_bound'] is not None and stats['failure_bound'] <= policy['max_failure_bound'])


def _activate(db, row, automatic=False):
    stats = _stats(db, row)
    if row['state'] not in ('candidate', 'shadow_ready', 'suspended', 'rolled_back'):
        raise ValueError('activation requires inactive recipe')
    if stats['train'] < 3 or stats['holdout'] < 2 or stats['failures'] or stats['unknown'] or not row['consent']:
        raise ValueError('activation requires consent, >=3 train, >=2 disjoint holdout and zero behavioral failures')
    if automatic:
        config = _config(db, row['project'])
        if config.get('delegation_id') or not _auto_ready(db,row):
            return False
    _state(db, row, 'active', 'approved auto policy' if automatic else 'explicit approval')
    return True


def _evidence(db, row, p, project, state, audit=False):
    if not row['consent']:
        raise ValueError('machine evidence requires explicit registered profile consent')
    recipe = json.loads(row['body'])
    proof, mismatch = _proof(p, project, state, recipe, row['profile_hash'], audit=audit)
    _check_holdout(project,proof,state)
    try:
        mismatch = mismatch or _profile_hash(recipe, project) != row['profile_hash']
    except (ValueError, OSError):
        mismatch = True
    if mismatch:
        _state(db, row, 'suspended', 'profile/model proof drift')
        return {'accepted': False, 'state': 'suspended', 'reason': 'proof_drift'}
    split = p.get('split')
    if split not in ('train', 'holdout'):
        raise ValueError('split: train or holdout required')
    unit = proof['unit_hash']
    group=proof.get('source_group',unit)
    grouped=db.execute('SELECT unit,split FROM recipe_source_groups WHERE project=? AND source_group=?',(project,group)).fetchone()
    if grouped and (grouped['split']!=split or grouped['unit']!=unit):raise ValueError('independent source group cannot cross train/holdout or count multiple units')
    prior_unit = db.execute('SELECT split FROM recipe_v1_units WHERE project=? AND unit=?', (project, unit)).fetchone()
    if prior_unit and prior_unit[0] != split:
        raise ValueError('independent unit cannot cross train/holdout split')
    prior = db.execute('SELECT * FROM recipe_v1_evidence WHERE recipe=? AND unit=?', (row['id'], unit)).fetchone()
    if prior:
        if prior['behavior'] != proof['behavior'] and 'unknown' not in (prior['behavior'], proof['behavior']):
            _state(db, row, 'suspended', 'conflicting independent behavioral evidence')
            _event(db, project, row['id'], 'conflict', proof)
            return {'accepted': False, 'conflict': True, 'state': 'suspended'}
        return {'accepted': False, 'duplicate': True, 'audit_cleared': False, **_stats(db, row)}
    if audit and (row['state'] != 'active' or not row['audit_pending']):
        raise ValueError('audit requires active recipe with pending audit')
    if audit:
        _complete_delivery(db,row,proof,project,state)
        db.execute('INSERT INTO recipe_v1_units VALUES(?,?,?)',(project,unit,'audit_only'))
        db.execute('INSERT OR IGNORE INTO recipe_source_groups VALUES(?,?,?,?)',(project,group,unit,'audit_only'))
        return {'accepted':True,'state':_row(db,project,row['id'])['state'],'audit_cleared':proof['verified'] and proof['behavior']=='pass',**_stats(db,row)}
    db.execute('INSERT OR IGNORE INTO recipe_v1_units VALUES(?,?,?)',(project,unit,split))
    db.execute('INSERT OR IGNORE INTO recipe_source_groups VALUES(?,?,?,?)',(project,group,unit,split))
    db.execute('INSERT INTO recipe_v1_evidence VALUES(?,?,?,?,?,?,?,?)',
               (uuid.uuid4().hex, row['id'], unit, split, proof['behavior'], _json(proof), 'independent_checker', time.time()))
    _event(db, project, row['id'], 'audit' if audit else 'evidence', {'unit': unit, 'behavior': proof['behavior']})
    if proof['behavior'] == 'fail':
        _state(db, row, 'suspended', 'verified behavioral failure')
    elif proof['behavior'] == 'pass':
        if audit:
            db.execute('UPDATE recipe_v1_recipes SET audit_pending=0,audits=audits+1 WHERE id=?', (row['id'],))
        stats = _stats(db, row)
        if row['state'] in ('candidate', 'shadow_ready') and stats['train'] >= 3 and stats['holdout'] >= 2 and not stats['failures']:
            db.execute("UPDATE recipe_v1_recipes SET state='shadow_ready' WHERE id=?", (row['id'],))
            fresh = _row(db, project, row['id'])
            _activate(db, fresh, automatic=True)
    return {'accepted': True, 'state': _row(db, project, row['id'])['state'],
            'audit_cleared': audit and proof['behavior'] == 'pass', **_stats(db, row)}


def _probe(db, row, p, project, state):
    if p.get('comparison')=='capability' or p.get('baseline_combo')=='Medium':raise ValueError('Medium-vs-Small unsupported by recipe probe; use capability_comparison version 1')
    budget = _config(db, project)['probe_budget']
    if not budget or not row['consent']:
        raise ValueError('probe requires explicit registered profile consent and approved budget')
    baseline, candidate = p.get('baseline'), p.get('candidate')
    if not isinstance(baseline, list) or not isinstance(candidate, list) or not baseline or len(baseline) != len(candidate) or len(baseline) > budget['max_pairs']:
        raise ValueError('probe requires paired evidence references within budget')
    recipe = json.loads(row['body'])
    sides = []
    reasons = []
    total_cost = total_latency = 0
    seen = set()
    for references in (baseline, candidate):
        units = {}
        for ref in references:
            proof, mismatch = _proof(ref, project, state, recipe, row['profile_hash'])
            unit = proof['unit_hash']
            if unit in units:
                raise ValueError('probe units must be independent and unique')
            prior = db.execute('SELECT 1 FROM recipe_v1_units WHERE project=? AND unit=?', (project, unit)).fetchone()
            if prior:
                raise ValueError('probe requires fresh holdout disjoint from learned evidence')
            units[unit] = proof
            seen.add(unit)
            execution = proof['execution'] if isinstance(proof['execution'], dict) else {}
            if execution.get('accounting_complete') is not True:reasons.append('accounting_unknown')
            if mismatch or proof['behavior'] == 'unknown' or (proof['behavior']=='pass' and not proof['verified']):
                reasons.append('ambiguous_or_drift')
            for key in ('cost', 'latency_ms'):
                value = execution.get(key)
                try:
                    learning._number(value, key)
                except ValueError:
                    reasons.append('accounting_unknown')
                    continue
                if key == 'cost':
                    total_cost += value
                else:
                    total_latency += value
        sides.append(units)
    if set(sides[0]) != set(sides[1]):
        raise ValueError('baseline and candidate must use same independent holdout units')
    if total_cost > budget['max_cost'] or total_latency > budget['max_latency_ms']:
        reasons.append('budget_exceeded')
    better = False
    for unit in sides[0]:
        left, right = sides[0][unit], sides[1][unit]
        left_execution = left['execution'] if isinstance(left['execution'], dict) else {}
        right_execution = right['execution'] if isinstance(right['execution'], dict) else {}
        if (not left_execution.get('before_hash') or left_execution.get('before_hash') != right_execution.get('before_hash') or
                left['profile_hash'] != right['profile_hash'] or left['model_binding'] != right['model_binding']):
            reasons.append('not_comparable')
        if left['behavior'] == 'pass' and right['behavior'] != 'pass':
            reasons.append('regression')
        if left['behavior'] != 'pass' and right['behavior'] == 'pass':
            better = True
    if not better:
        reasons.append('no_verified_improvement')
    result = {'selection': 'baseline' if reasons else 'candidate', 'reasons': sorted(set(reasons)),
              'pairs': len(baseline), 'cost': total_cost, 'latency_ms': total_latency,
              'lesson': 'Retain baseline on ambiguity or regression; probe evidence grants no routing authority.'}
    # Consumed holdout is never recycled into subsequent learning/probes.
    for unit in seen:
        db.execute('INSERT INTO recipe_v1_units VALUES(?,?,?)', (project, unit, 'probe_holdout'))
    pid = uuid.uuid4().hex
    db.execute('INSERT INTO recipe_v1_probes VALUES(?,?,?,?,?)', (pid, row['id'], project, _json(result), time.time()))
    _event(db, project, row['id'], 'probe', result)
    return {'probe_id': pid, **result}


def _dispatch(db, p, project, state):
    op = p.get('operation', p.get('op'))
    if op == 'lookup':
        return _lookup(db, project, p, state)
    if op in ('status', 'report'):
        rows = db.execute('SELECT * FROM recipe_v1_recipes WHERE project=? ORDER BY created,id', (project,)).fetchall()
        return {**_config(db, project), 'recipes': [dict(recipe_id=r['id'], state=r['state'], version=r['version'],
                hits=r['hits'], audit_pending=bool(r['audit_pending']), audits=r['audits'], **_stats(db, r)) for r in rows],
                'captures':db.execute('SELECT count(*) FROM recipe_v1_captures WHERE project=?',(project,)).fetchone()[0],
                'events': [dict(r) for r in db.execute('SELECT operation,recipe,detail,created FROM recipe_v1_events WHERE project=? ORDER BY id', (project,))]}
    if op == 'configure':
        current = _config(db, project)
        mode = p.get('mode', current['mode'])
        if mode not in ('off', 'shadow', 'on'):
            raise ValueError('mode: off/shadow/on required')
        config = {'mode': mode, 'auto_promotion': _policy(p.get('auto_promotion', current['auto_promotion'])),
                  'probe_budget': _budget(p.get('probe_budget', current['probe_budget']))}
        if type(p.get('auto_evidence',current.get('auto_evidence',False))) is not bool:raise ValueError('auto_evidence strict boolean required')
        config['auto_evidence']=p.get('auto_evidence',current.get('auto_evidence',False))
        db.execute('INSERT OR REPLACE INTO recipe_v1_config VALUES(?,?)', (project, _json(config)))
        _event(db, project, None, op, config)
        return config
    if op == 'register':
        recipe, profile_hash = _recipe(p.get('recipe'), project, state)
        # Registration also requires current complete writer/checker context.
        role = p.get('role')
        if not isinstance(role, dict):
            raise ValueError('registration requires current role and independent checker context')
        blockers = _safe(role, p.get('roles'), recipe, project)
        if blockers:
            raise ValueError('recipe registration: ' + ', '.join(blockers))
        from crews.outcomes import profile as checked_profile
        checker = next(item for item in p['roles'] if item.get('name') == role.get('routine_check'))
        pinned = checked_profile(checker, project, p['roles'])
        if not pinned or {key: pinned[key] for key in ('input', 'command')} != recipe['profile']:
            raise ValueError('registration requires authoritative checker_profile')
        recipe['_checker_profile'] = pinned
        validity=p.get('validity_seconds',30*86400)
        if type(validity) is not int or not 1<=validity<=90*86400:raise ValueError('recipe validity_seconds must be1..7776000')
        recipe['_expires_at']=time.time()+validity
        previous=db.execute('SELECT id FROM recipe_v1_recipes WHERE project=? AND family=? ORDER BY version DESC LIMIT 1',(project,_hash(recipe['features']))).fetchone()
        recipe['_rollback_target']=previous[0] if previous else None
        profile_hash = _hash(pinned)
        rid = uuid.uuid4().hex
        try:
            db.execute('INSERT INTO recipe_v1_recipes(id,project,family,version,body,profile_hash,state,consent,created) VALUES(?,?,?,?,?,?,?,?,?)',
                       (rid, project, _hash(recipe['features']), recipe['version'], _json(recipe), profile_hash, 'candidate',
                        int(p.get('machine_consent') is True), time.time()))
        except sqlite3.IntegrityError as error:
            raise ValueError('recipe family/version already registered; versions immutable') from error
        _event(db, project, rid, op, {'profile_hash': profile_hash, 'machine_consent': p.get('machine_consent') is True})
        return {'recipe_id': rid, 'state': 'candidate', 'profile_hash': profile_hash}
    row = _row(db, project, p.get('recipe_id'))
    if op in ('evidence', 'audit'):
        return _evidence(db, row, p, project, state, audit=op == 'audit')
    if op in ('suspend', 'rollback'):
        new_state = 'suspended' if op == 'suspend' else 'rolled_back'
        _state(db, row, new_state, _text(p.get('reason'), 'reason'))
        return {'recipe_id': row['id'], 'state': new_state}
    if op == 'activate':
        recipe = json.loads(row['body'])
        if _profile_hash(recipe, project) != row['profile_hash']:
            _state(db, row, 'suspended', 'profile drift at activation')
            return {'recipe_id': row['id'], 'state': 'suspended'}
        _activate(db, row)
        return {'recipe_id': row['id'], 'state': 'active'}
    if op == 'probe':
        return _probe(db, row, p, project, state)
    raise ValueError('recipe operation invalid')


def capture(run,producer,checker,project,state=None):
    with evidence_lock(state):return _capture(run,producer,checker,project,state)


def _capture(run,producer,checker,project,state=None):
    """Collect authoritative outcomes for consented profiles, not a training label."""
    from crews.outcomes import verified_pair
    root=Path(state) if state is not None else learning._root();target=root/'learning.sqlite'
    if not target.is_file():return {'captured':0}
    with __import__('contextlib').closing(sqlite3.connect(target)) as db:
        db.row_factory=sqlite3.Row
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='recipe_v1_recipes'").fetchone():return {'captured':0}
        proof=verified_pair(run,producer,checker,project,root)
        db.executescript(_SCHEMA);count=0
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute('SELECT * FROM recipe_v1_recipes WHERE project=? AND consent=1',(canonical(project),)).fetchall()
        _check_holdout(project,proof,root)
        for row in rows:
            body=json.loads(row['body'])
            if time.time()>=body.get('_expires_at',0):continue
            if proof['profile_hash']!=row['profile_hash'] or proof['model_binding']!=body['model_binding']:continue
            with db:
                if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
                row=_row(db,canonical(project),row['id'])
                identity=__import__('crews.outcomes',fromlist=['digest']).digest(proof.get('reference') or dict(run=run,producer=producer,checker=checker))
                changed=db.execute('INSERT OR IGNORE INTO recipe_v1_captures(project,recipe,run,producer,checker,proof,created) VALUES(?,?,?,?,?,?,?)',(canonical(project),row['id'],run,producer,identity,_json(proof),time.time()))
                count+=changed.rowcount
                if changed.rowcount and proof['learned'] and row['audit_pending']:
                    _complete_delivery(db,row,proof,canonical(project),root)
                config=_config(db,canonical(project))
                delegated_scope=True
                if config.get('delegation_id'):
                    from crews.automation import live
                    try:
                        _,limits=live(db,config['delegation_id'],canonical(project),root)
                        delegated_scope=body.get('_delegation_id')==config['delegation_id'] and body['max_difficulty']<=limits['max_difficulty']
                    except (ValueError,OSError):delegated_scope=False
                if config.get('auto_evidence') and delegated_scope and _delegation_live(db,canonical(project),root) and not row['audit_pending'] and proof['verified'] and not proof['learned'] and proof.get('combo','Small')=='Small' and (not body.get('frontier') or proof.get('model_revision')==body['version_strategy']['identity'] and time.time()<body['version_strategy']['expires']):
                    unit=proof['unit_hash'];split='holdout' if int(unit[:8],16)%5==0 else 'train'
                    prior=db.execute('SELECT split FROM recipe_v1_units WHERE project=? AND unit=?',(canonical(project),unit)).fetchone()
                    grouped=db.execute('SELECT unit,split FROM recipe_source_groups WHERE project=? AND source_group=?',(canonical(project),proof.get('source_group',unit))).fetchone()
                    existing=db.execute('SELECT 1 FROM recipe_v1_evidence WHERE recipe=? AND unit=?',(row['id'],unit)).fetchone()
                    if not existing and (not prior or prior[0]==split) and (not grouped or grouped['unit']==unit and grouped['split']==split):
                        db.execute('INSERT OR IGNORE INTO recipe_source_groups VALUES(?,?,?,?)',(canonical(project),proof.get('source_group',unit),unit,split))
                        db.execute('INSERT OR IGNORE INTO recipe_v1_units VALUES(?,?,?)',(canonical(project),unit,split))
                        db.execute('INSERT INTO recipe_v1_evidence VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,row['id'],unit,split,proof['behavior'],_json({**proof,'run':run,'producer':producer,'checker':checker}),'independent_checker',time.time()))
                        stats=_stats(db,row)
                        if row['state'] in ('candidate','shadow_ready') and stats['train']>=3 and stats['holdout']>=2 and not stats['failures']:
                            db.execute("UPDATE recipe_v1_recipes SET state='shadow_ready' WHERE id=?",(row['id'],))
                            _activate(db,_row(db,canonical(project),row['id']),automatic=True)
                if proof['behavior']=='fail':_state(db,row,'suspended','captured independent behavior failure')
                elif proof['behavior']=='unknown':_state(db,row,'suspended','captured independent outcome unknown')
        return {'captured':count,'label_created':False}

def dispatch(request, project, state=None):
    if isinstance(request,dict) and request.get('operation',request.get('op')) in ('evidence','audit','probe'):
        with evidence_lock(state):return _dispatch_request(request,project,state)
    return _dispatch_request(request,project,state)


def _dispatch_request(request, project, state=None):
    """Execute exactly one requested operation; no background capture or execution."""
    if not isinstance(request, dict):
        raise ValueError('recipe request: object required')
    op = request.get('operation', request.get('op'))
    read_only = op in ('lookup', 'status', 'report') and request.get('confirmed') is not True
    allowed = {'register', 'evidence', 'activate', 'suspend', 'rollback', 'audit', 'lookup', 'status', 'report', 'configure', 'probe'}
    if op not in allowed:
        raise ValueError('recipe operation invalid')
    if not read_only and request.get('confirmed') is not True:
        raise ValueError('recipe mutation requires confirmed is True')
    project = canonical(project)
    root = Path(state) if state is not None else learning._root()
    target = root / 'learning.sqlite'
    nonce=None
    if not read_only and op!='lookup':
        from crews.approval import authorize
        nonce=authorize(request,project,root)
    if read_only and not target.is_file():
        if op == 'lookup':
            return {'ok': True, 'match': False, 'effective_small': False, 'mode': 'shadow', 'candidate': None,
                    'approved_recipe': None, 'audit_due': False, 'reason': 'no_family'}
        return {'ok': True, 'mode': 'shadow', 'auto_promotion': None, 'probe_budget': None, 'recipes': [], 'events': []}
    if not read_only:
        root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target.resolve().as_uri() + ('?mode=ro' if read_only else '?mode=rwc'), uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        if not read_only:
            db.executescript(_SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            if nonce is not None:
                from crews.approval import consume
                consume(db,nonce)
        elif not db.execute("SELECT 1 FROM sqlite_master WHERE name='recipe_v1_recipes'").fetchone():
            if op == 'lookup':
                return {'ok': True, 'match': False, 'effective_small': False, 'mode': 'shadow', 'candidate': None,
                        'approved_recipe': None, 'audit_due': False, 'reason': 'no_family'}
            return {'ok': True, 'mode': 'shadow', 'recipes': [], 'events': []}
        result = _dispatch(db, request, project, root)
        if not read_only:
            db.commit()
        return {'ok': True, **result}
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def match(role, project, roles=None, state=None):
    """Read-only family proposal. Explicit confirmed lookup reserves effective use."""
    if not isinstance(role, dict) or role.get('recipe_features') is None:
        return {'match': False, 'effective_small': False, 'candidate': None, 'approved_recipe': None, 'reason': 'no_features'}
    return dispatch({'operation': 'lookup', 'role': role, 'roles': roles}, project, state)


def admit_delivery(cell,run,project,state):
    token=cell.get('audit_delivery_token')
    if not token:return
    from crews.automation import database
    from crews.outcomes import fingerprints
    with database(state) as db:
        row=db.execute('SELECT * FROM recipe_audit_deliveries WHERE token=? AND project=?',(token,project)).fetchone()
        if not row or row['state']!='reserved' or row['recipe']!=cell.get('recipe_id') or cell['policy_combo']!='Small':raise ValueError('audit delivery consumed or wrong binding')
        expected=json.loads(row['snapshot'])
        if fingerprints(project,list(expected))!=expected:raise ValueError('audit delivery snapshot stale')
        if time.time()-row['created']>3600:raise ValueError('audit delivery expired')
        db.execute("UPDATE recipe_audit_deliveries SET state='admitted',run=?,role=? WHERE token=? AND state='reserved'",(run,cell['role_id'],token))


def _complete_delivery(db,row,proof,project,state):
    reference=proof.get('reference',{}).get('producer',{})
    delivery=db.execute("SELECT token FROM recipe_audit_deliveries WHERE recipe=? AND project=? AND run=? AND role=? AND state='admitted'",(row['id'],project,reference.get('run'),reference.get('role'))).fetchone()
    if not delivery:raise ValueError('audit proof lacks admitted delivery token')
    db.execute("UPDATE recipe_audit_deliveries SET state='completed' WHERE token=? AND state='admitted'",(delivery[0],))
    if proof['verified'] and proof['behavior']=='pass':
        db.execute('UPDATE recipe_v1_recipes SET audit_pending=0,audits=audits+1 WHERE id=?',(row['id'],))
    else:_state(db,row,'suspended','audit delivery behavioral audit failed' if proof['behavior']=='fail' else 'audit delivery unknown')
    _event(db,project,row['id'],'audit_only',dict(reference=proof['reference'],behavior=proof['behavior']))


def failed_delivery(cell,project,state):
    token=cell.get('audit_delivery_token')
    if not token:return
    from crews.automation import database
    with database(state) as db:
        row=db.execute("SELECT recipe FROM recipe_audit_deliveries WHERE token=? AND project=? AND state='admitted'",(token,project)).fetchone()
        if not row:return
        db.execute("UPDATE recipe_audit_deliveries SET state='suspended' WHERE token=?",(token,))
        _state(db,_row(db,project,row['recipe']),'suspended','audit producer failed or cancelled')


def _check_holdout(project,proof,state):
    from contextlib import closing
    target=Path(state)/'runs.sqlite'
    if not target.is_file():return
    with closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='capability_holdouts'").fetchone():
            for owner, in db.execute('SELECT project FROM capability_holdouts WHERE source_group=?',(proof.get('source_group',proof['unit_hash']),)):
                left,right=Path(canonical(project)),Path(owner)
                if left==right or left.is_relative_to(right) or right.is_relative_to(left):raise ValueError('comparison holdout cannot train recipe competence')
        before=(proof.get('execution') or {}).get('before_hash')
        if before and db.execute("SELECT 1 FROM sqlite_master WHERE name='capability_content_holdouts'").fetchone():
            for owner, in db.execute('SELECT project FROM capability_content_holdouts WHERE before_hash=?',(before,)):
                left,right=Path(canonical(project)),Path(owner)
                if left==right or left.is_relative_to(right) or right.is_relative_to(left):raise ValueError('comparison content holdout cannot train recipe competence')


def failed_checker(cell,project,state):
    from crews import omp_adapter as a
    targets=[dict(run=cell.get('_run'),role=name) for name in cell.get('verify_targets') or []]+list(cell.get('workflow_targets') or [])
    with a.database(state) as runs:
        pairs=[]
        for target in targets:
            row=runs.execute('SELECT plan FROM runs WHERE id=? AND project=?',(target['run'],canonical(project))).fetchone()
            if not row:continue
            writer=next((c for w in json.loads(row[0])['waves'] for c in w['calls'] if c['role_id']==target['role']),None)
            if writer and writer.get('audit_delivery_token'):pairs.append((target,writer))
    from crews.automation import database
    with database(state) as db:
        for target,writer in pairs:
            row=db.execute("SELECT recipe FROM recipe_audit_deliveries WHERE token=? AND project=? AND run=? AND role=? AND state='admitted'",(writer['audit_delivery_token'],canonical(project),target['run'],target['role'])).fetchone()
            if row:
                db.execute("UPDATE recipe_audit_deliveries SET state='suspended' WHERE token=?",(writer['audit_delivery_token'],))
                _state(db,_row(db,canonical(project),row['recipe']),'suspended','audit delivery unknown: recorded checker failure')
