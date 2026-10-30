"""Local privacy, immutable provenance and safety checks; isolated from existing state."""
import copy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from crews import learning as l


def rejects(call):
    try:
        call()
    except (ValueError, TypeError):
        return
    raise AssertionError('expected rejection')


def check():
    previous = os.environ.get('CREWS_OMP_HOME')
    with tempfile.TemporaryDirectory() as home:
        os.environ['CREWS_OMP_HOME'] = home
        try:
            run(Path(home))
        finally:
            if previous is None:
                os.environ.pop('CREWS_OMP_HOME', None)
            else:
                os.environ['CREWS_OMP_HOME'] = previous


def run(home):
    project = str(home / 'secret-project-path-573981')
    role = {
        'name': 'private-role-name-573981', 'kind': 'check', 'mission': 'check private-objective-573981',
        'solution_space': 'private-method-573981', 'scope': [], 'read_scope': ['private-source-path-573981'],
        'commands': ['private-command-573981'], 'authority': ['private-authority-573981'],
        'criteria': ['private-criterion-573981'], 'deliverable': 'private-deliverable-573981',
        'facts': {'method_fixed': True, 'targets_fixed': True, 'criterion_fixed': True,
                  'unknown_cause': False, 'consequential_judgment': False, 'behavior_undecided': False},
        'answers': {'divisible': 0, 'specific': 1}, 'classification': True,
    }
    proposal = {'need': 'mechanical_verification', 'difficulty': 0}
    policy = 'Combo Large teacher prompt v7 private-policy-573981'
    context = 'artifact-sha256-private-context-573981'

    def call(op, **kw):
        return l.dispatch({'operation': op, **kw}, project)

    def obs(r=role, **kw):
        p = dict(role=r, context_fingerprint=context, policy_version=policy, proposal=proposal,
                 metrics={'source': 'teacher', 'latency_ms': 12, 'input_tokens': 30,
                          'output_tokens': 4, 'reasoning_tokens': None, 'cache_hit': False})
        p.update(kw)
        return call('observe', **p)

    def lookup(r=role, **kw):
        p = dict(role=r, context_fingerprint=context, policy_version=policy)
        p.update(kw)
        return call('lookup', **p)

    def label(oid, unit, split='train', **kw):
        p = dict(observation_id=oid, unit_id=unit, split=split, evidence='private-evidence-573981', **proposal)
        p.update(kw)
        return call('label', **p)

    def ready(r=role, prefix='base'):
        ids = []
        result = None
        for i in range(5):
            current = obs(r)
            ids.append(current['observation_id'])
            result = label(ids[-1], prefix + str(i), 'train' if i < 3 else 'holdout')
            if i < 2:
                assert result['state'] == 'collecting' and result['rule_id'] is None
            elif i < 4:
                assert result['state'] == 'candidate'
                rejects(lambda: call('activate', rule_id=result['rule_id']))
        assert result['state'] == 'shadow_ready'
        return result['rule_id'], ids

    assert call('status')['mode'] == 'shadow'
    initial = obs()
    assert len(initial['signature']) == 64
    assert not lookup()['match']
    renamed = {**role, 'name': 'different', 'deliverable': 'other', 'session_id': 'session-2'}
    spaced = {**renamed, 'mission': '  check   private-objective-573981  '}
    assert obs(renamed)['signature'] == initial['signature']
    assert obs(spaced)['signature'] != initial['signature']
    for field, value in [('mission', 'new task'), ('solution_space', 'new method'), ('read_scope', ['new scope']),
                         ('commands', ['new command']), ('authority', ['new authority']), ('criteria', ['new criterion'])]:
        assert obs({**role, field: value})['signature'] != initial['signature']
    assert obs(context_fingerprint='changed artifact content hash')['signature'] != initial['signature']
    rejects(lambda: obs(proposal={**proposal, 'reason': 'secret'}))
    rejects(lambda: obs(proposal={'need': 'unknown', 'difficulty': 0}))
    rejects(lambda: obs(proposal={'need': 'mechanical_verification', 'difficulty': True}))
    rejects(lambda: obs(proposal={'need': 'mechanical_verification', 'difficulty': float('nan')}))
    rejects(lambda: obs(metrics={'latency_ms': -1}))
    rejects(lambda: obs(metrics={'source': 'model_ground_truth'}))
    rejects(lambda: call('invented_operation'))

    # Run outcomes do not become labels, including uppercase COMPLETED.
    for outcome in ('COMPLETED', 'completed', 'provider_error', 'timeout', 'failed', 'cancelled'):
        assert call('outcome', observation_id=initial['observation_id'], outcome=outcome)['label_created'] is False
    assert call('status')['labels'] == 0
    rejects(lambda: label(initial['observation_id'], 'empty', evidence='  '))
    rejects(lambda: label(initial['observation_id'], 'model', source='teacher'))
    rejects(lambda: label(initial['observation_id'], 'bad-split', split='test'))
    rid, ids = ready()
    assert len(call('rules')['rules']) == 1
    assert not lookup()['match'] and lookup()['candidate_id'] == rid
    duplicate = label(obs()['observation_id'], 'base0')
    assert duplicate['duplicate'] and not duplicate['accepted']
    rejects(lambda: label(obs()['observation_id'], 'base0', 'holdout'))
    rejects(lambda: label(ids[0], 'different-independent-unit'))
    # One unit cannot leak between policy revisions either.
    other_policy_obs = obs(policy_version=policy + ' v8')['observation_id']
    rejects(lambda: label(other_policy_obs, 'base0', 'holdout'))
    assert label(other_policy_obs, 'base0')['duplicate']
    assert call('status')['labels'] == 5

    call('activate', rule_id=rid)
    assert not lookup()['match']  # Activation does not silently enable routing.
    call('configure', mode='on')
    for i in range(1, 10):
        hit = lookup()
        assert hit['match'] and hit['rule_id'] == rid and not hit['audit_due']
    tenth = lookup()
    assert tenth['audit_due']
    assert lookup()['audit_due']  # Audits cannot disappear when provider fails to reply.
    audited = call('audit', rule_id=rid, proposal=proposal)
    assert audited['agrees'] and audited['state'] == 'active'
    assert not lookup()['audit_due']
    assert not lookup(policy_version='changed teacher prompt identity')['match']
    assert not lookup(context_fingerprint='changed context')['match']
    assert not l.lookup(project + '-other', role, context, policy)['match']
    assert l.status(project + '-other')['mode'] == 'shadow'
    facts_change = copy.deepcopy(role)
    facts_change['facts']['method_fixed'] = False
    assert not lookup(facts_change)['match']
    assert not lookup({**role, 'commands': ['different exact method']})['match']
    learned = call('observe', role=role, context_fingerprint=context, policy_version=policy, proposal=proposal,
                   metrics={'source': 'learned', 'teacher_avoided': True, 'latency_ms': 1, 'input_tokens': None})
    learned_id = learned['observation_id']
    for field, value in (('source', 'teacher'), ('cache_hit', True), ('teacher_avoided', False),
                         ('teacher_requested', True), ('shadow_sampled', True), ('latency_ms', 9),
                         ('input_tokens', 9), ('output_tokens', 9), ('reasoning_tokens', 9),
                         ('outcome', 'failed')):
        rejects(lambda field=field, value=value: call('outcome', observation_id=learned_id,
                outcome='completed', metrics={field: value}))
    assert call('outcome', observation_id=learned_id, outcome='completed',
                metrics={'task_latency_ms': 7, 'task_input_tokens': 8, 'task_output_tokens': 9})['outcome'] == 'completed'
    rejects(lambda: label(learned_id, 'learned-source-overwrite'))
    with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
        learned_metrics = json.loads(db.execute('SELECT metrics FROM observations WHERE id=?', (learned_id,)).fetchone()[0])
    assert learned_metrics == {'source': 'learned', 'teacher_avoided': True, 'latency_ms': 1,
                               'input_tokens': None, 'outcome': 'completed', 'task_latency_ms': 7,
                               'task_input_tokens': 8, 'task_output_tokens': 9}
    before = call('status')
    assert before['teacher_calls_avoided'] == 1
    assert before['resource_coverage']['reasoning_tokens']['unknown'] == before['observations']
    assert before['resource_coverage']['input_tokens']['unknown'] >= 1
    assert before['label_accuracy']['correct'] == 5 and before['label_accuracy']['accuracy'] == 1
    assert before['errors'] == 1
    assert call('audit', rule_id=rid, proposal={'need': 'difficult_review', 'difficulty': 3})['state'] == 'suspended'
    assert not lookup()['match']
    rejects(lambda: call('activate', rule_id=rid))

    # Conflict suspends a different rule, including holdout labels.
    conflict_role = {**role, 'mission': 'independent conflicting family'}
    conflict_id, conflict_obs = ready(conflict_role, 'conflict')
    call('activate', rule_id=conflict_id)
    assert label(obs(conflict_role)['observation_id'], 'conflict-extra', 'holdout',
                 need='difficult_review', difficulty=3)['state'] == 'suspended'
    assert not lookup(conflict_role)['match']
    # Duplicate unit with disagreeing label also suspends, never adds an independent vote.
    dup_role = {**role, 'mission': 'duplicate conflict family'}
    dup_id, _ = ready(dup_role, 'dup')
    assert label(obs(dup_role)['observation_id'], 'dup0', need='difficult_review', difficulty=3)['conflict']
    rejects(lambda: call('activate', rule_id=dup_id))
    # Explicit rollback never auto-reactivates on later valid labels.
    rollback_role = {**role, 'mission': 'rollback family'}
    rollback_id, _ = ready(rollback_role, 'rollback')
    call('activate', rule_id=rollback_id)
    call('rollback', rule_id=rollback_id)
    assert label(obs(rollback_role)['observation_id'], 'rollback-more')['state'] == 'rolled_back'
    assert not lookup(rollback_role)['match']
    rejects(lambda: call('activate', rule_id=rollback_id))
    # Audit error is not training difficulty. It suspends without generating labels.
    error_role = {**role, 'mission': 'provider failure family'}
    error_id, _ = ready(error_role, 'error')
    call('activate', rule_id=error_id)
    count = call('status')['labels']
    assert call('audit', rule_id=error_id, outcome='provider_error')['state'] == 'suspended'
    assert call('status')['labels'] == count

    # Both automatic proposals and manual labels obey safety and explicit negative facts.
    for fact in ('unknown_cause', 'consequential_judgment', 'behavior_undecided'):
        dangerous = copy.deepcopy(role)
        dangerous['facts'][fact] = True
        rejects(lambda: obs(dangerous))
        oid = obs(dangerous, proposal=None)['observation_id']
        rejects(lambda: label(oid, 'danger-' + fact))
    unknown = {**role, 'facts': {}}
    unknown_id = obs(unknown)['observation_id']  # Collect teacher answer, never learn cheap unknown risk.
    rejects(lambda: label(unknown_id, 'unknown-risk'))
    # Malformed classifications never enter persistent safe metadata.
    rejects(lambda: obs({**role, 'facts': {'unknown_cause': 'credential-secret'}}))
    rejects(lambda: obs({**role, 'kind': 'untrusted-command'}))
    rejects(lambda: obs({**role, 'answers': {'divisible': float('inf')}}))
    for facts in ([], False, 0, ''):
        rejects(lambda facts=facts: obs({**role, 'facts': facts}))

    # Risk survives storage: neither observation nor later human label can cheapen it.
    risk_role = {**role, 'risk': {'security': True, 'authorization': False}}
    rejects(lambda: obs(risk_role))
    risk_oid = obs(risk_role, proposal=None)['observation_id']
    rejects(lambda: label(risk_oid, 'critical-cheap'))
    rejects(lambda: obs({**risk_role, 'answers': {**role['answers'], **proposal}}, proposal=None))
    assert label(risk_oid, 'critical-review', need='difficult_review', difficulty=2.5)['accepted']
    with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
        risk_safe = json.loads(db.execute('SELECT safe_role FROM observations WHERE id=?', (risk_oid,)).fetchone()[0])
    assert risk_safe['risk']['security'] is True and risk_safe['risk']['authorization'] is False
    rejects(lambda: l._proposal(risk_safe, proposal, learning_safe=False))
    rejects(lambda: obs({**role, 'risk': {'security': 'credential-secret'}}, proposal=None))
    rejects(lambda: obs({**role, 'host_tools': ['private-command-573981']}, proposal=None))
    for kind in ('check', 'research'):
        rejects(lambda kind=kind: obs({**role, 'kind': kind, 'scope': ['private-write-path-573981']}, proposal=None))

    # Specialist eligibility persists as presence, not private prose or attempt IDs.
    specialist = {'need': 'specialist', 'difficulty': 2}
    for field, value in (('capability_reason', 'private-capability-reason-573981'),
                         ('prior_attempt', {'run': 'private-prior-run-573981', 'role': 'private-prior-role-573981'})):
        specialist_role = {**role, field: value}
        specialist_oid = obs(specialist_role, proposal=specialist)['observation_id']
        assert label(specialist_oid, 'specialist-' + field, **specialist)['accepted']
        with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
            specialist_safe = json.loads(db.execute('SELECT safe_role FROM observations WHERE id=?', (specialist_oid,)).fetchone()[0])
        assert specialist_safe[field + '_present'] is True and field not in specialist_safe
        assert l._proposal(specialist_safe, specialist) == specialist
        if field == 'capability_reason':
            rejects(lambda: l._proposal(specialist_safe, {'need': 'specialist', 'difficulty': 1}))
    rejects(lambda: obs(role, proposal=specialist))
    rejects(lambda: obs({**role, 'capability_reason_present': True, 'prior_attempt_present': True}, proposal=specialist))
    rejects(lambda: obs({**role, 'capability_reason': '  '}, proposal=None))
    rejects(lambda: obs({**role, 'prior_attempt': {'run': 'private-prior-run-573981'}}, proposal=None))
    write_oid = obs({**role, 'kind': 'produce', 'scope': ['private-write-path-573981']}, proposal=None)['observation_id']
    with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
        write_safe = json.loads(db.execute('SELECT safe_role FROM observations WHERE id=?', (write_oid,)).fetchone()[0])
    assert write_safe['scope_write_present'] is True and 'scope' not in write_safe
    for kind in ('check', 'research'):
        rejects(lambda kind=kind: l._proposal({**write_safe, 'kind': kind}, {'need': 'difficult_review', 'difficulty': 3}))
    literal_a = obs({**role, 'commands': ['echo "a  b"']})
    literal_b = obs({**role, 'commands': ['echo "a b"']})
    assert literal_a['signature'] != literal_b['signature']
    partial_a = obs({**role, 'answers': {**role['answers'], 'need': 'mechanical_verification'}})
    partial_b = obs({**role, 'answers': {**role['answers'], 'difficulty': 0}})
    assert partial_a['signature'] != partial_b['signature']
    assert call('report')['label_accuracy']['scored'] >= 5
    assert len(call('observations', limit=2)['observations']) == 2
    rejects(lambda: call('observations', limit=10001))

    # Byte-level privacy: raw task/source/path/command/evidence/context/policy never stored.
    raw = (home / 'learning.sqlite').read_bytes()
    for secret in ('private-role-name', 'private-objective', 'private-source-path', 'private-command',
                   'private-authority', 'private-criterion', 'private-evidence', 'private-context',
                   'private-policy', 'secret-project-path', 'private-method', 'credential-secret',
                   'private-capability-reason', 'private-prior-run', 'private-prior-role', 'private-write-path'):
        assert secret.encode() not in raw, secret
    with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
        assert db.execute("SELECT count(*) FROM labels WHERE source!='user'").fetchone()[0] == 0
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert len((home / 'learning.key').read_bytes()) == 32
    call('configure', mode='off')
    assert obs()['observation_id'] is None and not lookup()['match']
    call('configure', mode='shadow')
    # Per-project cap is bounded and requires explicit purge, not silent label deletion.
    old_cap = l.MAX_OBSERVATIONS
    l.MAX_OBSERVATIONS = call('status')['observations']
    try:
        assert obs()['dropped'] is True
        other_project_observation = l.observe(project+'-capacity-other', role, context, policy, proposal)
        assert other_project_observation['observation_id'] and not other_project_observation.get('dropped', False)
    finally:
        l.MAX_OBSERVATIONS = old_cap
    removed = call('purge')['purged']
    assert removed > 0
    clean = call('status')
    assert clean['observations'] == 0 and clean['labels'] == 0 and clean['states'] == {}
    assert clean['mode'] == 'shadow'
    assert call('rules')['rules'] == []
    assert not (home / 'runs.sqlite').exists()
    feedback_checks(home, role, proposal, policy, context)


