"""Offline trust-boundary checks. No signing keys or provider spend required."""
import copy
import tempfile
from pathlib import Path
from unittest.mock import patch

from check_effort_policy import isolated_home
from crews import sdlc_api
from crews import workflow
from crews import workflow_evaluation as w


def reject(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('expected refusal')


def row(name, accepted, cost):
    return dict(id=name, family='integer', accepted=accepted, behavior='pass' if accepted else 'fail',
                false_complete=False, components={k: cost / len(w.COMPONENTS) for k in w.COMPONENTS},
                latency_ms=10, pricing_reference='test fixture; not verified pricing')


def run():
    baseline = [row('one', True, 2), row('two', False, 4)]
    candidate = [row('one', True, 1), row('two', False, 1)]
    preview = w.compare(baseline, candidate)
    assert preview['baseline']['cost_per_accepted'] == 6
    assert preview['candidate']['cost_per_accepted'] == 2
    assert preview['rollout'] == 'NO_GO' and not preview['authenticated']
    swapped = w.compare(baseline, [row('one', False, 1), row('two', True, 1)])
    assert not swapped['quality_gate']
    changed = copy.deepcopy(candidate)
    changed[0]['family'] = 'different'
    reject(lambda: w.compare(baseline, changed))
    reject(lambda: w.compare(baseline, candidate[:1]))
    reject(lambda: w.compare(baseline, candidate + candidate[:1]))
    unknown = copy.deepcopy(candidate)
    unknown[0]['behavior'] = 'unknown'
    unknown[0]['accepted'] = False
    assert not w.compare(baseline, unknown)['quality_gate']
    unknown = copy.deepcopy(candidate)
    unknown[0]['components']['governance'] = None
    assert w.summarize(unknown)['cost_per_accepted'] is None
    assert w.summarize([row('failed', False, 7)])['cost_per_accepted'] is None
    with tempfile.TemporaryDirectory(prefix='workflow-evaluation-') as folder, isolated_home(folder):
        send = lambda payload: sdlc_api.dispatch(dict(operation='evaluation', request=payload), folder, folder)
        reject(lambda: sdlc_api.dispatch(dict(operation='evaluation', baseline=baseline, candidate=candidate), folder, folder))
        absent = send(dict(operation='report', results=[]))
        assert absent['rollout'] == 'NO_GO' and not absent['accounting_complete']
        unit = dict(id='one', family='integer', source_group='original', split='holdout', expected_abstain=False,
                    before_hash='before', acceptance_hash='acceptance')
        policy = workflow._policy(folder, folder)
        arms = {arm: dict(profile=profile, model=policy['model'], policy=copy.deepcopy(policy), environment={'fixture': 'isolated'})
                for arm, profile in (('baseline', 'baseline'), ('candidate', 'sdlc_cost_aware'))}
        spec = dict(units=[unit], arms=arms, noninferiority_margin=0, max_latency_ratio=1.2, min_cost_reduction=.15)
        reject(lambda: send(dict(operation='freeze', spec=spec)))
        # Isolated verifier seam exercises persisted manifest behavior, not real operator approval.
        with patch.object(w, 'authorize', return_value='isolated-freeze-verifier-nonce-0001'):
            eid = send(dict(operation='freeze', spec=spec))['evaluation_id']
            from crews import evaluation
            # Generic evaluator must continue rejecting SDLC-only schema fields.
            with patch('crews.evaluation.authorize', return_value='generic-schema-nonce-0001'):
                reject(lambda: evaluation.dispatch(dict(operation='freeze', spec=spec), folder, folder))
            for key in ('profile', 'policy', 'model', 'environment'):
                wrong = copy.deepcopy(spec)
                wrong['arms']['candidate'][key] = 'wrong' if key in ('profile', 'model') else {'wrong': True}
                reject(lambda: send(dict(operation='freeze', spec=wrong)))
            empty = send(dict(operation='report', evaluation_id=eid, results=[]))
            assert empty['rollout'] == 'NO_GO' and len(empty['missing']) == 2
            refs = [dict(unit='one', arm=arm, workflow_id=arm, project=str(Path(folder) / arm)) for arm in ('baseline', 'candidate')]
            for ref in refs:
                Path(ref['project']).mkdir()
            def verified(db, reference, frozen, created, state, binding):
                return row('one', True, 2 if reference['arm'] == 'baseline' else 1), [], [], dict(attempts=3, evidence_hash='fixture')
            # Authenticated-record seam tests aggregation; never described as monetary rollout evidence.
            with patch.object(w, '_record', side_effect=verified):
                report = send(dict(operation='report', evaluation_id=eid, results=refs))
                assert report['rollout'] == 'GO' and report['candidate']['accepted'] == 1
                bad = copy.deepcopy(refs)
                bad[1]['workflow_id'] = bad[0]['workflow_id']
                reject(lambda: send(dict(operation='report', evaluation_id=eid, results=bad)))
                bad = copy.deepcopy(refs)
                bad[1]['unit'] = 'not-frozen'
                reject(lambda: send(dict(operation='report', evaluation_id=eid, results=bad)))
            metrics = dict(components={k: 1 for k in w.COMPONENTS}, latency_ms=10, pricing_reference='fixture',
                           coverage={k: True for k in ('all_attempts', 'main', 'governance', 'context')})
            reject(lambda: send(dict(operation='attest', workflow_id='baseline', evidence_hash='fake', metrics=metrics)))
            metrics['coverage']['context'] = False
            reject(lambda: send(dict(operation='attest', workflow_id='baseline', evidence_hash='fake', metrics=metrics)))
    print('PASS caller rows blocked, strict pairs/families, wrong profile/model/policy/environment freeze refused, generic evaluator schema unchanged, swapped pass regression, missing corpus/pricing, unsigned freeze/accounting refusal; aggregation seams not rollout receipts')


if __name__ == '__main__':
    run()
