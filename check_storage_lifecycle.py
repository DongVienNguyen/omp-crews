"""Real SQLite admission/receipt/record handoff without JSON ticket proliferation."""
import json
from pathlib import Path
import tempfile
from crews import omp_adapter as a
from check_effort_policy import isolated_home, role, task_answers

with tempfile.TemporaryDirectory() as directory, isolated_home(directory):
    root=Path(directory)
    producer=role('repeatable_task',0,'produce',name='artifact-writer')
    reader=role('bounded_retrieval',1,'research',name='artifact-reader')
    # Producer before integrator creates an actual earlier-record context handoff.
    reader['kind']='integrate';reader['scope']=['integrated.txt']
    spec={'task':'Inspect Combo model and effort policy','roles':[producer,reader]}
    answers=task_answers('repeatable_task',2);answers['divisible']={'noul':1}
    plan=a.build_plan(spec,answers,directory,'compact-storage',directory)
    first=next(c for w in plan['waves'] for c in w['calls'] if c['role_id']=='artifact-writer')
    second=next(c for w in plan['waves'] for c in w['calls'] if c['role_id']=='artifact-reader')
    with a.database(directory) as db:
        db.execute("CREATE TRIGGER refuse_admission BEFORE INSERT ON admissions BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    try:a.dispatch(plan['run_id'],first['role_id'],directory,'compact-storage',directory)
    except a.sqlite3.IntegrityError:pass
    else:raise AssertionError('Expected fixture admission failure')
    with a.database(directory) as db:
        assert db.execute('SELECT status FROM calls WHERE run=? AND role=?',(plan['run_id'],first['role_id'])).fetchone()[0]=='planned'
        assert db.execute('SELECT count(*) FROM tickets').fetchone()[0]==0
        db.execute('DROP TRIGGER refuse_admission')
    ticket=a.dispatch(plan['run_id'],first['role_id'],directory,'compact-storage')
    assert not (root/'tickets').exists()
    assert a.ticket(ticket['token'],directory)['call']['role_id']==first['role_id']
    proof={'model':first['model'],'effort':first['reasoning_effort'],'provider':first['provider'],'role':first['role_id'],'token':ticket['token'],'time':1}
    a.store_receipt(ticket['token'],directory,proof)
    assert a.receipt(ticket['token'],directory)==proof
    assert not (root/'wire').exists()
    a.record(plan['run_id'],first['role_id'],{'status':'COMPLETE','verification':['Artifact verified']},directory,'compact-storage')
    record=Path(plan['records'][first['role_id']])
    assert not record.exists(), 'No duplicate JSON materialized until a later wave requires it'
    try:a.ticket(ticket['token'],directory)
    except ValueError:pass
    else:raise AssertionError('Recorded role ticket must be inactive')
    a.admit(plan['run_id'],second['role_id'],second['prompt'],directory,'compact-storage',directory)
    assert record.is_file()
    assert json.loads(record.read_text())['status']=='COMPLETE'
    with a.database(directory) as db:
        assert db.execute('SELECT count(*) FROM admissions').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM receipts').fetchone()[0]==0
    print('PASS: compact SQLite ticket/receipt, revoked completion, lazy record handoff and no JSON proliferation')