def feedback_checks(home, role, proposal, policy, context):
    from crews import omp_adapter as adapter
    project = home / 'feedback-project'
    project.mkdir()
    project = adapter.canonical(str(project))
    target = Path(project) / 'artifact.txt'
    target.write_text('verified content', encoding='utf-8')
    answers = {**role['answers'], **proposal}
    effective = {**role, 'answers': answers}

    def call(op, **kw):
        return l.dispatch({'operation': op, **kw}, project)

    def fixture(name='good', source='teacher', original=role):
        observed = call('observe', role=original, context_fingerprint=context, policy_version=policy,
                        proposal=proposal, metrics={'source': source, 'shadow_sampled': True})
        cell = {**adapter.remap_seat(effective, 'haiku', 'low'), 'role_id': 'check',
                'role_answers': answers, 'declared_role_answers': answers,
                'write_scope': [], 'read_scope': ['artifact.txt'], 'facts': copy.deepcopy(original.get('facts', {})),
                'classification': {'learning': {'observation_id': observed['observation_id']}}}
        plan = {'waves': [{'kind': role['kind'], 'calls': [cell]}]}
        result = {'status': 'COMPLETE', 'host_authenticated': True, 'verification': ['assert artifact verified independently'],
                  'native': {'exitCode': 0, 'resolvedModel': cell['provider'] + '/' + cell['model'] + ':' + cell['reasoning_effort'],
                             'resolvedThinkingLevel': cell['reasoning_effort']},
                  'wire': {'model': cell['model'], 'effort': cell['reasoning_effort'], 'provider': cell['provider'], 'role': 'check'},
                  'fingerprints': {'artifact.txt': hashlib.sha256(target.read_bytes()).hexdigest()}}
        save(name, plan, result)
        return plan, result, observed['observation_id']

    def save(name, plan, result, status='completed', receipt_project=project):
        with adapter.database(home) as db:
            db.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)',
                       (name, receipt_project, 'session', 100, json.dumps(plan)))
            db.execute('INSERT OR REPLACE INTO calls VALUES(?,?,?,?,?)',
                       (name, 'check', 'digest', status, json.dumps(result)))

    def feedback(name='good', **kw):
        return call('feedback', **{'run': name, 'role': 'check', 'session': 'session',
                    'need': proposal['need'], 'difficulty': proposal['difficulty'], 'evidence': 'human checked actual result',
                    'unit_id': name, 'split': 'train', **kw})

    assert call('feedback_options')['feedback_options'] == []
    plan, result, oid = fixture()
    raw_runs = (home / 'runs.sqlite').read_bytes()
    labels = call('status')['labels']
    options = call('feedback_options')['feedback_options']
    assert options == [{'observation_id': oid, 'run': 'good', 'role': 'check', 'session': 'session',
                        'declared_need': proposal['need'], 'declared_difficulty': proposal['difficulty']}]
    assert call('status')['labels'] == labels  # COMPLETE receipt and listing never label.
    assert (home / 'runs.sqlite').read_bytes() == raw_runs  # Read-only receipt resolution.
    rejects(lambda: feedback(session='wrong'))
    rejects(lambda: feedback(verified_small=False))
    rejects(lambda: feedback(evidence=''))
    rejects(lambda: feedback(need='everyday_implementation', difficulty=0, split='invalid'))
    assert feedback(verified_small=True)['accepted']
    assert call('feedback_options')['feedback_options'] == []
    with closing(sqlite3.connect(home / 'learning.sqlite')) as db:
        assert db.execute('SELECT need,difficulty FROM labels WHERE observation_id=?', (oid,)).fetchone() == (proposal['need'], proposal['difficulty'])
    assert not feedback()['accepted']

    for name, mutate in (
        ('unauthenticated', lambda c, r: r.update(host_authenticated=False)),
        ('exit', lambda c, r: r['native'].update(exitCode=1)),
        ('bool_exit', lambda c, r: r['native'].update(exitCode=False)),
        ('wire', lambda c, r: r['wire'].update(effort='HIGH')),
        ('model', lambda c, r: r['native'].update(resolvedModel='other')),
        ('effort', lambda c, r: r['native'].update(resolvedThinkingLevel='high')),
        ('provider', lambda c, r: r['wire'].update(provider='other')),
        ('provider_error', lambda c, r: r.update(failure_kind='provider_error')),
        ('native_error', lambda c, r: r['native'].update(error='provider error')),
        ('noobs', lambda c, r: c['classification'].update(learning={})),
        ('noscope', lambda c, r: r.update(fingerprints={})),
        ('noverification', lambda c, r: r.update(verification=[])),
        ('noncomplete', lambda c, r: r.update(status='PARTIAL')),
        ('notSmall', lambda c, r: c.update(policy_combo='Medium')),
        ('binding', lambda c, r: c.update(policy_binding='outdated')),
        ('facts', lambda c, r: c['facts'].update(method_fixed=False)),
    ):
        plan, result, _ = fixture(name)
        plan = copy.deepcopy(plan)
        mutate(plan['waves'][0]['calls'][0], result)
        save(name, plan, result)
        rejects(lambda: feedback(name))
    plan, result, _ = fixture('uncompleted')
    save('uncompleted', plan, result, status='admitted')
    rejects(lambda: feedback('uncompleted'))
    plan, result, _ = fixture('wrongproject')
    save('wrongproject', plan, result, receipt_project=project + '-other')
    rejects(lambda: feedback('wrongproject'))
    fixture('learned', source='learned')
    rejects(lambda: feedback('learned'))
    fixture('unknownfacts', original={**role, 'facts': {}})
    rejects(lambda: feedback('unknownfacts'))
    fixture('stale')
    target.write_text('changed after receipt', encoding='utf-8')
    rejects(lambda: feedback('stale'))
    assert call('feedback_options')['feedback_options'] == []
    rejects(lambda: l.dispatch({'operation': 'feedback_options'}, project + '-missing'))
    report = call('report')
    assert report['shadow_samples'] > 0 and report['by_source']['teacher'] > 0
    assert report['by_source_outcome']['teacher']['pending'] > 0
    assert report['pending_outcomes'] > 0 and report['resource_coverage']['task_latency_ms']['unknown'] > 0


