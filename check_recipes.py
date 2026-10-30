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

from crews import outcomes, recipes
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
    with tempfile.TemporaryDirectory(prefix='crews-recipes-') as directory:
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
        binding = outcomes.digest({'provider': 'test', 'model': 'small-v1', 'effort': 'medium', 'policy': 'policy-v1'})
        profile = {'input': 'verify.py', 'command': command}
        facts = {**dict.fromkeys(recipes.TRUE_FACTS, True), **dict.fromkeys(recipes.FALSE_FACTS, False),
                 'deterministic_check': True}
        role = {'name': 'writer', 'kind': 'produce', 'mission': 'Fix serialization mapping',
                'scope': ['target.py'], 'inputs': ['target.py'], 'commands': [],
                'answers': {'need': 'everyday_implementation', 'difficulty': 1, 'divisible': 0},
                'facts': facts, 'routine_check': 'verifier', 'acceptance': [invariant],
                'recipe_features': features, 'recipe_profile': profile, 'model_binding': binding}
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

        def receipt(unit, behavior='pass', model='small-v1', learned=False, filename='target.py', execution='completed'):
            """Persist synthetic admitted receipt; real verifier validates linkage/hashes."""
            rid = hashlib.sha256((unit + str(receipt.count)).encode()).hexdigest()
            receipt.count += 1
            pinned = outcomes.profile(checker, str(project), roles)
            producer = {'role_id': 'writer', 'agent_type': 'crew-produce-test', 'provider': 'test',
                        'model': model, 'policy_combo': 'Small', 'reasoning_effort': 'medium', 'routing_policy_version': 'policy-v1',
                        'write_scope': [filename], 'acceptance': [invariant],
                        'input_fingerprints': {'before': 'source-'+unit}, 'evidence_unit': unit}
            if learned:
                producer['recipe_id'] = 'learned-recipe'
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
            state.mkdir(exist_ok=True)
            with closing(sqlite3.connect(state / 'runs.sqlite')) as db, db:
                db.executescript('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,project TEXT,plan TEXT);'
                                 'CREATE TABLE IF NOT EXISTS calls(run TEXT,role TEXT,status TEXT,result TEXT);')
                from crews.attempt_ledger import initialize
                initialize(db)
                from crews.omp_adapter import canonical
                db.execute('INSERT INTO runs VALUES(?,?,?)', (rid, canonical(str(project)), json.dumps({'waves': [
                    {'calls': [producer]}, {'calls': [check_cell]}]})))
                db.execute('INSERT INTO calls VALUES(?,?,?,?)', (rid, 'writer', 'completed', json.dumps(producer_result)))
                db.execute('INSERT INTO calls VALUES(?,?,?,?)', (rid, 'verifier', 'completed' if behavior != 'unknown' else 'failed', json.dumps(checker_result)))
                import time
                for cell,value,status in [(producer,producer_result,'completed'),(check_cell,checker_result,'completed' if behavior!='unknown' else 'failed')]:
                    db.execute('INSERT INTO execution_attempts(run,role,ordinal,project,fault,is_repair,combo,cell,result,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,cell['role_id'],1,canonical(str(project)),'fixture',0,cell.get('policy_combo','Large'),json.dumps(cell),json.dumps(value),time.time()))
            return {'run': rid, 'producer': 'writer', 'checker': 'verifier'}
        receipt.count = 0

        def evidence(rid, unit, split='train', **kwargs):
            return call('evidence', recipe_id=rid, split=split, **receipt(unit, **kwargs))

        def ready(rid, prefix):
            for index in range(3):
                evidence(rid, prefix + '-train-' + str(index))
            for index in range(2):
                evidence(rid, prefix + '-holdout-' + str(index), 'holdout')

        assert recipes.match(role, str(project), roles, state)['mode'] == 'shadow'
        assert not state.exists(), 'read-only lookup created state'
        for confirmation in (None, False, 1, 'true'):
            reject(lambda: recipes.dispatch({'operation': 'configure', 'confirmed': confirmation, 'mode': 'on'}, str(project), state), 'confirmed')
        assert not state.exists()
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
        fresh_ref=receipt('fresh-audit',learned=True)
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
        gc.collect()  # outcomes verifier uses sqlite context manager; collect its closed-scope handles.
    return passed


def math_close(left, right):
    return abs(left - right) < 1e-12


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS', 'checks': checks}, indent=2))
