"""Run: python -B check_recipes.py. All state and receipts live in TemporaryDirectory.

Checks call real outcomes.verified_pair; fixture receipts model admitted independent
runs, never replace production verifier with a caller-supplied success label.
"""
import copy
from contextlib import closing
import gc
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from crews import outcomes, recipes, omp_adapter as adapter
from crews.classification import policy_version
from check_effort_policy import isolated_home, task_answers
from approval_fixture import Signer


def reject(call, contains=None):
    try:
        call()
    except ValueError as error:
        if contains:
            assert contains in str(error), str(error)
    else:
        raise AssertionError('expected ValueError')


def check():
    passed = []
    signer=Signer()
    with tempfile.TemporaryDirectory(prefix='crews-recipes-') as directory, isolated_home(Path(directory)/'state'):
        base = Path(directory)
        project = base / 'project'
        project.mkdir()
        state = base / 'state'
        (project / 'verify.py').write_text('assert True\n', encoding='utf-8')
        (project / 'target.py').write_text('value = 1\n', encoding='utf-8')
        (project / 'renamed.py').write_text('value = 2\n', encoding='utf-8')
        command = 'python -B verify.py'
        invariant = 'normal/error/boundary preserved'
        features = {'domain': 'serialization', 'language': 'python', 'operation': 'mapping',
                    'invariant': invariant, 'dependency_shape': 'single_component'}
        binding = outcomes.digest({'provider': 'test', 'model': 'small-v1', 'effort': 'medium', 'policy': policy_version(), 'revision': 'small-revision'})
        profile = {'input': 'verify.py', 'command': command}
        facts = {**dict.fromkeys(recipes.TRUE_FACTS, True), **dict.fromkeys(recipes.FALSE_FACTS, False),
                 'deterministic_check': True}
        role = {'name': 'writer', 'kind': 'produce', 'mission': 'Fix serialization mapping',
                'scope': ['target.py'], 'inputs': ['target.py'], 'commands': [],
                'answers': {'need': 'everyday_implementation', 'difficulty': 1, 'divisible': 0},
                'facts': facts, 'routine_check': 'verifier', 'acceptance': [invariant],
                'recipe_features': features, 'recipe_profile': profile, 'model_binding': binding,
                'model_revision': 'small-revision'}
        checker = {'name': 'verifier', 'kind': 'check', 'scope': [],
                   'inputs': ['target.py', 'renamed.py', 'verify.py'], 'commands': [command],
                   'criteria': [invariant], 'checker_profile': {**profile, 'version': '1'}}
        roles = [role, checker]
        recipe = {'features': features, 'version': 1, 'cue': 'fixed mapping boundary',
                  'lesson': 'Preserve explicit missing/null semantics', 'evidence': ['approved family'],
                  'negative_examples': ['unknown cause', 'cross-system changes'],
                  'applicability': {'domain': 'serialization'}, 'exclusions': [{'domain': 'auth'}],
                  'profile': profile, 'recipe_steps': ['Change explicit mapping only', 'Run independent boundary check'],
                  'max_difficulty': 1.5, 'model_binding': binding}

        def call(op, **kwargs):
            return recipes.dispatch(signer.approve({'operation':op,**kwargs},str(project),state),str(project),state)

        def register(version=1, consent=True, body=None, current_role=None, current_roles=None):
            value = copy.deepcopy(recipe if body is None else body)
            value['version'] = version
            return call('register', recipe=value, machine_consent=consent,
                        role=current_role or role, roles=current_roles or roles)['recipe_id']

        def report(rid):
            return next(item for item in call('report')['recipes'] if item['recipe_id'] == rid)

        def receipt(unit, behavior='pass', model='small-v1', learned=False, filename='target.py', execution='completed', current_role=None):
            """Persist synthetic admitted receipt; real verifier validates linkage/hashes."""
            rid = hashlib.sha256((unit + str(receipt.count)).encode()).hexdigest()
            receipt.count += 1
            pinned = outcomes.profile(checker, str(project), roles)
            producer = {'role_id': 'writer', 'agent_type': 'crew-produce-test', 'provider': 'test',
                        'model': model, 'policy_combo': 'Small', 'reasoning_effort': 'medium', 'routing_policy_version': routing_version,
                        'model_revision': 'small-revision', 'recipe_features': (current_role or role)['recipe_features'],
                        'write_scope': [filename], 'acceptance': [invariant],
                        'input_fingerprints': {'before': 'source-'+unit}, 'evidence_unit': unit}
            if learned:
                producer['recipe_id'] = learned if isinstance(learned, str) else 'learned-recipe'
            check_cell = {'role_id': 'verifier', 'agent_type': 'crew-check-test', 'provider': 'test',
                          'model': 'checker-v1', 'reasoning_effort': 'medium', 'verify_targets': ['writer'],
                          'checker_profile': pinned, 'acceptance': [invariant], 'write_scope':[], 'read_scope':['verify.py',filename]}

            def result(cell, paths):
                return {'status': 'COMPLETE', 'host_authenticated':True, 'native': {'exitCode': 0,
                        'resolvedModel': 'test/' + cell['model'] + ':medium', 'resolvedThinkingLevel': 'medium'},
                        'wire': {'provider': 'test', 'model': cell['model'], 'effort': 'medium', 'role': cell['role_id']},
                        'fingerprints': outcomes.fingerprints(str(project), paths)}

            producer_result = result(producer, [filename])
            checker_result = result(check_cell, ['verify.py', filename])
            checker_result['tool_receipts'] = [{'tool':'bash','command':command,'exit_code':0,'tool_call_id':'host-verify-fixture','error':False,'source':'host_profile','role':'verifier','profile_hash':outcomes.digest(pinned),'artifacts':checker_result['fingerprints']}]
            checker_result['criterion_results'] = [{'criterion': invariant, 'status': behavior if behavior != 'unknown' else 'pass'}]
            checker_result['tool_receipts'][0]['criterion_results']=checker_result['criterion_results']
            if behavior == 'unknown':
                checker_result['failure_kind'] = execution
                checker_result['tool_receipts'] = []
            checker_result['outcome'] = outcomes.derive(check_cell, checker_result, str(project))
            assert checker_result['outcome']['behavior'] == behavior
            with adapter.database(state) as db:
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (rid, adapter.canonical(str(project)), 'fixture', __import__('time').time(), json.dumps({'waves': [
                    {'calls': [producer]}, {'calls': [check_cell]}]})))
                db.execute('INSERT INTO calls VALUES(?,?,?,?,?)', (rid, 'writer', '', 'completed', json.dumps(producer_result)))
                db.execute('INSERT INTO calls VALUES(?,?,?,?,?)', (rid, 'verifier', '', 'completed' if behavior != 'unknown' else 'failed', json.dumps(checker_result)))
                import time
                for cell,value,status in [(producer,producer_result,'completed'),(check_cell,checker_result,'completed' if behavior!='unknown' else 'failed')]:
                    db.execute('INSERT INTO execution_attempts(run,role,ordinal,project,fault,is_repair,combo,cell,result,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,cell['role_id'],1,adapter.canonical(str(project)),'fixture',0,cell.get('policy_combo','Large'),json.dumps(cell),json.dumps(value),time.time()))
            return {'run': rid, 'producer': 'writer', 'checker': 'verifier'}
        receipt.count = 0

        def evidence(rid, unit, split='train', **kwargs):
            return call('evidence', recipe_id=rid, split=split, **receipt(unit, **kwargs))

        def ready(rid, prefix, **kwargs):
            for index in range(3):
                evidence(rid, prefix + '-train-' + str(index), **kwargs)
            for index in range(2):
                evidence(rid, prefix + '-holdout-' + str(index), 'holdout', **kwargs)

        assert recipes.match(role, str(project), roles, state)['mode'] == 'shadow'
        assert not state.exists(), 'read-only lookup created state'
        for confirmation in (None, False, 1, 'true'):
            reject(lambda: recipes.dispatch({'operation': 'configure', 'confirmed': confirmation, 'mode': 'on'}, str(project), state), 'confirmed')
        assert not state.exists()
        state.mkdir()
        (state / 'policy.json').write_text(json.dumps({'provider': 'test', 'combos': {
            name: {'model': 'small-v1' if name == 'Small' else name.lower()+'-v1', 'effort': 'Auto'}
            for name in adapter.COMBOS}}), encoding='utf-8')
        with isolated_home(state):
            routing_version = policy_version()
        binding = outcomes.digest({'provider':'test','model':'small-v1','effort':'medium','policy':routing_version,'revision':'small-revision'})
        role['model_binding'] = recipe['model_binding'] = binding
        rid = register()
        assert (state / 'learning.sqlite').is_file()
        with closing(sqlite3.connect(state / 'learning.sqlite')) as db, db:
            db.execute('CREATE TABLE exact_preserved(value TEXT)')
            db.execute("INSERT INTO exact_preserved VALUES('unchanged')")
        passed.append('strict confirmation; read-only previews create no state; shared learning.sqlite')

        renamed = copy.deepcopy(role)
        renamed.update(mission='Completely different words and file name', scope=['renamed.py'], inputs=['renamed.py'])
        result = recipes.match(renamed, str(project), [renamed, checker], state)
        assert result['candidate']['recipe_id'] == rid and result['reason'] == 'shadow'
        assert result['approved_recipe'] is None and not result['effective_small']
        ood = copy.deepcopy(role)
        ood['recipe_features']['domain'] = 'unrelated'
        assert recipes.match(ood, str(project), [ood, checker], state)['candidate'] is None
        for fact in recipes.TRUE_FACTS:
            unsafe = copy.deepcopy(role)
            unsafe['facts'].pop(fact)
            assert recipes.match(unsafe, str(project), [unsafe, checker], state)['reason'] == 'safety_revalidation'
        for fact in recipes.FALSE_FACTS:
            for value in (True, None):
                unsafe = copy.deepcopy(role)
                unsafe['facts'][fact] = value
                assert recipes.match(unsafe, str(project), [unsafe, checker], state)['reason'] == 'safety_revalidation'
        unsafe = copy.deepcopy(role)
        unsafe['scope'] = ['target.py', 'renamed.py', 'third.py', 'fourth.py']
        assert recipes.match(unsafe, str(project), [unsafe, checker], state)['reason'] == 'safety_revalidation'
        for mutation in ('link', 'invariant', 'profile', 'writable'):
            unsafe = copy.deepcopy(role)
            test_checker = copy.deepcopy(checker)
            if mutation == 'link':
                unsafe['routine_check'] = 'missing'
            elif mutation == 'invariant':
                unsafe['acceptance'] = ['different invariant']
            elif mutation == 'profile':
                test_checker['commands'] = ['python -B other.py']
            else:
                unsafe['scope'] = ['verify.py']
                test_checker['inputs'].append('verify.py')
            assert recipes.match(unsafe, str(project), [unsafe, test_checker], state)['reason'] == 'safety_revalidation'
        passed.append('wording/filename-independent retrieval; OOD, all safety facts, scope, checker/invariant guards')

        reject(lambda: call('activate', recipe_id=rid), '3 train')
        reject(lambda: evidence(rid, 'manual-unrelated-family', current_role=ood), 'family binding')
        assert report(rid)['train'] == report(rid)['holdout'] == 0
        legacy_ref = receipt('legacy-no-attempts')
        legacy_state = base / 'legacy-state'
        legacy_state.mkdir()
        with closing(sqlite3.connect(state / 'runs.sqlite')) as source, closing(sqlite3.connect(legacy_state / 'runs.sqlite')) as legacy:
            source.backup(legacy)
            with legacy:
                legacy.execute('DROP TABLE execution_attempts')
        with closing(sqlite3.connect(state / 'learning.sqlite')) as source, closing(sqlite3.connect(legacy_state / 'learning.sqlite')) as legacy:
            source.backup(legacy)
        legacy_proof = outcomes.verified_pair(**legacy_ref, project=str(project), state=legacy_state)
        reject(lambda: recipes._producer(legacy_proof, str(project), legacy_state), 'canonical attempt source')
        with patch.object(outcomes, 'verified_pair', return_value=legacy_proof):
            reject(lambda: call('evidence', recipe_id=rid, split='train', **legacy_ref), 'canonical attempt source')
        reject(lambda: recipes.capture(**legacy_ref, project=str(project), state=legacy_state), 'canonical attempt source')
        assert report(rid)['train'] == report(rid)['holdout'] == 0
        passed.append('manual evidence rejects unrelated family; legacy pair without canonical attempts refuses evidence and capture')
        first = evidence(rid, 'same-source-bug')
        assert first['train'] == 1
        duplicate = evidence(rid, 'same-source-bug')
        assert duplicate['duplicate'] and duplicate['train'] == 1
        reject(lambda: evidence(rid, 'same-source-bug', 'holdout'), 'cross train/holdout')
        same_group=receipt('correlated-variant')
        parent=outcomes.verified_pair(**{k:v for k,v in receipt('same-source-bug').items()},project=str(project),state=state)
        variant=outcomes.verified_pair(**same_group,project=str(project),state=state)
        with patch.object(outcomes,'verified_pair',return_value={**variant,'source_group':parent['source_group']}):
            reject(lambda:call('evidence',recipe_id=rid,split='holdout',**same_group),'source group')
        evidence(rid, 'train-two')
        evidence(rid, 'train-three')
        evidence(rid, 'holdout-one', 'holdout')
        reject(lambda: call('activate', recipe_id=rid), '3 train')
        evidence(rid, 'holdout-two', 'holdout')
        assert report(rid)['state'] == 'shadow_ready'
        assert math_close(report(rid)['failure_bound'], 1 - .05 ** (1 / 5))
        call('activate', recipe_id=rid)
        assert recipes.match(role, str(project), roles, state)['approved_recipe'] is None
        call('configure', mode='on')
        preview = recipes.match(role, str(project), roles, state)
        assert preview['approved_recipe']['recipe_id'] == rid and not preview['effective_small']
        assert report(rid)['hits'] == 0
        for index in range(9):
            assert call('lookup', role=renamed, roles=[renamed, checker])['effective_small']
        due = call('lookup', role=role, roles=roles)
        assert due['audit_due'] and due['effective_small'] and due['audit_delivery_token']
        assert not call('lookup', role=role, roles=roles)['effective_small']
        duplicate_audit = call('audit', recipe_id=rid, split='train', **receipt('same-source-bug'))
        assert not duplicate_audit['audit_cleared'] and report(rid)['audit_pending']
        unknown_ref=receipt('audit-provider-error','unknown',execution='provider_error')
        reject(lambda:call('audit',recipe_id=rid,split='holdout',**unknown_ref),'delivery token')
        with closing(sqlite3.connect(state/'learning.sqlite')) as db,db:
            db.execute("UPDATE recipe_audit_deliveries SET state='admitted',run=?,role=? WHERE token=?",(unknown_ref['run'],'writer',due['audit_delivery_token']))
        unknown_audit=call('audit',recipe_id=rid,split='holdout',**unknown_ref)
        assert unknown_audit['state']=='suspended' and not report(rid)['audit_pending']
        call('activate',recipe_id=rid)
        with patch('crews.automation.audit_interval',return_value=1):
            fresh_due=call('lookup',role=role,roles=roles)
        fresh_ref=receipt('fresh-audit',learned=rid)
        with closing(sqlite3.connect(state/'learning.sqlite')) as db,db:
            db.execute("UPDATE recipe_audit_deliveries SET state='admitted',run=?,role=? WHERE token=?",(fresh_ref['run'],'writer',fresh_due['audit_delivery_token']))
        audit=call('audit',recipe_id=rid,split='holdout',**fresh_ref)
        assert audit['audit_cleared'] and not report(rid)['audit_pending']
        assert call('lookup',role=role,roles=roles)['effective_small']
        call('rollback', recipe_id=rid, reason='manual quality rollback')
        assert not call('lookup', role=role, roles=roles)['effective_small']
        evidence(rid, 'post-rollback')
        assert report(rid)['state'] == 'rolled_back'
        call('activate', recipe_id=rid)
        assert report(rid)['state'] == 'active'
        passed.append('unit dedup and split isolation; 3+2 activation; every-10-hit fresh behavioral audit; rollback sticky until approval')

        reject(lambda: evidence(rid, 'learned-origin', learned=True), 'non-learned')
        no_consent = register(2, consent=False)
        reject(lambda: evidence(no_consent, 'no-consent'), 'consent')
        reject(lambda: call('evidence', recipe_id=rid, split='train', run='missing', producer='writer', checker='verifier', success=True), 'run')
        with patch.object(outcomes, 'verified_pair', return_value={'verified': True, 'behavior': 'pass'}):
            reject(lambda: call('evidence', recipe_id=rid, split='train', run='x', producer='writer', checker='verifier'), 'missing proof')
        failure = evidence(rid, 'known-behavior-failure', behavior='fail')
        assert failure['state'] == 'suspended' and failure['failures'] == 1
        reject(lambda: call('activate', recipe_id=rid), 'zero behavioral failures')
        conflicting = register(3)
        evidence(conflicting, 'contradiction')
        conflict = evidence(conflicting, 'contradiction', behavior='fail')
        assert conflict['conflict'] and report(conflicting)['state'] == 'suspended'
        reject(lambda: call('activate', recipe_id=conflicting), 'zero behavioral failures')
        passed.append('real authoritative receipt validation; missing/self-learned proof rejected; consent and conflict suspension')

        model_drift = register(4)
        assert evidence(model_drift, 'model-drift', model='small-v2')['state'] == 'suspended'
        drift_role = copy.deepcopy(role)
        drift_role['model_binding'] = 'a' * 64
        assert call('lookup', role=drift_role, roles=[drift_role, checker])['reason'] == 'profile_or_model_drift'
        profile_drift = register(5)
        (project / 'verify.py').write_text('assert 1 == 1\n', encoding='utf-8')
        assert call('lookup', role=role, roles=roles)['reason'] == 'profile_or_model_drift'
        assert report(profile_drift)['state'] == 'suspended'
        (project / 'verify.py').write_text('assert True\n', encoding='utf-8')
        assert not call('lookup', role=role, roles=roles)['effective_small']
        invalid = copy.deepcopy(recipe)
        invalid['applicability'] = {'unknown_cause': False}
        reject(lambda: register(6, body=invalid), 'features')
        invalid = copy.deepcopy(recipe)
        invalid['profile']['input'] = '../verify.py'
        reject(lambda: register(6, body=invalid), 'project-relative')
        extra_writer = {'kind': 'integrate', 'scope': ['verify.py']}
        reject(lambda: register(6, current_roles=roles + [extra_writer]), 'writable')
        passed.append('model/profile drift suspends; immutable versions and risk-gate learning forbidden; profile outside every writer')

        auto = register(6)
        reject(lambda: call('configure', auto_promotion={'min_train': 3, 'min_holdout': 2, 'max_failure_bound': .05}), '5 holdout')
        call('configure', auto_promotion={'min_train': 3, 'min_holdout': 5, 'max_failure_bound': .05})
        for index in range(54):
            evidence(auto, 'auto-train-' + str(index))
        for index in range(4):
            evidence(auto, 'auto-holdout-' + str(index), 'holdout')
        assert report(auto)['state'] != 'active'
        evidence(auto, 'auto-holdout-4', 'holdout')
        assert report(auto)['state'] == 'active' and report(auto)['failure_bound'] <= .05
        assert report(auto)['train'] + report(auto)['holdout'] == 59
        call('rollback', recipe_id=auto, reason='auto cannot revive rollback')
        evidence(auto, 'auto-extra')
        assert report(auto)['state'] == 'rolled_back'
        call('configure', auto_promotion=None)
        passed.append('bounded auto-promotion requires >=5 holdout and >=59 units; exact 95% failure bound; rollback never auto-revives')

        probe_recipe = register(7)
        reject(lambda: call('probe', recipe_id=probe_recipe, baseline=[], candidate=[]), 'budget')
        call('configure', probe_budget={'max_pairs': 2, 'max_cost': 1.0, 'max_latency_ms': 1000})
        baseline = receipt('probe-regression', 'pass')
        candidate = receipt('probe-regression', 'fail')
        result = call('probe', recipe_id=probe_recipe, baseline=[baseline], candidate=[candidate], score=9999)
        assert result['selection'] == 'baseline' and 'regression' in result['reasons']
        assert 'accounting_unknown' in result['reasons']
        assert report(probe_recipe)['train'] == report(probe_recipe)['holdout'] == 0
        reject(lambda: call('probe', recipe_id=probe_recipe, baseline=[baseline], candidate=[candidate]), 'fresh holdout')
        unequal = receipt('other-unit')
        reject(lambda: call('probe', recipe_id=probe_recipe, baseline=[receipt('one-unit')], candidate=[unequal]), 'same independent')
        result = call('probe', recipe_id=probe_recipe,
                      baseline=[receipt('probe-ambiguous', 'unknown', execution='cancelled')],
                      candidate=[receipt('probe-ambiguous', 'pass')])
        assert result['selection'] == 'baseline' and 'ambiguous_or_drift' in result['reasons']
        reject(lambda: call('probe', recipe_id=probe_recipe, baseline=[receipt('train-two')], candidate=[receipt('train-two')]), 'fresh holdout')
        reject(lambda: call('probe', recipe_id=probe_recipe, baseline=[baseline] * 3, candidate=[candidate] * 3), 'within budget')
        from crews.accounting import attest
        positive_base=receipt('fresh-positive-probe','fail')
        positive_candidate=receipt('fresh-positive-probe','pass')
        for ref,cost in [(positive_base,.2),(positive_candidate,.1)]:
            metrics={'cost':cost,'latency_ms':10,'pricing_reference':'independent test fixture','includes':['producer','checker','classifier','main','repairs']}
            request=signer.approve({'run':ref['run'],'metrics':metrics},str(project),state)
            attest(request,str(project),state)
        selected=call('probe',recipe_id=probe_recipe,baseline=[positive_base],candidate=[positive_candidate])
        assert selected['selection']=='candidate' and selected['reasons']==[]
        assert report(probe_recipe)['train']==report(probe_recipe)['holdout']==0
        passed.append('offline paired probe uses run references, never scores; baseline kept on regression/unknown/accounting gaps; frozen holdout/budget enforced')
        auto_capture=register(8)
        call('configure',auto_evidence=True)
        for index in range(30):
            ref=receipt('automatic-source-'+str(index))
            recipes.capture(ref['run'],ref['producer'],ref['checker'],str(project),state)
        assert report(auto_capture)['train']>=3 and report(auto_capture)['holdout']>=2
        assert report(auto_capture)['state']=='shadow_ready'
        call('configure',auto_evidence=False)
        before_count=report(auto_capture)['train']+report(auto_capture)['holdout']
        ref=receipt('capture-disabled')
        recipes.capture(ref['run'],ref['producer'],ref['checker'],str(project),state)
        assert report(auto_capture)['train']+report(auto_capture)['holdout']==before_count
        with closing(sqlite3.connect(state / 'learning.sqlite')) as db, db:
            assert db.execute('SELECT value FROM exact_preserved').fetchone()[0] == 'unchanged'
            assert {row[0] for row in db.execute('SELECT DISTINCT source FROM recipe_v1_evidence')} == {'independent_checker'}
        passed.append('existing exact tables untouched; only independent_checker machine evidence stored')
        linkage = copy.deepcopy(recipe)
        linkage['features']['domain'] = 'lifecycle'
        linkage['applicability'] = {'domain': 'lifecycle'}
        linked_role = copy.deepcopy(role)
        linked_role.update(recipe_features=linkage['features'], recipe_confirmed=True, deliverable='target.py')
        linked_checker = copy.deepcopy(checker)
        linked_checker.update(name='mapping-check', mission='Check mapping boundary behavior', answers={'need':'mechanical_verification','difficulty':1,'divisible':0}, deliverable='verdict')
        linked_role['routine_check']='mapping-check'
        linked_roles = [linked_role, linked_checker]
        linked = register(body=linkage, current_role=linked_role, current_roles=linked_roles)
        ready(linked, 'lifecycle-ready', current_role=linked_role)
        call('activate', recipe_id=linked)

        def planned():
            with isolated_home(state):
                plan = adapter.build_plan({'task':'Fix fixed mapping', 'roles':linked_roles},
                    task_answers('everyday_implementation', 1, True), str(project), 'linkage', state)
            cell = next(c for w in plan['waves'] for c in w['calls'] if c['role_id']=='writer')
            assert cell['recipe_id']==linked and cell['policy_combo']=='Small', cell['recipe_evidence']
            return plan

        def dispatch(plan):
            return adapter.dispatch(plan['run_id'], 'writer', str(project), 'linkage', state)

        recovery = planned()
        recovery_id = recovery['run_id']
        original = copy.deepcopy(next(c for w in recovery['waves'] for c in w['calls'] if c['role_id']=='writer'))
        dispatch(recovery)
        adapter.record(recovery_id, 'writer', {'status':'FAILED', 'verification':['bounded failure']}, str(project), 'linkage', state)
        with adapter.database(state) as db:
            failed_plan = adapter.load_run(db, recovery_id, str(project), 'linkage')
        failed_cell = next(c for w in failed_plan['waves'] for c in w['calls'] if c['role_id']=='writer')
        for guard in ('trial_id', 'audit_delivery_token'):
            failed_cell[guard] = 'consumed'
            with adapter.database(state) as db:
                db.execute('UPDATE runs SET plan=? WHERE id=?', (json.dumps(failed_plan), recovery_id))
            for repair in (False, True):
                reject(lambda: adapter.escalate(recovery_id, 'writer', 'retry', str(project), 'linkage', repair=repair, state=state), 'retry forbidden')
            failed_cell.pop(guard)
        with adapter.database(state) as db:
            db.execute('UPDATE runs SET plan=? WHERE id=?', (json.dumps(failed_plan), recovery_id))
        escalated = adapter.escalate(recovery_id, 'writer', 'explicit next Combo', str(project), 'linkage', state=state)['call']
        assert escalated['policy_combo']=='Medium'
        recipes.validate_delivery(escalated, str(project), state)
        assert not any(key in escalated for key in ('recipe_id', 'recipe_role', 'recipe_roles', 'recipe_evidence', 'audit_delivery_token'))
        assert 'Untrusted approved recipe guidance' not in escalated['prompt'] and linkage['recipe_steps'][0] not in escalated['prompt']
        for key in ('write_scope', 'read_scope', 'acceptance', 'commands', 'role_answers', 'input_fingerprints', 'local_policy_snapshot'):
            assert escalated[key]==original[key], key
        next_admission = dispatch(recovery)
        adapter.ticket(next_admission['token'], str(project), state)
        adapter.record(recovery_id, 'writer', {'status':'FAILED', 'verification':['Medium failure']}, str(project), 'linkage', state)
        for index in range(2):
            repaired = adapter.escalate(recovery_id, 'writer', 'bounded repair', str(project), 'linkage', repair=True, state=state)['call']
            assert repaired['policy_combo']=='Medium'
            dispatch(recovery)
            adapter.record(recovery_id, 'writer', {'status':'FAILED', 'verification':['repair failed']}, str(project), 'linkage', state)
        reject(lambda: adapter.escalate(recovery_id, 'writer', 'third repair', str(project), 'linkage', repair=True, state=state), 'budget exhausted')
        with adapter.database(state) as db:
            assert db.execute('SELECT escalations,repairs FROM attempts WHERE run=? AND role=?', (recovery_id, 'writer')).fetchone()==(1,2)
            db.execute('INSERT INTO attempts VALUES(?,?,?,?)', (recovery_id, 'budget-fixture', 3, 0))
        reject(lambda: adapter.escalate(recovery_id, 'writer', 'fifth escalation', str(project), 'linkage', state=state), 'budget exhausted')
        passed.append('explicit recipe escalation admits Medium without recipe authority/guidance; original scope/criteria and trial/audit/run caps preserved')
        pending = planned()
        call('rollback', recipe_id=linked, reason='pending plan rollback')
        reject(lambda:dispatch(pending), 'recipe')
        call('activate', recipe_id=linked)
        admitted = dispatch(pending)
        hits = report(linked)['hits']
        adapter.ticket(admitted['token'], str(project), state)
        adapter.ticket(admitted['token'], str(project), state)
        assert report(linked)['hits']==hits
        call('suspend', recipe_id=linked, reason='ticket suspension')
        reject(lambda:adapter.ticket(admitted['token'], str(project), state), 'recipe')
        call('activate', recipe_id=linked)
        adapter.ticket(admitted['token'], str(project), state)
        newer = register(version=2, body=linkage, current_role=linked_role, current_roles=linked_roles)
        reject(lambda:adapter.ticket(admitted['token'], str(project), state), 'recipe')
        passed.append('recipe rollback blocks planned admission; suspension/new version blocks ticket; unchanged ticket consumes no hits')

        # Same profile/model, unrelated families: only source producer family owns capture.
        before = report(auto_capture)
        ref = receipt('family-specific-capture', current_role=linked_role)
        captured = recipes.capture(**ref, project=str(project), state=state)
        assert captured['captured']==2
        assert report(auto_capture)==before
        call('activate', recipe_id=auto_capture)
        with patch('crews.automation.audit_interval', return_value=1):
            intended = call('lookup', role=role, roles=roles)
        audit_ref = receipt('exact-family-audit', learned=auto_capture)
        with closing(sqlite3.connect(state/'learning.sqlite')) as db, db:
            db.execute("UPDATE recipe_audit_deliveries SET state='admitted',run=?,role=? WHERE token=?", (audit_ref['run'],'writer',intended['audit_delivery_token']))
            db.execute('UPDATE recipe_v1_recipes SET audit_pending=1 WHERE id=?', (rid,))
        assert recipes.capture(**audit_ref, project=str(project), state=state)['captured']==1
        assert report(auto_capture)['audits']==1 and not report(auto_capture)['audit_pending']
        assert report(rid)['audit_pending'] and report(rid)['audits']==1
        passed.append('authoritative producer family isolates nonlearned capture; exact learned recipe clears only its admitted audit')
        gc.collect()  # outcomes verifier uses sqlite context manager; collect its closed-scope handles.
    return passed


def math_close(left, right):
    return abs(left - right) < 1e-12


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS', 'checks': checks}, indent=2))
