"""Execution failure pauses governance without inventing a Large denial."""
import tempfile
from check_effort_policy import isolated_home
from crews import automation as auto, omp_adapter as a

with tempfile.TemporaryDirectory(prefix='crews-governance-failure-') as folder, isolated_home(folder):
    auto.install(folder)
    ref = auto.next_review(folder, folder)
    admitted = a.dispatch(ref['run'], ref['role'], folder, ref['session'], folder)
    a.record(ref['run'], ref['role'], dict(status='FAILED', failure_kind='cancelled',
             verification=['admission lease expired']), folder, ref['session'], folder,
             host_key=admitted['host_key'])
    blocked = auto.next_review(folder, folder)
    assert blocked == {'blocked': 'recorded governance review failed: cancelled'}, blocked
    status = auto.dispatch(dict(operation='status'), folder, folder)
    assert status['grants'][0]['live'] is False
    assert auto.next_review(folder, folder) is None, 'Failed review must not auto-replay'
    assert 'denial' not in status['jobs'][0]['result']
print('PASS: cancelled governance pauses authority, preserves failure kind, never replays or fabricates denial')
