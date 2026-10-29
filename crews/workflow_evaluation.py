"""Frozen workflow evaluation. Caller rows never grant rollout authority.

Signed spec: evaluation_mode defaults to 'monetary'; 'quality_only' replaces
min_cost_reduction with no monetary gate. Other frozen fields stay required.
Quality-only latency spans host workflow creation through last immutable native
attempt timestamp, including orchestration, retries and independent checks.
Money remains unknown/not evaluated; quality-only GO never proves savings.
"""
import json
import math
import time
from pathlib import Path

from crews.approval import authorize, consume
from crews.outcomes import derive, digest, fingerprints, model_proof

COMPONENTS = {'main', 'governance', 'classifier', 'scout', 'architecture', 'producer', 'checker', 'repairs', 'context'}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def summarize(records, evaluation_mode='monetary'):
    if evaluation_mode not in ('monetary', 'quality_only'):
        raise ValueError('workflow evaluation mode invalid')
    if not isinstance(records, list):
        raise ValueError('workflow accounting records required')
    accepted = 0
    total = 0
    latencies, missing, seen, families = [], [], set(), {}
    latency_missing = []
    for item in records:
        required = {'id', 'family', 'accepted', 'behavior', 'false_complete', 'components', 'latency_ms', 'pricing_reference'}
        if not isinstance(item, dict) or set(item) != required or not isinstance(item['id'], str) or not item['id'] or item['id'] in seen:
            raise ValueError('unique strict workflow record required')
        if not isinstance(item['family'], str) or not item['family'].strip():
            raise ValueError('workflow family required')
        seen.add(item['id'])
        if type(item['accepted']) is not bool or type(item['false_complete']) is not bool or item['behavior'] not in ('pass', 'fail', 'unknown'):
            raise ValueError('workflow behavior invalid')
        if item['accepted'] and (item['behavior'] != 'pass' or item['false_complete']):
            raise ValueError('accepted workflow needs independent behavior and no false completion')
        accepted += item['accepted']
        family = families.setdefault(item['family'], dict(total=0, accepted=0, fail=0, unknown=0, false_complete=0))
        family['total'] += 1
        family['accepted'] += item['accepted']
        family['false_complete'] += item['false_complete']
        if item['behavior'] != 'pass':
            family[item['behavior']] += 1
        costs = item['components']
        complete = isinstance(costs, dict) and set(costs) == COMPONENTS and all(_number(v) for v in costs.values())
        complete = complete and isinstance(item['pricing_reference'], str) and bool(item['pricing_reference'].strip()) and _number(item['latency_ms'])
        if _number(item['latency_ms']):
            latencies.append(item['latency_ms'])
        else:
            latency_missing.append(item['id'])
        if evaluation_mode == 'quality_only':
            continue
        if not complete:
            missing.append(item['id'])
        else:
            total += math.fsum(costs.values())
    full = bool(records) and not missing and evaluation_mode == 'monetary'
    latency_full = bool(records) and not latency_missing
    return dict(tasks=len(records), accepted=accepted, families=families,
                missing=latency_missing if evaluation_mode == 'quality_only' else missing, accounting_complete=full,
                total_cost=total if full else None, cost_per_accepted=total / accepted if full and accepted else None,
                p95=sorted(latencies)[math.ceil(.95 * len(latencies)) - 1] if (latency_full if evaluation_mode == 'quality_only' else full) else None,
                latency_complete=latency_full, unknown_is_zero=False)


def latency_gate(left, right, spec):
    if not left.get('latency_complete') or not right.get('latency_complete'):
        return False
    if 'max_latency_ms' in spec:
        return _number(right.get('p95')) and right['p95'] <= spec['max_latency_ms']
    return (_number(left.get('p95')) and _number(right.get('p95'))
            and right['p95'] <= left['p95'] * min(1.2, spec['max_latency_ratio']))


