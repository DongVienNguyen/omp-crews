"""Run offline boundary checks and signed host fixtures for both evaluation modes.

Quality-only signed spec = units, arms, noninferiority_margin,
max_latency_ratio, evaluation_mode='quality_only'. No min_cost_reduction,
prices, components, or accounting attestations required. Existing monetary spec
stays unchanged; explicit evaluation_mode='monetary' is also accepted.
"""
import copy

from check_workflow_accounting import run as signed_checks
from check_workflow_evaluation import reject, row, run as boundary_checks
from crews import workflow_evaluation as e


def run():
    boundary_checks()
    baseline = [row('one', True, 2), row('two', False, 4)]
    candidate = [row('one', True, 1), row('two', False, 1)]
    for record in baseline + candidate:
        record.update(components={}, pricing_reference='')
    preview = e.compare(baseline, candidate, 'quality_only')
    assert preview['quality_gate'] and preview['latency_gate']
    assert preview['cost_gate'] is None and preview['money_status'] == 'not_evaluated'
    assert preview['rollout'] == 'NO_GO' and not preview['authenticated']
    assert not e.compare(baseline, candidate)['latency_gate']
    swapped = [row('one', False, 1), row('two', True, 1)]
    assert not e.compare(baseline, swapped, 'quality_only')['quality_gate']
    unknown = copy.deepcopy(candidate)
    unknown[0].update(behavior='unknown', accepted=False)
    assert not e.compare(baseline, unknown, 'quality_only')['quality_gate']
    false_complete = copy.deepcopy(candidate)
    false_complete[0].update(false_complete=True, accepted=False)
    assert not e.compare(baseline, false_complete, 'quality_only')['quality_gate']
    for latency in (None, True, float('nan'), -1, 13):
        slow = copy.deepcopy(candidate)
        slow[0]['latency_ms'] = latency
        assert not e.compare(baseline, slow, 'quality_only')['latency_gate']
    reject(lambda: e.compare(baseline, candidate, 'unknown'))
    signed_checks()
    signed_checks('quality_only')
    print('PASS quality-only schema, unknown money, mandatory behavior, per-unit nonregression, latency gate, both signed modes; fixture proof not provider benchmark')


if __name__ == '__main__':
    run()
