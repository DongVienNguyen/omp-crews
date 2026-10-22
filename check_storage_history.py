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