def compare(baseline, candidate, evaluation_mode='monetary'):
    """Untrusted arithmetic preview. Only dispatch can issue authenticated GO."""
    left, right = summarize(baseline, evaluation_mode), summarize(candidate, evaluation_mode)
    paired = {r['id']: r for r in baseline}
    if set(paired) != {r['id'] for r in candidate} or any(r['family'] != paired[r['id']]['family'] for r in candidate):
        raise ValueError('paired workflow identities and families required')
    quality = bool(baseline) and right['accepted'] >= left['accepted'] and all(
        r['behavior'] != 'unknown' and paired[r['id']]['behavior'] != 'unknown' and not r['false_complete']
        and not paired[r['id']]['false_complete'] and not (paired[r['id']]['behavior'] == 'pass' and r['behavior'] != 'pass')
        and not (paired[r['id']]['accepted'] and not r['accepted']) for r in candidate)
    cost = left['cost_per_accepted'] is not None and right['cost_per_accepted'] is not None and right['cost_per_accepted'] <= left['cost_per_accepted'] * .85
    latency = left['p95'] is not None and right['p95'] is not None and right['p95'] <= left['p95'] * 1.2
    return dict(baseline=left, candidate=right, quality_gate=quality,
                cost_gate=cost if evaluation_mode == 'monetary' else None, latency_gate=latency,
                evaluation_mode=evaluation_mode, money_status='unknown' if evaluation_mode == 'monetary' else 'not_evaluated',
                rollout='NO_GO', authenticated=False, missing=['frozen corpus and authenticated workflow receipts required'])


def _schema(db):
    from crews.workflow import _schema as workflows_schema
    workflows_schema(db)
    db.execute('CREATE TABLE IF NOT EXISTS workflow_accounting(workflow TEXT PRIMARY KEY,request TEXT NOT NULL,attested REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS workflow_evaluations(id TEXT PRIMARY KEY,project TEXT NOT NULL,spec TEXT NOT NULL,created REAL NOT NULL,approval TEXT NOT NULL)')


def _freeze(request, project, state):
    """SDLC bindings have their own schema; generic evaluation stays strict."""
    from crews.omp_adapter import database
    nonce = authorize(request, project, state)
    spec = request.get('spec')
    mode = spec.get('evaluation_mode', 'monetary') if isinstance(spec, dict) else None
    if mode not in ('monetary', 'quality_only'):
        raise ValueError('workflow evaluation mode invalid')
    absolute = isinstance(spec, dict) and 'max_latency_ms' in spec
    if absolute and (mode != 'quality_only' or 'max_latency_ratio' in spec):
        raise ValueError('absolute latency requires quality_only and replaces ratio')
    latency_key = 'max_latency_ms' if absolute else 'max_latency_ratio'
    gates = {'noninferiority_margin', latency_key}
    if mode == 'monetary':
        gates.add('min_cost_reduction')
    fields = gates | {'units', 'arms'}
    if not isinstance(spec, dict) or set(spec) not in (fields, fields | {'evaluation_mode'}):
        raise ValueError('strict frozen workflow spec and arm bindings required')
    units = spec['units']
    if not isinstance(units, list) or not units:
        raise ValueError('workflow evaluation units required')
    seen, groups = set(), {}
    for unit in units:
        if not isinstance(unit, dict) or set(unit) != {'id', 'family', 'source_group', 'split', 'expected_abstain', 'before_hash', 'acceptance_hash'}:
            raise ValueError('strict frozen workflow unit required')
        if any(not isinstance(unit[k], str) or not unit[k].strip() for k in ('id', 'family', 'source_group', 'before_hash', 'acceptance_hash')) or unit['id'] in seen:
            raise ValueError('unique frozen workflow unit required')
        if unit['split'] not in ('train', 'holdout') or type(unit['expected_abstain']) is not bool:
            raise ValueError('workflow unit split/abstain invalid')
        if unit['source_group'] in groups and groups[unit['source_group']] != unit['split']:
            raise ValueError('workflow source family cannot cross split')
        seen.add(unit['id'])
        groups[unit['source_group']] = unit['split']
    valid_latency = _number(spec[latency_key]) and (spec['max_latency_ms'] > 0 if absolute else 1 <= spec['max_latency_ratio'] <= 2)
    if any(not _number(spec[k]) for k in gates) or not 0 <= spec['noninferiority_margin'] <= .1 or not valid_latency or (mode == 'monetary' and not 0 <= spec['min_cost_reduction'] < 1):
        raise ValueError('workflow evaluation gates outside conservative limits')
    arms = spec['arms']
    if not isinstance(arms, dict) or set(arms) != {'baseline', 'candidate'}:
        raise ValueError('paired workflow arm bindings required')
    for arm, profile in (('baseline', 'baseline'), ('candidate', 'sdlc_cost_aware')):
        binding = arms[arm]
        if not isinstance(binding, dict) or set(binding) != {'profile', 'model', 'policy', 'environment'} or binding['profile'] != profile:
            raise ValueError('workflow arm profile binding invalid')
        policy = binding['policy']
        if not isinstance(policy, dict) or set(policy) != {'model', 'routing', 'local'} or not isinstance(binding['model'], str) or not binding['model'] or policy['model'] != binding['model']:
            raise ValueError('workflow arm model/policy binding invalid')
        if not isinstance(binding['environment'], dict) or not binding['environment']:
            raise ValueError('workflow arm environment binding required')
    if any(arms['baseline'][key] != arms['candidate'][key] for key in ('model', 'policy', 'environment')):
        raise ValueError('workflow arms require equal model/policy/environment controls')
    eid = digest(dict(project=project, spec=spec))
    with database(state) as db:
        _schema(db)
        db.execute('BEGIN IMMEDIATE')
        consume(db, nonce)
        db.execute('INSERT INTO workflow_evaluations VALUES(?,?,?,?,?)', (eid, project, json.dumps(spec), time.time(), json.dumps(request)))
    return dict(evaluation_id=eid, frozen=True)