def integration_boundaries():
    from crews import omp_adapter as adapter
    with tempfile.TemporaryDirectory(prefix='learning-boundaries-') as folder:
        root = Path(folder); state = root / 'explicit'; project = root / 'project'; project.mkdir()
        previous = os.environ.get('CREWS_OMP_HOME'); os.environ['CREWS_OMP_HOME'] = str(root / 'ambient')
        role = {'kind':'research','mission':'Read fixed source','scope':[],'answers':{'divisible':0,'specific':1},'facts':{'unknown_cause':False,'consequential_judgment':False,'behavior_undecided':False}}
        proposal = {'need':'bounded_retrieval','difficulty':1}
        try:
            def call(operation, **fields):return l.dispatch({'operation':operation,**fields},str(project),state)
            rule = None
            for index in range(5):
                obs = call('observe',role=role,context_fingerprint='context',policy_version='version',proposal=proposal,metrics={'source':'teacher'})
                labelled = call('label',observation_id=obs['observation_id'],unit_id=str(index),split='train' if index<3 else 'holdout',evidence='independent',**proposal)
                rule = labelled['rule_id']
            call('activate',rule_id=rule);call('configure',mode='on')
            cell = {'classification':{'outcome':'learned','learning':{'rule_id':rule}},'role_answers':proposal,'input_fingerprints':{}}
            l.validate_delivery(cell,str(project),state)
            from check_effort_policy import task_answers
            (project/'source.txt').write_text('original')
            execution_role={**role,'name':'read-source','deliverable':'facts.json','inputs':['source.txt'],'read_scope':['source.txt'],'commands':[],'acceptance':['Read original source'],'answers':{**role['answers'],**proposal},'classification_evidence':cell['classification']}
            pending=adapter.build_plan({'task':'Read original source','roles':[execution_role]},task_answers('bounded_retrieval',1),str(project),'pending',state)
            ambient=root/'ambient';ambient.mkdir();(ambient/'policy.json').write_text('{"provider":"ambient","combos":{"Small":{"model":"different-small","effort":"High"},"Medium":{"model":"different-medium","effort":"High"},"Large":{"model":"different-large","effort":"High"}}}')
            adapter.validate_model(pending['waves'][0]['calls'][0],state)
            from crews.classification import classify_role
            assert classify_role(execution_role,str(project),[execution_role],state)['provider']!='ambient'
            (ambient/'policy.json').unlink()
            active=adapter.build_plan({'task':'Read original source','roles':[execution_role]},task_answers('bounded_retrieval',1),str(project),'active',state)
            admitted=adapter.dispatch(active['run_id'],'read-source',str(project),'active',state)
            adapter.ticket(admitted['token'],str(project),state)
            (project/'source.txt').write_text('changed after planning')
            rejects(lambda:adapter.dispatch(pending['run_id'],'read-source',str(project),'pending',state))
            rejects(lambda:adapter.ticket(admitted['token'],str(project),state))
            (project/'source.txt').write_text('original')
            from crews.outcomes import fingerprints
            writer_cell={**cell,'input_fingerprints':fingerprints(project,['source.txt']),'immutable_input_fingerprints':fingerprints(project,['source.txt'],exclude=['source.txt']),'write_scope':['source.txt']}
            (project/'source.txt').write_text('writer output')
            l.validate_delivery(writer_cell,str(project),state,check_writes=False)
            rejects(lambda:l.validate_delivery(writer_cell,str(project),state))
            (project/'source.txt').write_text('original')
            (project/'src').mkdir()
            (project/'src/input.py').write_text('immutable')
            (project/'src/output.py').write_text('before')
            directory_cell={**cell,'input_fingerprints':fingerprints(project,['src']),'immutable_input_fingerprints':fingerprints(project,['src'],exclude=['src/output.py']),'write_scope':['src/output.py']}
            (project/'src/output.py').unlink()
            l.validate_delivery(directory_cell,str(project),state,check_writes=False)
            (project/'src/output.py').write_text('new output')
            l.validate_delivery(directory_cell,str(project),state,check_writes=False)
            nested=['src/generated/output.py']
            nested_cell={**cell,'input_fingerprints':fingerprints(project,['src']),'immutable_input_fingerprints':fingerprints(project,['src'],exclude=nested),'write_scope':nested}
            (project/'src/generated').mkdir()
            (project/'src/generated/output.py').write_text('authorized output')
            l.validate_delivery(nested_cell,str(project),state,check_writes=False)
            (project/'src/input.py').write_text('changed sibling')
            rejects(lambda:l.validate_delivery(directory_cell,str(project),state,check_writes=False))
            call('rollback',rule_id=rule)
            rejects(lambda:l.validate_delivery(cell,str(project),state))
            rejects(lambda:adapter.dispatch(pending['run_id'],'read-source',str(project),'pending',state))
            rejects(lambda:adapter.ticket(admitted['token'],str(project),state))
            observed=call('observe',role=role,context_fingerprint='record-context',policy_version='version',proposal=proposal,metrics={'source':'teacher'})
            recorded_role={**execution_role,'classification_evidence':{'outcome':'declared','learning':{'observation_id':observed['observation_id']}}}
            recorded=adapter.build_plan({'task':'Read original source','roles':[recorded_role]},task_answers('bounded_retrieval',1),str(project),'recorded',state)
            ticket=adapter.dispatch(recorded['run_id'],'read-source',str(project),'recorded',state)
            adapter.record(recorded['run_id'],'read-source',{'status':'FAILED','verification':['isolated failure']},str(project),'recorded',state,host_key=ticket['host_key'])
            observations=call('observations')['observations'];assert next(item for item in observations if item['observation_id']==observed['observation_id'])['metrics']['outcome']=='failed'
            alias = root / 'alias'
            try:alias.symlink_to(project,target_is_directory=True)
            except OSError:pass
            else:assert l.dispatch({'operation':'status'},str(alias),state)['observations']==6
            assert not (root/'ambient'/'learning.sqlite').exists()
        finally:
            if previous is None:os.environ.pop('CREWS_OMP_HOME',None)
            else:os.environ['CREWS_OMP_HOME']=previous


if __name__ == '__main__':
    check()
    integration_boundaries()
    print('learning checks passed')
