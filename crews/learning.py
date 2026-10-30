"""Exact, user-labelled learning; private safety evidence persists only as markers."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from crews.classification import ClassificationFacts, answer_errors, metadata, safety_errors, refuse

MAX_OBSERVATIONS = 10000
AUDIT_EVERY = 10
CHEAP = {'bounded_retrieval', 'repeatable_task', 'mechanical_verification'}
SOURCES = {'teacher', 'declared', 'deterministic', 'learned'}
OUTCOMES = {'ok', 'completed', 'COMPLETED', 'provider_error', 'timeout', 'failed', 'cancelled', 'unknown'}
_EXCLUDED = {'name', 'deliverable', 'session', 'session_id', 'task_id', 'id', 'answers', 'classification', 'declared_answers', 'classification_evidence'}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, project TEXT NOT NULL, signature TEXT NOT NULL, policy TEXT NOT NULL,
 safe_role TEXT NOT NULL, proposal TEXT, metrics TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS obs_family ON observations(project,signature,policy);
CREATE TABLE IF NOT EXISTS labels (
 observation_id TEXT PRIMARY KEY REFERENCES observations(id) ON DELETE CASCADE,
 project TEXT NOT NULL, signature TEXT NOT NULL, policy TEXT NOT NULL, unit TEXT NOT NULL,
 split TEXT NOT NULL, need TEXT NOT NULL, difficulty REAL NOT NULL, evidence TEXT NOT NULL,
 source TEXT NOT NULL CHECK(source='user'), created REAL NOT NULL,
 UNIQUE(project,signature,policy,unit));
CREATE TABLE IF NOT EXISTS rules (
 id TEXT PRIMARY KEY, project TEXT NOT NULL, signature TEXT NOT NULL, policy TEXT NOT NULL,
 safe_role TEXT NOT NULL, answers TEXT NOT NULL, state TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 0,
 audit_pending INTEGER NOT NULL DEFAULT 0, audits INTEGER NOT NULL DEFAULT 0,
 disagreements INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL,
 UNIQUE(project,signature,policy));
"""


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ': nonempty string required')
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(name + ': finite nonnegative number required')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _normalize(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if value is None or type(value) in (bool, int, float):
        return value
    raise ValueError('fingerprint: JSON values required')


def _root():
    return Path(os.environ.get('CREWS_OMP_HOME', str(Path.home() / '.crews-omp'))).expanduser()


def _key(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'learning.key'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(os.urandom(32))
    # Another process may have created the key but not finished its tiny write yet.
    for _ in range(100):
        key = path.read_bytes()
        if len(key) == 32:
            return key
        time.sleep(0.01)
    raise ValueError('invalid local learning key; learning disabled')


def _digest(key, domain, value):
    return hmac.new(key, (domain + '\0' + _json(value)).encode(), hashlib.sha256).hexdigest()


def _safe_role(role):
    if not isinstance(role, dict):
        raise ValueError('role: object required')
    if role.get('kind') not in ('produce', 'check', 'integrate', 'research'):
        raise ValueError('kind: valid role kind required')
    classification = role.get('classification', False)
    if type(classification) is not bool:
        raise ValueError('classification: boolean required')
    base = role.get('answers') if role.get('answers') is not None else {}
    full = {**role, 'answers': base}
    # Validate all input, including declared answers and authority, before stripping.
    refuse(answer_errors(full, require_complete=False) + safety_errors(full))
    facts = ClassificationFacts.model_validate({} if role.get('facts') is None else role['facts']).model_dump()
    details = metadata(role)
    return {'kind': role['kind'], 'facts': facts, 'classification': classification,
            'answers': {k: base[k] for k in ('divisible', 'specific') if k in base},
            'risk': details.risk.model_dump() if details.risk is not None else None,
            'capability_reason_present': details.capability_reason is not None,
            'prior_attempt_present': details.prior_attempt is not None,
            'scope_write_present': bool(role.get('scope'))}


def _proposal(safe, proposal, learning_safe=True):
    if not isinstance(proposal, dict) or set(proposal) != {'need', 'difficulty'}:
        raise ValueError('proposal: exactly need and difficulty required')
    effective = {**safe, 'answers': {**safe['answers'], **proposal}}
    # Presence markers feed only the safety validator, never execution authority.
    if safe.get('capability_reason_present'):
        effective['capability_reason'] = 'present'
    if safe.get('prior_attempt_present'):
        effective['prior_attempt'] = {'run': 'present', 'role': 'present'}
    if safe.get('scope_write_present'):
        effective['scope'] = ['present']
    refuse(answer_errors(effective) + safety_errors(effective))
    if learning_safe and proposal['need'] in CHEAP and any(safe['facts'][k] is not False for k in
                                                          ('unknown_cause', 'consequential_judgment', 'behavior_undecided')):
        raise ValueError('cheap proposal requires explicit negative risk facts')
    return {'need': proposal['need'], 'difficulty': proposal['difficulty']}


def _identity(key, project, role, context_fingerprint, policy_version):
    project = _text(project, 'project')
    context = _text(context_fingerprint, 'context_fingerprint')
    policy = _text(policy_version, 'policy_version')
    safe = _safe_role(role)
    brief = {k: v for k, v in role.items() if k not in _EXCLUDED}
    declared = {k: role.get('answers', {}).get(k) for k in ('need', 'difficulty') if role.get('answers', {}).get(k) is not None}
    signature = _digest(key, 'family', {'brief': _normalize(brief), 'declared': declared, 'context': context})
    return _digest(key, 'project', os.path.normcase(str(Path(project).resolve()))), signature, _digest(key, 'policy', policy), safe


def _metrics(metrics, *, task_only=False):
    if metrics is None:
        return {}
    if not isinstance(metrics, dict):
        raise ValueError('metrics: object required')
    if task_only and metrics.keys() - {'task_latency_ms', 'task_input_tokens', 'task_output_tokens'}:
        raise ValueError('outcome metrics: only task resource metrics may be updated')
    clean = {}
    for key in ('source', 'outcome'):
        if key in metrics:
            if metrics[key] not in (SOURCES if key == 'source' else OUTCOMES):
                raise ValueError(key + ': invalid value')
            clean[key] = metrics[key]
    for key in ('cache_hit', 'teacher_avoided', 'teacher_requested', 'shadow_sampled'):
        if key in metrics:
            if type(metrics[key]) is not bool:
                raise ValueError(key + ': boolean required')
            clean[key] = metrics[key]
    for key in ('latency_ms', 'task_latency_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'task_input_tokens', 'task_output_tokens'):
        if key in metrics:
            clean[key] = None if metrics[key] is None else _number(metrics[key], key)
    return clean


def _connect(root):
    db = sqlite3.connect(root / 'learning.sqlite', timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=30000')
    db.execute('PRAGMA max_page_count=8192')
    db.executescript(_SCHEMA)
    db.execute('BEGIN IMMEDIATE')
    return db


def _mode(db, project):
    row = db.execute('SELECT value FROM config WHERE key=?', ('mode:' + project,)).fetchone()
    return row[0] if row else 'shadow'


def _observation(db, project, oid):
    row = db.execute('SELECT * FROM observations WHERE id=? AND project=?', (_text(oid, 'observation_id'), project)).fetchone()
    if not row:
        raise ValueError('observation not found in project')
    return row


def _rule(db, project, rid):
    row = db.execute('SELECT * FROM rules WHERE id=? AND project=?', (_text(rid, 'rule_id'), project)).fetchone()
    if not row:
        raise ValueError('rule not found in project')
    return row


def _derive(db, obs):
    family = (obs['project'], obs['signature'], obs['policy'])
    labels = db.execute('SELECT * FROM labels WHERE project=? AND signature=? AND policy=?', family).fetchall()
    answers = {'need': labels[0]['need'], 'difficulty': labels[0]['difficulty']}
    conflict = any((r['need'], r['difficulty']) != (answers['need'], answers['difficulty']) for r in labels)
    train = sum(r['split'] == 'train' for r in labels)
    holdout = sum(r['split'] == 'holdout' for r in labels)
    row = db.execute('SELECT * FROM rules WHERE project=? AND signature=? AND policy=?', family).fetchone()
    if not row and train < 3 and not conflict:
        return {'rule_id': None, 'state': 'collecting', 'train_units': train, 'holdout_units': holdout, 'conflict': False}
    state = 'suspended' if conflict else ('shadow_ready' if train >= 3 and holdout >= 2 else 'candidate')
    if row:
        # Neither more examples nor replay can reactivate a suspended/rolled-back rule.
        if row['state'] in ('suspended', 'rolled_back') or (row['state'] == 'active' and not conflict):
            state = row['state']
        db.execute('UPDATE rules SET state=?,answers=? WHERE id=?', (state, _json(answers), row['id']))
        rid = row['id']
    else:
        rid = uuid.uuid4().hex
        db.execute('INSERT INTO rules(id,project,signature,policy,safe_role,answers,state,created) VALUES(?,?,?,?,?,?,?,?)',
                   (rid, *family, obs['safe_role'], _json(answers), state, time.time()))
    return {'rule_id': rid, 'state': state, 'train_units': train, 'holdout_units': holdout, 'conflict': conflict}


def _receipt(db, ph, project, row):
    """Validate stored execution evidence, never self-reported completion alone."""
    from crews.omp_adapter import scope_path, validate_model
    if row['status'] != 'completed':
        raise ValueError('feedback requires completed receipt')
    plan = json.loads(row['plan'])
    found = [(w, c) for w in plan['waves'] for c in w['calls'] if c['role_id'] == row['role']]
    if len(found) != 1:
        raise ValueError('feedback role missing or ambiguous')
    wave, cell = found[0]
    if cell.get('policy_combo') != 'Small':
        raise ValueError('feedback requires Small Combo receipt')
    validate_model(cell, Path(db.execute('PRAGMA database_list').fetchone()[2]).parent)
    result = json.loads(row['result'] or '{}')
    native, wire = result.get('native') or {}, result.get('wire') or {}
    evidence = result.get('verification')
    if (result.get('host_authenticated') is not True or result.get('status') != 'COMPLETE' or result.get('failure_kind') or
            type(native.get('exitCode')) is not int or native['exitCode'] != 0 or
            native.get('error') or native.get('aborted') or
            not isinstance(evidence, list) or not evidence or
            any(not isinstance(v, str) or not v.strip() for v in evidence)):
        raise ValueError('feedback requires valid native exit 0 and verified completion')
    from crews.outcomes import model_proof, fingerprints as current_fingerprints
    if not model_proof(cell, result):
        raise ValueError('feedback model/effort receipt mismatch')
    fingerprints = result.get('fingerprints')
    scopes = set(cell.get('write_scope', []) + cell.get('read_scope', []))
    if not isinstance(fingerprints, dict) or set(fingerprints) != scopes:
        raise ValueError('feedback missing scope fingerprints')
    if current_fingerprints(project, list(fingerprints)) != fingerprints:
        raise ValueError('feedback evidence stale')
    oid = cell.get('classification', {}).get('learning', {}).get('observation_id')
    obs = _observation(db, ph, oid)
    if json.loads(obs['metrics']).get('source') not in SOURCES - {'learned'}:
        raise ValueError('feedback requires original nonlearned observation')
    safe = json.loads(obs['safe_role'])
    answers = cell.get('role_answers', {})
    if (safe['kind'] != wave['kind'] or safe['facts'] != ClassificationFacts.model_validate(cell.get('facts', {})).model_dump() or
            safe['answers'] != {k: answers[k] for k in ('divisible', 'specific') if k in answers}):
        raise ValueError('feedback observation provenance mismatch')
    observed_risk=safe.get('risk')
    current_risk=metadata(cell).risk
    if observed_risk != (current_risk.model_dump() if current_risk is not None else None):
        raise ValueError('feedback risk provenance mismatch')
    _proposal(safe, {k: answers.get(k) for k in ('need', 'difficulty')})
    declared = cell.get('declared_role_answers', answers)
    return {'observation_id': oid, 'run': row['run'], 'role': row['role'], 'session': row['session'],
            'declared_need': declared.get('need'), 'declared_difficulty': declared.get('difficulty')}


def _feedback_receipts(db, ph, project, p, options=False):
    from crews.omp_adapter import canonical
    project = canonical(project)
    target = Path(db.execute('PRAGMA database_list').fetchone()[2]).parent / 'runs.sqlite'
    if not target.is_file():
        if options:
            return []
        raise ValueError('feedback run not found in project')
    runs = sqlite3.connect(target.resolve().as_uri() + '?mode=ro', uri=True)
    runs.row_factory = sqlite3.Row
    try:
        query = ('SELECT r.id run,r.session,r.plan,c.role,c.status,c.result FROM runs r '
                 'JOIN calls c ON c.run=r.id WHERE r.project=?')
        params = [project]
        if not options:
            query += ' AND r.id=? AND c.role=? AND r.session=?'
            params += [_text(p.get(k), k) for k in ('run', 'role', 'session')]
        query += ' ORDER BY r.created DESC,r.id DESC,c.role'
        rows = runs.execute(query, params)
        if not options:
            row = rows.fetchone()
            if row is None:
                raise ValueError('feedback run/project/role/session mismatch')
            return _receipt(db, ph, project, row)
        limit = p.get('limit', 100)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('limit: integer from 1 to 1000 required')
        eligible = []
        for row in rows:
            try:
                receipt = _receipt(db, ph, project, row)
            except (ValueError, TypeError, KeyError, OSError):
                continue
            if db.execute('SELECT 1 FROM labels WHERE observation_id=?', (receipt['observation_id'],)).fetchone():
                continue
            eligible.append(receipt)
            if len(eligible) == limit:
                break
        return eligible
    finally:
        runs.close()


def _summary(db, project):
    observations = db.execute('SELECT metrics FROM observations WHERE project=?', (project,)).fetchall()
    metrics = [json.loads(r['metrics']) for r in observations]
    resource = {}
    for key in ('latency_ms', 'task_latency_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'task_input_tokens', 'task_output_tokens'):
        known = [m[key] for m in metrics if m.get(key) is not None]
        resource[key] = {'total': sum(known), 'known': len(known), 'unknown': len(metrics) - len(known)}
    labels = db.execute('SELECT l.need,l.difficulty,l.split,o.proposal FROM labels l JOIN observations o ON o.id=l.observation_id WHERE l.project=?', (project,)).fetchall()
    scored = [r for r in labels if r['proposal'] is not None]
    correct = sum(json.loads(r['proposal']) == {'need': r['need'], 'difficulty': r['difficulty']} for r in scored)
    by_source, by_outcome, by_source_outcome = {}, {}, {}
    for m in metrics:
        source, outcome = m.get('source', 'unknown'), m.get('outcome', 'pending')
        by_source[source] = by_source.get(source, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        bucket = by_source_outcome.setdefault(source, {})
        bucket[outcome] = bucket.get(outcome, 0) + 1
    return {'mode': _mode(db, project), 'observations': len(metrics), 'labels': len(labels),
            'by_source': by_source, 'by_outcome': by_outcome, 'by_source_outcome': by_source_outcome,
            'pending_outcomes': by_outcome.get('pending', 0), 'unknown_outcomes': by_outcome.get('unknown', 0),
            'teacher_requests': sum(m.get('teacher_requested', m.get('source') == 'teacher') is True for m in metrics),
            'teacher_cache_hits': sum(m.get('source') == 'teacher' and m.get('cache_hit') is True for m in metrics),
            'shadow_samples': sum(m.get('shadow_sampled') is True for m in metrics),
            'label_accuracy': {'correct': correct, 'scored': len(scored), 'unknown': len(labels) - len(scored),
                               'accuracy': correct / len(scored) if scored else None},
            'teacher_calls_observed': sum(m.get('source') == 'teacher' and m.get('teacher_requested', True) and not m.get('cache_hit', False) for m in metrics),
            'teacher_calls_avoided': sum(m.get('source') == 'learned' and m.get('teacher_avoided') is True for m in metrics),
            'errors': sum(m.get('outcome') in ('provider_error', 'timeout', 'failed', 'cancelled') for m in metrics),
            'resource_coverage': resource, 'audit_every': AUDIT_EVERY, 'max_observations': MAX_OBSERVATIONS,
            'states': {r['state']: r['n'] for r in db.execute('SELECT state,count(*) n FROM rules WHERE project=? GROUP BY state', (project,))}}


def validate_delivery(cell, project, state=None, *, check_writes=True):
    """Recheck frozen learned context and revocable rule authority before use."""
    classification = cell.get('classification') or {}
    if classification.get('outcome') != 'learned':
        return
    from crews.outcomes import fingerprints
    expected = cell.get('input_fingerprints')
    if not isinstance(expected, dict):
        raise ValueError('learned classification context missing; create a fresh plan')
    if not check_writes:
        expected = cell.get('immutable_input_fingerprints')
        if not isinstance(expected, dict):
            raise ValueError('learned immutable context missing; create a fresh plan')
    actual = fingerprints(project, list(expected), exclude=cell.get('write_scope', []) if not check_writes else ())
    if actual != expected:
        raise ValueError('learned classification context stale; create a fresh plan')
    rid = (classification.get('learning') or {}).get('rule_id')
    root = Path(state) if state is not None else _root()
    project = os.path.normcase(str(Path(project).resolve()))
    key = _key(root)
    ph = _digest(key, 'project', project)
    from contextlib import closing
    with closing(sqlite3.connect((root / 'learning.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        row = _rule(db, ph, rid)
        if row['state'] != 'active' or _mode(db, ph) != 'on' or row['audit_pending']:
            raise ValueError('learned classification authority inactive or pending audit')
        proposal = {k: cell['role_answers'][k] for k in ('need', 'difficulty')}
        if json.loads(row['answers']) != proposal:
            raise ValueError('learned classification answers changed')


def dispatch(request, project=None, state=None):
    """Bridge API. Only label is ground truth; caller confirms human mutations."""
    if not isinstance(request, dict):
        raise ValueError('learning request: object required')
    op = request.get('operation', request.get('op'))
    if op not in {'observe', 'lookup', 'label', 'activate', 'rollback', 'audit', 'outcome', 'status',
                  'report', 'rules', 'observations', 'configure', 'purge', 'feedback', 'feedback_options'}:
        raise ValueError('learning operation: invalid name')
    project = str(Path(_text(project if project is not None else request.get('project'), 'project')).resolve())
    root = Path(state) if state is not None else _root()
    key = _key(root)
    project_hash = _digest(key, 'project', os.path.normcase(project))
    db = _connect(root)
    try:
        result = _dispatch(db, key, project, project_hash, op, request)
        db.commit()
        return {'ok': True, **result}
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _dispatch(db, key, project, ph, op, p):
    if op == 'feedback_options':
        return {'feedback_options': _feedback_receipts(db, ph, project, p, options=True)}
    if op == 'feedback':
        if 'verified_small' in p and p['verified_small'] is not True:
            raise ValueError('verified_small: true required when supplied')
        receipt = _feedback_receipts(db, ph, project, p)
        result = _dispatch(db, key, project, ph, 'label', {**p, 'observation_id': receipt['observation_id']})
        return {**receipt, **result}
    if op == 'configure':
        mode = p.get('mode')
        if mode == 'enabled':
            mode = 'on'
        if mode not in ('off', 'shadow', 'on'):
            raise ValueError('mode: off, shadow or on required')
        db.execute('INSERT OR REPLACE INTO config(key,value) VALUES(?,?)', ('mode:' + ph, mode))
        return {'mode': mode}
    if op in ('status', 'report'):
        return _summary(db, ph)
    if op == 'purge':
        count = db.execute('SELECT count(*) FROM observations WHERE project=?', (ph,)).fetchone()[0]
        db.execute('DELETE FROM rules WHERE project=?', (ph,))
        db.execute('DELETE FROM observations WHERE project=?', (ph,))
        db.execute('DELETE FROM config WHERE key=?', ('mode:' + ph,))
        return {'purged': count}
    if op in ('rules', 'observations'):
        limit = p.get('limit', 100)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('limit: integer from 1 to 1000 required')
        if op == 'rules':
            rows = db.execute('SELECT id rule_id,signature,policy,state,answers,hits,audit_pending,audits,disagreements FROM rules WHERE project=? ORDER BY created DESC LIMIT ?', (ph, limit))
        else:
            rows = db.execute('SELECT id observation_id,signature,policy,proposal,metrics,created FROM observations WHERE project=? ORDER BY created DESC LIMIT ?', (ph, limit))
        values = [dict(r) for r in rows]
        for r in values:
            for field in ('answers', 'proposal', 'metrics'):
                if r.get(field) is not None:
                    r[field] = json.loads(r[field])
        return {op: values}
    if op in ('observe', 'lookup'):
        ph, signature, policy, safe = _identity(key, project, p.get('role'), p.get('context_fingerprint'), p.get('policy_version'))
        if op == 'observe':
            if _mode(db, ph) == 'off':
                return {'observation_id': None, 'signature': signature, 'mode': 'off'}
            if db.execute('SELECT count(*) FROM observations WHERE project=?', (ph,)).fetchone()[0] >= MAX_OBSERVATIONS:
                return {'observation_id': None, 'signature': signature, 'dropped': True, 'reason': 'capacity'}
            proposal = p.get('proposal')
            if proposal is not None:
                proposal = _proposal(safe, proposal, learning_safe=False)
            oid = uuid.uuid4().hex
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)',
                       (oid, ph, signature, policy, _json(safe), _json(proposal) if proposal else None, _json(_metrics(p.get('metrics'))), time.time()))
            return {'observation_id': oid, 'signature': signature}
        row = db.execute('SELECT * FROM rules WHERE project=? AND signature=? AND policy=?', (ph, signature, policy)).fetchone()
        result = {'match': False, 'answers': None, 'rule_id': None, 'candidate_id': row['id'] if row else None, 'audit_due': False, 'mode': _mode(db, ph)}
        if row:
            result['state'] = row['state']
            if row['state'] in ('active', 'shadow_ready') and _mode(db, ph) != 'off':
                answers = _proposal(safe, json.loads(row['answers']))
                result['answers'] = answers
                result['rule_id'] = row['id']
                if row['state'] == 'active' and _mode(db, ph) == 'on':
                    hits = row['hits'] + 1
                    due = bool(row['audit_pending']) or hits % AUDIT_EVERY == 0
                    db.execute('UPDATE rules SET hits=?,audit_pending=? WHERE id=?', (hits, int(due), row['id']))
                    result.update(match=True, rule_id=row['id'], audit_due=due)
        return result
    if op == 'label':
        obs = _observation(db, ph, p.get('observation_id'))
        if json.loads(obs['metrics']).get('source') == 'learned':
            raise ValueError('learned decisions cannot label themselves; independent teacher/user observation required')
        _text(p.get('evidence'), 'evidence')
        unit = _digest(key, 'unit', _text(p.get('unit_id'), 'unit_id'))
        if p.get('split') not in ('train', 'holdout'):
            raise ValueError('split: train or holdout required')
        if p.get('source', 'user') != 'user':
            raise ValueError('label source: user required')
        answers = _proposal(json.loads(obs['safe_role']), {'need': p.get('need'), 'difficulty': p.get('difficulty')})
        prior = db.execute('SELECT * FROM labels WHERE project=? AND signature=? AND unit=?', (ph, obs['signature'], unit)).fetchone()
        if prior:
            if prior['split'] != p['split']:
                raise ValueError('independent unit cannot cross train/holdout split')
            if (prior['need'], prior['difficulty']) != (answers['need'], answers['difficulty']):
                # Commit suspension even though no duplicate label is admitted.
                db.execute("UPDATE rules SET state='suspended' WHERE project=? AND signature=? AND policy=?", (ph, obs['signature'], obs['policy']))
                return {'accepted': False, 'conflict': True, 'state': 'suspended'}
            if prior['policy'] != obs['policy']:
                return {'accepted': False, 'duplicate': True, 'rule_id': None, 'state': 'collecting'}
            return {'accepted': False, 'duplicate': True, **_derive(db, obs)}
        if db.execute('SELECT 1 FROM labels WHERE observation_id=?', (obs['id'],)).fetchone():
            raise ValueError('observation already labelled; independent observation required')
        db.execute('INSERT INTO labels VALUES(?,?,?,?,?,?,?,?,?,?,?)', (obs['id'], ph, obs['signature'], obs['policy'], unit,
                   p['split'], answers['need'], answers['difficulty'], _digest(key, 'evidence', p['evidence']), 'user', time.time()))
        return {'accepted': True, **_derive(db, obs)}
    if op == 'outcome':
        obs = _observation(db, ph, p.get('observation_id'))
        outcome = p.get('outcome')
        if outcome not in OUTCOMES:
            raise ValueError('outcome: invalid value')
        metrics = json.loads(obs['metrics'])
        metrics.update(_metrics(p.get('metrics'), task_only=True))
        metrics['outcome'] = outcome
        db.execute('UPDATE observations SET metrics=? WHERE id=?', (_json(metrics), obs['id']))
        return {'observation_id': obs['id'], 'outcome': outcome, 'label_created': False}
    row = _rule(db, ph, p.get('rule_id'))
    if op == 'rollback':
        db.execute("UPDATE rules SET state='rolled_back',audit_pending=0 WHERE id=?", (row['id'],))
        return {'rule_id': row['id'], 'state': 'rolled_back'}
    if op == 'activate':
        if row['state'] != 'shadow_ready':
            raise ValueError('activation requires consistent 3 train and 2 independent holdout units')
        _proposal(json.loads(row['safe_role']), json.loads(row['answers']))
        db.execute("UPDATE rules SET state='active',hits=0,audit_pending=0 WHERE id=?", (row['id'],))
        return {'rule_id': row['id'], 'state': 'active'}
    if op == 'audit':
        if row['state'] not in ('active', 'shadow_ready'):
            raise ValueError('audit requires active or shadow-ready rule')
        outcome = p.get('outcome', 'ok')
        if outcome not in OUTCOMES:
            raise ValueError('outcome: invalid value')
        agrees = False
        if outcome in ('ok', 'completed', 'COMPLETED'):
            try:
                agrees = _proposal(json.loads(row['safe_role']), p.get('proposal')) == json.loads(row['answers'])
            except (ValueError, TypeError):
                agrees = False
        state = row['state'] if agrees else 'suspended'
        db.execute('UPDATE rules SET state=?,audit_pending=0,audits=audits+1,disagreements=disagreements+? WHERE id=?',
                   (state, int(not agrees and outcome in ('ok', 'completed', 'COMPLETED')), row['id']))
        return {'rule_id': row['id'], 'state': state, 'agrees': agrees}
    raise ValueError('unsupported learning operation')


def learning(args, project=None):
    return dispatch(args, project)


def observe(project, role, context_fingerprint, policy_version, proposal=None, metrics=None):
    return dispatch(dict(operation='observe', role=role, context_fingerprint=context_fingerprint,
                         policy_version=policy_version, proposal=proposal, metrics=metrics), project)


def lookup(project, role, context_fingerprint, policy_version):
    return dispatch(dict(operation='lookup', role=role, context_fingerprint=context_fingerprint,
                         policy_version=policy_version), project)


def label(project, observation_id, need, difficulty, evidence, split, unit_id):
    return dispatch(dict(operation='label', observation_id=observation_id, need=need, difficulty=difficulty,
                         evidence=evidence, split=split, unit_id=unit_id), project)


def activate(project, rule_id):
    return dispatch(dict(operation='activate', rule_id=rule_id), project)


def rollback(project, rule_id):
    return dispatch(dict(operation='rollback', rule_id=rule_id), project)


def status(project):
    return dispatch(dict(operation='status'), project)


def rules(project):
    return dispatch(dict(operation='rules'), project)


def report(project):
    return dispatch(dict(operation='report'), project)