def _snapshot(db, workflow, project, include_timestamps=False):
    row = db.execute('SELECT manifest,created FROM workflows WHERE id=? AND project=?', (workflow, project)).fetchone()
    if not row:
        raise ValueError('workflow/project mismatch')
    manifest = json.loads(row[0])
    nodes = list(db.execute('SELECT node,state,run,cells FROM workflow_nodes WHERE workflow=? ORDER BY node', (workflow,)))
    calls, attempts, runs = [], [], []
    for _, _, run, _ in nodes:
        if run is None:
            continue
        run_row = db.execute('SELECT project,plan,created FROM runs WHERE id=?', (run,)).fetchone()
        if not run_row or run_row[0] != project:
            raise ValueError('workflow run/project mismatch')
        runs.append([run, *run_row])
        calls.extend([run, *r] for r in db.execute('SELECT role,status,result FROM calls WHERE run=? ORDER BY role', (run,)))
        fields = 'id,role,ordinal,cell,result' + (',created' if include_timestamps else '')
        attempts.extend([run, *r] for r in db.execute('SELECT ' + fields + ' FROM execution_attempts WHERE run=? ORDER BY id', (run,)))
    # Include orphaned/cross-bound attempts too; never silently omit recorded spend.
    fields = 'id,run,role,ordinal,cell,result' + (',created' if include_timestamps else '')
    linked = list(db.execute('SELECT ' + fields + ' FROM execution_attempts WHERE workflow=? ORDER BY id', (workflow,)))
    evidence = dict(manifest=manifest, nodes=nodes, runs=runs, calls=calls, attempts=attempts, linked_attempts=linked)
    if include_timestamps:
        evidence['workflow_created'] = row[1]
    return evidence, row[1], digest(evidence)


def _attest(request, project, state):
    from crews.omp_adapter import database
    metrics = request.get('metrics')
    if not isinstance(metrics, dict) or set(metrics) != {'components', 'latency_ms', 'pricing_reference', 'coverage'}:
        raise ValueError('complete workflow accounting metrics required')
    summarize([dict(id='attestation', family='accounting', accepted=False, behavior='unknown', false_complete=False,
                    **{k: metrics[k] for k in ('components', 'latency_ms', 'pricing_reference')})])
    if not isinstance(metrics['components'], dict) or set(metrics['components']) != COMPONENTS or not all(_number(v) for v in metrics['components'].values()) or not _number(metrics['latency_ms']) or not isinstance(metrics['pricing_reference'], str) or not metrics['pricing_reference'].strip():
        raise ValueError('complete components and pricing provenance required')
    if metrics['coverage'] != {k: True for k in ('all_attempts', 'main', 'governance', 'context')} or any(type(v) is not bool for v in metrics['coverage'].values()):
        raise ValueError('whole workflow accounting coverage required')
    nonce = authorize(request, project, state)
    with database(state) as db:
        _schema(db)
        db.execute('BEGIN IMMEDIATE')
        evidence, _, identity = _snapshot(db, request.get('workflow_id'), project)
        if request.get('evidence_hash') != identity:
            raise ValueError('workflow accounting evidence changed')
        if any(c[2] in ('planned', 'admitted') for c in evidence['calls']):
            raise ValueError('workflow accounting requires settled attempts')
        consume(db, nonce)
        db.execute('INSERT INTO workflow_accounting VALUES(?,?,?)', (request['workflow_id'], json.dumps(request), time.time()))
    return dict(attested=True, workflow_id=request['workflow_id'], evidence_hash=identity)


