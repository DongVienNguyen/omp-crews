"""Absolute operator latency ceiling never bypasses quality or missing evidence."""
from crews.workflow_evaluation import latency_gate
from check_workflow_accounting import run as signed_checks
from check_workflow_evaluation import run as boundary_checks


def run():
    baseline=dict(p95=224301.15866661072,latency_complete=True)
    candidate=dict(p95=391330.5678367615,latency_complete=True)
    absolute=dict(max_latency_ms=400000)
    assert latency_gate(baseline,candidate,absolute)
    assert not latency_gate(baseline,candidate,dict(max_latency_ratio=1.2))
    assert latency_gate(baseline,dict(p95=400000,latency_complete=True),absolute)
    assert not latency_gate(baseline,dict(p95=400000.001,latency_complete=True),absolute)
    for value in (None,True,float('nan'),float('inf'),-1):
        assert not latency_gate(baseline,dict(p95=value,latency_complete=True),absolute)
    assert not latency_gate(baseline,{**candidate,'latency_complete':False},absolute)
    assert not latency_gate({**baseline,'latency_complete':False},candidate,absolute)
    signed_checks('quality_only',max_latency_ms=400000)
    boundary_checks()
    print('PASS absolute400s inclusive boundary, missing/invalid latency refusal, ratio unchanged, signed absolute gate and original proof/quality guards')

if __name__=='__main__':run()
