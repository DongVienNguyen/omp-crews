"""Offline real bridge subprocess check: escalation, stale evidence, launch and replay."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from crews import omp_adapter as a

ROOT = Path(__file__).resolve().parent
NODE = shutil.which('node')
assert NODE, 'Node.js is required for the extension bridge regression'
with tempfile.TemporaryDirectory() as tmp:
    project = Path(tmp) / 'project'
    project.mkdir()
    artifact = project / 'artifact.txt'
    artifact.write_text('verified source', encoding='utf-8')
    state = Path(tmp) / 'state'
    spec = {'task': 'Write artifact and verify artifact contents', 'roles': [
        {'name': 'artifact-producer', 'kind': 'produce', 'mission': 'Write artifact with stated contents',
         'deliverable': 'producer.json', 'scope': ['artifact.txt'], 'acceptance': ['Artifact contains verified source'],
         'answers': {'need': 'repeatable_task', 'difficulty': 0, 'divisible': 0, 'specific': 1}},
        {'name': 'artifact-checker', 'kind': 'check', 'mission': 'Verify artifact contents',
         'deliverable': 'checker.json', 'inputs': ['artifact.txt'], 'criteria': ['Artifact contains verified source'],
         'answers': {'need': 'mechanical_verification', 'difficulty': 0, 'divisible': 0, 'specific': 1}}]}
    answers = {'need': {'choice': 'repeatable_task', 'confidence': 1, 'probabilities': {'repeatable_task': 1}},
               'difficulty': {'score': 0}, 'divisible': {'noul': 0}, 'needs_verifier': {'noul': 1}}
    plan = a.build_plan(spec, answers, str(project), 'bridge-check', state)
    producer, checker = [w['calls'][0] for w in plan['waves']]
    def record(cell, status):
        a.admit(plan['run_id'], cell['role_id'], cell['prompt'], str(project), 'bridge-check', state)
        a.record(plan['run_id'], cell['role_id'], {'status': status, 'verification': ['Fixture evidence']}, str(project), 'bridge-check', state)
    record(producer, 'COMPLETE')
    record(checker, 'FAILED')
    raised = a.escalate(plan['run_id'], checker['role_id'], 'Checker fixture failure', str(project), 'bridge-check', False, state)['call']
    assert (raised['model'], raised['policy_combo'], raised['reasoning_effort']) == ('code-sol', 'Medium', 'low')
    request = {'op': 'dispatch', 'run': plan['run_id'], 'role': checker['role_id'], 'project': str(project), 'session': 'bridge-check'}
    def bridge():
        script = "import {callBridge} from " + json.dumps((ROOT / 'bridge-client.mjs').as_uri()) + ";\n"
        script += 'try { console.log(JSON.stringify(callBridge(' + json.dumps({'python': sys.executable, 'state': str(state)}) + ',' + json.dumps(str(ROOT)) + ',' + json.dumps(request) + '))); } catch(e) { console.error(e.message); process.exitCode=1; }'
        return subprocess.run([NODE, '--input-type=module', '-e', script], capture_output=True, text=True, encoding='utf-8', timeout=40,
                              env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    artifact.write_text('changed after producer', encoding='utf-8')
    failed = bridge()
    assert failed.returncode == 1
    assert 'Crews bridge dispatch: prior role evidence stale: artifact.txt' in failed.stderr, failed.stderr
    rows = a.results(plan['run_id'], str(project), 'bridge-check', state)
    assert next(r for r in rows if r['role_id'] == checker['role_id'])['status'] == 'planned'
    with a.database(state) as db:
        assert db.execute('SELECT count(*) FROM tickets').fetchone()[0] == 0
    artifact.write_text('verified source', encoding='utf-8')
    success = bridge()
    assert success.returncode == 0, success.stderr
    ticket = json.loads(success.stdout)
    assert ticket['call']['model'] == 'code-sol' and ticket['call']['reasoning_effort'] == 'low'
    replay = bridge()
    assert replay.returncode == 1 and 'unplanned, modified or already admitted dispatch' in replay.stderr, replay.stderr
print('PASS: escalated checker preserves stale-evidence refusal, exposes exact bridge error, launches when valid and rejects replay')
