"""Isolated routing precedence and modern native proof regressions."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from crews import governance, omp_adapter as adapter, outcomes


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'oracle.py').write_text('assert True\n', encoding='utf-8')
        role = dict(name='produce-value', kind='produce', scope=['value.py'], inputs=['oracle.py'],
                    commands=['python oracle.py'], acceptance=['value correct'],
                    answers=dict(need='everyday_implementation', difficulty=1.5),
                    facts={**dict.fromkeys(adapter.BOUNDED_ROUTE['true_facts'], True),
                           **dict.fromkeys(adapter.BOUNDED_ROUTE['false_facts'], False)},
                    bounded_check=dict(input='oracle.py', command='python oracle.py'))
        policy = adapter.validate_policy(dict(provider='fixture', combos={
            combo: dict(model=combo.lower(), effort='High') for combo in adapter.COMBOS}))
        with patch.object(adapter, 'model_policy', return_value=policy), \
             patch('crews.automation.policy_snapshot', return_value=dict(epoch=7)), \
             patch('crews.automation.routing_policy', return_value={}) as routing:
            decision = adapter.routing_decision(role, project=root, roles=[role])
            assert decision['baseline_combo'] == 'Medium' and decision['final_combo'] == 'Small'
            assert decision['reasoning_effort'] == 'high'
            routing.return_value = dict(everyday_implementation='Medium')
            decision = adapter.routing_decision(role, project=root, roles=[role])
            assert decision['final_combo'] == 'Medium'
            assert decision['policy_source'] == 'legacy_force_preserve'
            assert decision['blocked_by'] == ['explicit_floor:Medium']
            routing.return_value = dict(everyday_implementation=dict(mode='baseline', combo='Medium'))
            assert adapter.effective_combo(role, project=root, roles=[role])[0] == 'Small'
            routing.return_value = dict(everyday_implementation=dict(mode='floor', combo='Large'))
            assert adapter.effective_combo(role, project=root, roles=[role])[0] == 'Large'
            routing.return_value = {}
            for key in adapter.BOUNDED_ROUTE['false_facts']:
                unsafe = {**role, 'facts': {**role['facts'], key: True}}
                assert adapter.effective_combo(unsafe, project=root, roles=[unsafe])[0] == 'Medium'
            for difficulty in (1.5001, True):
                unsafe = {**role, 'answers': {**role['answers'], 'difficulty': difficulty}}
                assert adapter.effective_combo(unsafe, project=root, roles=[unsafe])[0] == 'Medium'
            for scope in ([], ['a.py', 'b.py', 'c.py', 'd.py'], ['oracle.py']):
                unsafe = {**role, 'scope': scope}
                assert adapter.effective_combo(unsafe, project=root, roles=[unsafe])[0] == 'Medium'
        for entry in ({'mode': 'force', 'combo': 'Small'}, {'mode': 'baseline', 'combo': 'Small', 'floor': 'Large'}, None):
            try:
                governance.routing_entry(entry)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid routing entry accepted')
        cell = dict(provider='fixture', model='small', reasoning_effort='high', role_id='writer')
        result = dict(native=dict(exitCode=0, resolvedModel='fixture/small:high', resolvedThinkingLevel='high'),
                      wire=dict(provider='fixture', model='small', effort='high', role='writer'))
        assert outcomes.model_proof(cell, result)
        result['native']['resolvedModel'] = 'fixture/small:low'
        assert not outcomes.model_proof(cell, result)
        (root / 'nested').mkdir()
        (root / 'nested' / 'file').write_text('before', encoding='utf-8')
        before = outcomes.fingerprints(root, ['nested'])
        (root / 'nested' / 'file').write_text('after', encoding='utf-8')
        assert outcomes.fingerprints(root, ['nested']) != before
        checker = dict(name='check-value', kind='check', scope=[], inputs=['value.py', 'oracle.py'],
                       commands=['python oracle.py'], criteria=['value correct'])
        producer = {**role, 'commands': [], 'routine_check': 'check-value',
                    'answers': dict(need='everyday_implementation', difficulty=1)}
        assert adapter.small_eligibility(producer, root, [producer, checker], True)['eligible']
        assert not adapter.small_eligibility(producer, root, [producer], True)['eligible']
        writable = {**producer, 'scope': ['oracle.py']}
        assert not adapter.small_eligibility(writable, root, [writable, checker], True)['eligible']
        from crews.capability_trials import eligible
        frontier={**producer,'answers':dict(need='everyday_implementation',difficulty=1.5)}
        assert eligible(frontier,[frontier,checker],root)==[]
        for key in adapter.BOUNDED_ROUTE['true_facts']+adapter.BOUNDED_ROUTE['false_facts']:
            missing={**frontier,'facts':{k:v for k,v in frontier['facts'].items() if k!=key}}
            assert eligible(missing,[missing,checker],root)
        for value in (1,1.50001,True,float('nan')):
            bad={**frontier,'answers':dict(need='everyday_implementation',difficulty=value)}
            assert eligible(bad,[bad,checker],root)
        assert eligible({**frontier,'commands':['python oracle.py']},[frontier,checker],root)
        from crews.workflow_evaluation import capability_metrics
        baseline=dict(accepted=True,tokens=100,attempts=2,latency_ms=100)
        candidate=dict(accepted=True,tokens=80,attempts=2,latency_ms=110)
        records=dict(baseline=[baseline],candidate=[candidate])
        assert capability_metrics(records,'token-primary')['qualifies']
        assert not capability_metrics(records,'latency-primary')['qualifies']
        candidate['accepted']=False
        assert not capability_metrics(records,'token-primary')['qualifies']
        candidate.update(accepted=True,tokens=None,latency_ms=80)
        assert not capability_metrics(records,'token-primary')['qualifies']
        result=capability_metrics(records,'latency-primary')
        assert result['qualifies'] and result['token_efficiency']=='unknown' and result['benefit_scope']=='latency_only'
        candidate['attempts']=3
        assert not capability_metrics(records,'latency-primary')['qualifies']
    print('small learning routing/proof regressions passed')


if __name__ == '__main__':
    main()