def _record(db, reference, unit, frozen_at, state, binding, evaluation_mode='monetary'):
    from crews.omp_adapter import canonical
    from crews.workflow import _validate_artifacts, _validate_frozen
    project = canonical(reference['project'])
    evidence, created, identity = _snapshot(db, reference['workflow_id'], project, include_timestamps=evaluation_mode == 'quality_only')
    manifest = evidence['manifest']
    missing, violations = [], []
    if created <= frozen_at or any(r[3] <= frozen_at for r in evidence['runs']):
        violations.append('workflow_precedes_frozen_holdout')
    if digest({'acceptance': manifest['acceptance'], 'before': manifest['before']}) != unit['before_hash'] or digest(manifest['acceptance']) != unit['acceptance_hash']:
        violations.append('frozen_contract_mismatch')
    if any(manifest.get(key) != binding[key] for key in ('profile', 'policy', 'environment')) or manifest['policy'].get('model') != binding['model']:
        violations.append('frozen_arm_binding_mismatch')
    if fingerprints(project, list(manifest['sources'])) != manifest['sources']:
        violations.append('frozen_sources_changed')
    try:
        _validate_frozen(manifest, project, state)
        _validate_artifacts(db, manifest)
    except ValueError:
        violations.append('workflow_artifacts_changed')
    plans = {r[0]: json.loads(r[2]) for r in evidence['runs']}
    cells = {(run, c['role_id']): c for run, plan in plans.items() for wave in plan['waves'] for c in wave['calls']}
    def bound(cell):
        return (cell.get('workflow_profile') == binding['profile'] and cell.get('workflow_policy_snapshot') == binding['policy']
                and cell.get('policy_binding') == binding['model'] and cell.get('routing_policy_version') == binding['policy']['routing'])
    if any(not bound(cell) for cell in cells.values()):
        violations.append('frozen_execution_binding_mismatch')
    attempts = {(r[0], r[2]): [] for r in evidence['attempts']}
    for attempt in evidence['attempts']:
        attempts[(attempt[0], attempt[2])].append(attempt)
        if not bound(json.loads(attempt[4])):
            violations.append('frozen_attempt_binding_mismatch')
        if not json.loads(attempt[5]).get('host_authenticated'):
            missing.append('attempt_host_receipt_missing')
        elif not model_proof(json.loads(attempt[4]), json.loads(attempt[5])):
            missing.append('attempt_model_proof_missing')
    if {a[1] for a in evidence['attempts']} != {a[0] for a in evidence['linked_attempts']}:
        violations.append('workflow_attempt_binding_mismatch')
    final = []
    false_complete = False
    for run, role, status, raw in evidence['calls']:
        cell = cells.get((run, role))
        result = json.loads(raw) if raw else {}
        history = attempts.get((run, role), [])
        if not cell or not history or not model_proof(json.loads(history[-1][4]), json.loads(history[-1][5])):
            missing.append('immutable_attempt_receipt_missing')
            continue
        if status in ('planned', 'admitted') or not result.get('host_authenticated') or not model_proof(cell, result):
            missing.append('delivery_model_authority_proof_missing')
        # Research snapshots are validated at handoff; later authorized writers
        # may change their inputs. Final checker evidence remains current.
        if cell.get('agent_type','').startswith('crew-check-'):
            expected = result.get('fingerprints') or {}
            if fingerprints(project, list(expected)) != expected:
                violations.append('execution_artifacts_stale')
        false_complete |= bool(result.get('outcome', {}).get('claim_contradicted'))
        if [cell.get('node_id'), role] in manifest['final_checks'] or (cell.get('node_id'), role) in manifest['final_checks']:
            proof = derive(cell, result, project)
            if not set(manifest['acceptance']) <= set((cell.get('checker_profile') or {}).get('criteria', [])):
                violations.append('original_acceptance_not_checked')
            final.append(proof['behavior'])
    if not final or 'unknown' in final:
        missing.append('independent_behavior_unknown')
    behavior = 'fail' if 'fail' in final else 'pass' if final and all(v == 'pass' for v in final) else 'unknown'
    if false_complete:
        violations.append('false_complete')
    if any(c.get('policy_abstained') is not unit['expected_abstain'] for c in cells.values() if c.get('write_scope')):
        violations.append('frozen_abstention_mismatch')
    metrics = dict(components={}, latency_ms=None, pricing_reference='')
    if evaluation_mode == 'quality_only':
        # Host ledger times, never caller durationMs or a signed price estimate.
        ends = [a[6] for a in evidence['attempts']]
        starts = {r[0]: r[3] for r in evidence['runs']}
        if (not ends or not _number(created) or any(not _number(a[6]) or a[6] < created
                or a[6] < starts[a[0]] for a in evidence['attempts'])):
            missing.append('immutable_workflow_latency_missing')
        else:
            metrics['latency_ms'] = (max(ends) - created) * 1000
    else:
        accounted = db.execute('SELECT request,attested FROM workflow_accounting WHERE workflow=?', (reference['workflow_id'],)).fetchone()
        if accounted:
            signed = json.loads(accounted[0])
            authorize(signed, project, state, accepted_at=accounted[1])
            if signed.get('workflow_id') != reference['workflow_id'] or signed.get('evidence_hash') != identity:
                violations.append('signed_accounting_evidence_changed')
            else:
                metrics = signed['metrics']
        else:
            missing.append('signed_whole_workflow_accounting_missing')
    accepted = behavior == 'pass' and not [m for m in missing if m != 'signed_whole_workflow_accounting_missing'] and not violations and bool(evidence['calls']) and all(c[2] == 'completed' for c in evidence['calls']) and all(n[2] for n in evidence['nodes'])
    record = dict(id=unit['id'], family=unit['family'], accepted=accepted, behavior=behavior, false_complete=false_complete,
                  **{k: metrics[k] for k in ('components', 'latency_ms', 'pricing_reference')})
    return record, missing, violations, dict(workflow_id=reference['workflow_id'], evidence_hash=identity,
                                         attempts=len(evidence['attempts']),
                                         latency_source='host_workflow_created_to_last_immutable_attempt' if evaluation_mode == 'quality_only' else 'signed_accounting',
                                         stage_routes=[dict(run=run, role=role, stage=c.get('workflow_stage'), combo=c.get('policy_combo')) for (run, role), c in cells.items()])


