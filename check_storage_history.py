"""Readback summaries and automatic retention throttle without touching real state."""
import json
import sqlite3
import tempfile
import time
from pathlib import Path
from crews import omp_adapter as a
from crews import maintenance, storage
from check_effort_policy import isolated_home

with tempfile.TemporaryDirectory() as temp, isolated_home(temp):
    root=Path(temp)
    summary={'roles':[{'role_id':'old-role','combo':'Small','model':'model','effort':'low','status':'completed','usage':{'input':12,'output':3},'duration_ms':100,'attempts':{'repairs':1,'escalations':0}}],'attempts':{'repairs':1,'escalations':0}}
    with a.database(temp) as db:
        db.execute(storage.SUMMARY_SCHEMA)
        db.execute('INSERT INTO run_summaries VALUES(?,?,?,?,?)',('a'*32,a.canonical(str(root)),'history',time.time()-8*86400,json.dumps(summary)))
    history=a.history(str(root),state=temp)
    assert history[0]['archived'] and history[0]['roles'][0]['status']=='completed'
    report=a.routing_report(str(root),temp)
    assert report['runs']==1 and report['native_usage']=={'input':12,'output':3,'durationMs':100}
    assert report['attempts']['repairs']==1
    assert report['bounded_small']==0 and report['by_requested_combo']=={'unknown':1}
    summary['roles'][0].update(requested_combo='Medium',effective_combo='Small',small_route='bounded',native_model_known=True)
    with a.database(temp) as db:
        db.execute('UPDATE run_summaries SET summary=?',(json.dumps(summary),))
    report=a.routing_report(str(root),temp)
    assert report['bounded_small']==1 and report['by_requested_combo']=={'Medium':1}
    assert report['by_execution_evidence']=={'native_model_known':1}
    legacy_cell={'role_id':'legacy-bounded','policy_combo':'Small','bounded_small':True}
    archived=storage._summary({'waves':[{'calls':[legacy_cell]}]},[],[])
    assert archived['roles'][0]['bounded_small'] is True
    archived['roles'].append({'role_id':'known-normal','combo':'Medium','small_route':None,'usage':{}})
    with a.database(temp) as db:
        db.execute('UPDATE run_summaries SET summary=?',(json.dumps(archived),))
    report=a.routing_report(str(root),temp)
    assert report['bounded_small']==1 and report['small_routes']=={'bounded':1,'none':1}
    try:
        with a.database(temp) as db:a.load_run(db,'a'*32,str(root),'history')
    except ValueError as error:assert 'archived' in str(error)
    else:raise AssertionError('Archived history cannot be replayed')
    first=maintenance.run(temp)
    assert first['operation']=='cleanup'
    assert maintenance.run(temp)=={'skipped':'throttled'}
    (root/'storage.json').write_text('{"auto_cleanup":false}')
    assert maintenance.run(temp)=={'skipped':'disabled'}
print('PASS: archived summaries remain reportable/not executable; maintenance throttles and opt-out works')
