"""Explicit independently attested run accounting; unknown is never zero."""
import json,math,time
from pathlib import Path
from crews.approval import authorize,consume


def attest(request,project,state):
 from crews.omp_adapter import database,canonical
 if not isinstance(request,dict) or request.get('confirmed') is not True:raise ValueError('accounting requires explicit confirmation')
 run=request.get('run');metrics=request.get('metrics')
 required={'cost','latency_ms','pricing_reference','includes'}
 if not isinstance(metrics,dict) or set(metrics)!=required:raise ValueError('complete accounting metrics required')
 for key in ('cost','latency_ms'):
  value=metrics[key]
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('finite nonnegative accounting required')
 if set(metrics['includes'])!={'producer','checker','classifier','main','repairs'} or not isinstance(metrics['pricing_reference'],str) or not metrics['pricing_reference'].strip():raise ValueError('complete cost components and pricing provenance required')
 nonce=authorize(request,project,state)
 with database(state) as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute('SELECT project FROM runs WHERE id=?',(run,)).fetchone()
  if not row or row[0]!=canonical(project):raise ValueError('accounting run/project mismatch')
  if db.execute("SELECT 1 FROM calls WHERE run=? AND status IN ('planned','admitted')",(run,)).fetchone():raise ValueError('accounting requires settled run')
  consume(db,nonce)
  db.execute('CREATE TABLE IF NOT EXISTS run_accounting(run TEXT PRIMARY KEY,metrics TEXT NOT NULL,attested REAL NOT NULL)')
  db.execute('INSERT INTO run_accounting VALUES(?,?,?)',(run,json.dumps(metrics),time.time()))
 return {'run':run,'accounting_verified':True}