def dispatch(request, project, state):
    from crews.omp_adapter import canonical, database
    if not isinstance(request, dict):
        raise ValueError('workflow evaluation request required')
    project = canonical(project)
    operation = request.get('operation')
    if operation == 'freeze':
        return _freeze(request, project, state)
    if operation == 'attest':
        return _attest(request, project, state)
    if operation == 'evidence':
        with database(state) as db:
            evidence, _, identity = _snapshot(db, request.get('workflow_id'), project)
        return dict(workflow_id=request['workflow_id'], evidence_hash=identity,
                    attempts=len(evidence['attempts']), accounting_verified=False)
    if operation != 'report' or set(request) - {'operation', 'evaluation_id', 'results'}:
        raise ValueError('workflow evaluation requires freeze/attest/report; caller scores forbidden')
    if not request.get('evaluation_id'):
        return dict(rollout='NO_GO', selection='baseline', authenticated=False, accounting_complete=False,
                    missing=['operator-approved frozen corpus missing'], unknown_is_zero=False)
    # Validate the separately signed SDLC manifest without relaxing evaluation.py.
    refs = request.get('results')
    if not isinstance(refs, list):
        raise ValueError('workflow result references required')
    with database(state) as db:
        _schema(db)
        stored = db.execute('SELECT spec,created,approval FROM workflow_evaluations WHERE id=? AND project=?', (request['evaluation_id'], project)).fetchone()
        if not stored:
            raise ValueError('workflow evaluation not frozen in project')
        raw, frozen_at, approval = stored
        spec, signed = json.loads(raw), json.loads(approval)
        authorize(signed, project, state, accepted_at=frozen_at)
        if signed.get('spec') != spec or digest(dict(project=project, spec=spec)) != request['evaluation_id']:
            raise ValueError('frozen workflow evaluation manifest changed')
        mode = spec.get('evaluation_mode', 'monetary')
        units = {u['id']: u for u in spec['units'] if u['split'] == 'holdout'}
        pairs, used, snapshots = {}, set(), set()
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {'unit', 'arm', 'workflow_id', 'project'} or ref['unit'] not in units or ref['arm'] not in ('baseline', 'candidate'):
                raise ValueError('strict frozen workflow reference required')
            key = (ref['unit'], ref['arm'])
            ep = canonical(ref['project'])
            if not Path(ep).is_relative_to(Path(project)):
                raise ValueError('workflow evaluation snapshot escapes project')
            if key in pairs or ref['workflow_id'] in used or ep in snapshots:
                raise ValueError('independent unique paired workflow snapshots required')
            pairs[key] = ref
            used.add(ref['workflow_id'])
            snapshots.add(ep)
        rows = {'baseline': [], 'candidate': []}
        missing, violations, receipts, sources = [], [], [], {}
        for unit in units.values():
            for arm in rows:
                ref = pairs.get((unit['id'], arm))
                if not ref:
                    missing.append([unit['id'], arm, 'workflow_missing'])
                    row = dict(id=unit['id'], family=unit['family'], accepted=False, behavior='unknown', false_complete=False, components={}, latency_ms=None, pricing_reference='')
                else:
                    try:
                        args = (db, ref, unit, frozen_at, state, spec['arms'][arm])
                        row, gaps, faults, receipt = _record(*args, evaluation_mode=mode) if mode == 'quality_only' else _record(*args)
                        receipts.append(dict(unit=unit['id'], arm=arm, **receipt))
                        missing.extend([unit['id'], arm, gap] for gap in gaps)
                        violations.extend([unit['id'], arm, fault] for fault in faults)
                        source = unit['before_hash']
                        if source in sources and sources[source] != unit['id']:
                            violations.append([unit['id'], arm, 'source_reused_as_independent_unit'])
                        sources[source] = unit['id']
                    except (ValueError, KeyError) as exc:
                        missing.append([unit['id'], arm, str(exc)])
                        row = dict(id=unit['id'], family=unit['family'], accepted=False, behavior='unknown', false_complete=False, components={}, latency_ms=None, pricing_reference='')
                rows[arm].append(row)
    report = compare(rows['baseline'], rows['candidate'], mode)
    report.update(evaluation_id=request['evaluation_id'], authenticated=True, missing=missing, violations=violations, receipts=receipts,
                  accounting_complete=not missing and not violations and all(report[a]['accounting_complete'] for a in rows),
                  uncertainty='Finite frozen pilot; no production guarantee.')
    report['quality_gate'] = report['quality_gate'] and not missing and not violations
    left, right = report['baseline'], report['candidate']
    if mode == 'quality_only':
        report['accounting_complete'] = False
        report['cost_gate'] = None
        report['latency_gate'] = bool(not missing and not violations and latency_gate(left, right, spec))
        report['latency_criterion'] = ({'kind':'absolute','max_latency_ms':spec['max_latency_ms']}
                                       if 'max_latency_ms' in spec else {'kind':'relative','max_latency_ratio':min(1.2,spec['max_latency_ratio'])})
        required_gates = ('quality_gate', 'latency_gate')
    else:
        report['cost_gate'] = bool(report['accounting_complete'] and left['cost_per_accepted'] is not None and right['cost_per_accepted'] is not None and right['cost_per_accepted'] <= left['cost_per_accepted'] * (1 - max(.15, spec['min_cost_reduction'])))
        report['latency_gate'] = bool(report['accounting_complete'] and left['p95'] is not None and right['p95'] is not None and right['p95'] <= left['p95'] * min(1.2, spec['max_latency_ratio']))
        required_gates = ('quality_gate', 'cost_gate', 'latency_gate')
    report['rollout'] = 'GO' if all(report[k] for k in required_gates) else 'NO_GO'
    report['selection'] = 'candidate' if report['rollout'] == 'GO' else 'baseline'
    return report
