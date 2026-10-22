"""Local assert checks; no provider, model, credentials or existing state needed."""
import copy
from contextlib import closing
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
        'solution_space': 'private-method-573981', 'scope': ['private-source-path-573981'],
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
    for field, value in [('mission', 'new task'), ('solution_space', 'new method'), ('scope', ['new scope']),
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
    call('observe', role=role, context_fingerprint=context, policy_version=policy, proposal=proposal,
         metrics={'source': 'learned', 'teacher_avoided': True, 'latency_ms': 1, 'input_tokens': None})
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
                   'private-policy', 'secret-project-path', 'private-method', 'credential-secret'):
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


if __name__ == '__main__':
    check()
    print('learning checks passed')
