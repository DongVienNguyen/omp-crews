"""Append-only execution evidence and fault strikes; latest calls remain a view."""
import json,time
from crews.outcomes import digest

SCHEMA='''
CREATE TABLE IF NOT EXISTS execution_attempts(id INTEGER PRIMARY KEY,run TEXT NOT NULL,role TEXT NOT NULL,ordinal INTEGER NOT NULL,project TEXT NOT NULL,workflow TEXT,node TEXT,fault TEXT NOT NULL,is_repair INTEGER NOT NULL,combo TEXT NOT NULL,cell TEXT NOT NULL,result TEXT NOT NULL,created REAL NOT NULL,UNIQUE(run,role,ordinal));
CREATE TABLE IF NOT EXISTS fault_strikes(project TEXT NOT NULL,fault TEXT NOT NULL,attempt INTEGER NOT NULL UNIQUE,checker_run TEXT NOT NULL,checker_role TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS fault_verdicts(attempt INTEGER NOT NULL,project TEXT NOT NULL,fault TEXT NOT NULL,criterion TEXT NOT NULL,status TEXT NOT NULL,checker_run TEXT NOT NULL,checker_role TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(attempt,criterion,checker_run,checker_role));
CREATE TRIGGER IF NOT EXISTS execution_attempts_no_update BEFORE UPDATE ON execution_attempts BEGIN SELECT RAISE(ABORT,'attempt history immutable'); END;
CREATE TRIGGER IF NOT EXISTS execution_attempts_no_delete BEFORE DELETE ON execution_attempts BEGIN SELECT RAISE(ABORT,'attempt history immutable'); END;
'''


def initialize(db):db.executescript(SCHEMA)


def fault_key(cell):
    return digest({'acceptance':sorted(set(cell.get('acceptance',[]))),'targets':sorted(set(cell.get('write_scope') or []))})


def strikes(db,project,cell):
    rows=db.execute("SELECT count(DISTINCT v.attempt) FROM fault_verdicts v JOIN execution_attempts a ON a.id=v.attempt WHERE v.project=? AND v.fault=? AND v.status='fail' AND a.is_repair=1 AND a.combo='Medium' AND v.created>coalesce((SELECT max(p.created) FROM fault_verdicts p WHERE p.project=v.project AND p.fault=v.fault AND p.criterion=v.criterion AND p.status='pass'),0) GROUP BY v.criterion",(project,fault_key(cell))).fetchall()
    return max((r[0] for r in rows),default=0)


def guard(db,project,cell):
    if cell.get('policy_combo')=='Medium' and strikes(db,project,cell)>=2:raise ValueError('two behavioral Medium repairs failed for this fault; Large required')


def record(db,run,role,project,cell,result):
    prior=db.execute('SELECT count(*) FROM execution_attempts WHERE run=? AND role=?',(run,role)).fetchone()[0]
    counters=db.execute('SELECT repairs FROM attempts WHERE run=? AND role=?',(run,role)).fetchone()
    previous=db.execute("SELECT v.status FROM fault_verdicts v WHERE v.project=? AND v.fault=? AND v.created=(SELECT max(p.created) FROM fault_verdicts p WHERE p.project=v.project AND p.fault=v.fault AND p.criterion=v.criterion)",(project,fault_key(cell))).fetchall()
    is_repair=bool(counters and counters[0]>0 or any(r[0]=='fail' for r in previous))
    db.execute('INSERT INTO execution_attempts(run,role,ordinal,project,workflow,node,fault,is_repair,combo,cell,result,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run,role,prior+1,project,cell.get('workflow_id'),cell.get('node_id'),fault_key(cell),int(is_repair),cell['policy_combo'],json.dumps(cell),json.dumps(result),time.time()))
    if not result.get('host_authenticated') or result.get('outcome',{}).get('behavior') not in ('pass','fail'):return
    targets=[dict(run=run,role=target) for target in cell.get('verify_targets') or []]+list(cell.get('workflow_targets') or [])
    verdicts=result.get('outcome',{}).get('verification',{}).get('criteria') or result.get('criterion_results') or []
    for target in targets:
        attempt=db.execute('SELECT id,fault,is_repair,combo,cell FROM execution_attempts WHERE run=? AND role=? ORDER BY ordinal DESC LIMIT 1',(target['run'],target['role'])).fetchone()
        if not attempt:continue
        producer=json.loads(attempt[4]);criteria=producer.get('acceptance') or []
        own=[v for v in verdicts if isinstance(v,dict) and v.get('criterion') in criteria and v.get('status') in ('pass','fail')]
        if len({v['criterion'] for v in own})!=len(set(criteria)) or not criteria:continue
        behavior='fail' if any(v['status']=='fail' for v in own) else 'pass'
        for verdict in own:
            db.execute('INSERT OR IGNORE INTO fault_verdicts VALUES(?,?,?,?,?,?,?,?)',(attempt[0],project,attempt[1],verdict['criterion'],verdict['status'],run,role,time.time()))
        prior=db.execute('SELECT result FROM calls WHERE run=? AND role=?',(target['run'],target['role'])).fetchone()
        if prior and prior[0]:
            value=json.loads(prior[0]);outcome=value.setdefault('outcome',{});outcome.update(independent_behavior=behavior,checker_run=run,checker_role=role,claim_contradicted=value.get('producer_claim',value.get('status'))=='COMPLETE' and behavior=='fail')
            db.execute('UPDATE calls SET result=? WHERE run=? AND role=?',(json.dumps(value),target['run'],target['role']))
        if attempt[2] and attempt[3]=='Medium' and behavior=='fail':db.execute('INSERT OR IGNORE INTO fault_strikes VALUES(?,?,?,?,?,?)',(project,attempt[1],attempt[0],run,role,time.time()))


def report(db,project,workflow=None):
    args=[project];where='project=?'
    if workflow is not None:where+=' AND workflow=?';args.append(workflow)
    rows=db.execute('SELECT combo,result,is_repair FROM execution_attempts WHERE '+where,args).fetchall()
    usage={k:{'known':0,'unknown':0,'total':0} for k in ('input','output','cacheRead','cacheWrite','durationMs')}
    by_combo={};outcomes={}
    for combo,raw,repair in rows:
        result=json.loads(raw);native=result.get('native') or {};metrics=native.get('usage') or {};by_combo[combo]=by_combo.get(combo,0)+1
        execution=result.get('outcome',{}).get('execution','unknown');outcomes[execution]=outcomes.get(execution,0)+1
        for key,coverage in usage.items():
            value=native.get(key) if key=='durationMs' else metrics.get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and 0<=value<float('inf'):coverage['known']+=1;coverage['total']+=value
            else:coverage['unknown']+=1
    return dict(population='immutable provider attempts, not latest roles',attempts=len(rows),by_combo=by_combo,outcomes=outcomes,usage=usage,main_orchestration='unknown',pricing='unverified')
