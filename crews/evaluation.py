"""Frozen, operator-approved policy evaluation. No model score is accepted."""
import json,math,time
from pathlib import Path
from crews.approval import authorize,consume
from crews.outcomes import verified_pair,digest


def dispatch(request,project,state):
 from crews.omp_adapter import database,canonical
 if not isinstance(request,dict):raise ValueError('evaluation request required')
 op=request.get('operation');project=canonical(project)
 if op not in ('freeze','report'):raise ValueError('evaluation operation invalid')
 with database(state) as db:
  db.execute('CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,project TEXT,spec TEXT,created REAL)')
  db.execute('CREATE TABLE IF NOT EXISTS evaluation_approvals(id TEXT PRIMARY KEY,request TEXT NOT NULL)')
  if op=='freeze':
   nonce=authorize(request,project,state);spec=request.get('spec')
   if not isinstance(spec,dict) or set(spec)!={'units','noninferiority_margin','max_latency_ratio','min_cost_reduction'}:raise ValueError('evaluation frozen units and gates required')
   units=spec['units']
   if not isinstance(units,list) or not units:raise ValueError('evaluation units required')
   seen=set();groups={}
   for u in units:
    if not isinstance(u,dict) or set(u)!={'id','family','source_group','split','expected_abstain','before_hash','acceptance_hash'}:raise ValueError('strict frozen unit metadata required')
    if any(not isinstance(u[k],str) or not u[k] for k in ('id','family','source_group','before_hash','acceptance_hash')) or u['id'] in seen:raise ValueError('unique evaluation unit required')
    if u['split'] not in ('train','holdout') or type(u['expected_abstain']) is not bool:raise ValueError('unit split/abstain invalid')
    if u['source_group'] in groups and groups[u['source_group']]!=u['split']:raise ValueError('source family cannot cross split')
    seen.add(u['id']);groups[u['source_group']]=u['split']
   for key in ('noninferiority_margin','max_latency_ratio','min_cost_reduction'):
    v=spec[key]
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('finite gate required')
   if not 0<=spec['noninferiority_margin']<=.1 or not 1<=spec['max_latency_ratio']<=2 or not 0<=spec['min_cost_reduction']<1:raise ValueError('evaluation gates outside conservative limits')
   eid=digest({'project':project,'spec':spec});consume(db,nonce)
   db.execute('INSERT INTO evaluations VALUES(?,?,?,?)',(eid,project,json.dumps(spec),time.time()))
   db.execute('INSERT INTO evaluation_approvals VALUES(?,?)',(eid,json.dumps(request)))
   return {'evaluation_id':eid,'frozen':True}
  row=db.execute('SELECT spec,created FROM evaluations WHERE id=? AND project=?',(request.get('evaluation_id'),project)).fetchone()
  if not row:raise ValueError('evaluation not frozen in project')
  spec=json.loads(row[0])
  frozen_at=row[1]
  approval=db.execute('SELECT request FROM evaluation_approvals WHERE id=?',(request.get('evaluation_id'),)).fetchone()
  if not approval:raise ValueError('frozen evaluation signature missing')
  signed=json.loads(approval[0]);authorize(signed,project,state,accepted_at=frozen_at)
  if signed.get('spec')!=spec or digest({'project':project,'spec':spec})!=request['evaluation_id']:raise ValueError('frozen evaluation manifest changed')
 refs=request.get('results')
 if not isinstance(refs,list):raise ValueError('evaluation results list required')
 records={};used_runs=set();source_units={}
 for r in refs:
  if not isinstance(r,dict) or set(r)-{'unit','arm','run','producer','checker','project','abstained'} or r.get('arm') not in ('baseline','candidate'):raise ValueError('evaluation reference invalid')
  key=(r.get('unit'),r['arm'])
  if key in records:raise ValueError('duplicate evaluation arm')
  if not isinstance(r.get('run'),str) or r['run'] in used_runs:raise ValueError('evaluation run cannot be reused across arms or units')
  used_runs.add(r['run'])
  if not any(u['id']==r.get('unit') for u in spec['units']):raise ValueError('unfrozen evaluation unit')
  records[key]=r
 families={};missing=[];costs={'baseline':[],'candidate':[]};times={'baseline':[],'candidate':[]};abstain={'correct':0,'known':0,'total':0};violations=[]
 for u in [u for u in spec['units'] if u['split']=='holdout']:
  f=families.setdefault(u['family'],{'units':0,'baseline_pass':0,'candidate_pass':0,'baseline_delivered':0,'candidate_delivered':0});f['units']+=1
  for arm in ('baseline','candidate'):
   r=records.get((u['id'],arm))
   if not r:missing.append([u['id'],arm]);continue
   ep=canonical(r.get('project',project))
   if not Path(ep).is_relative_to(Path(project)):raise ValueError('evaluation snapshot escapes project')
   try:proof=verified_pair(r['run'],r['producer'],r['checker'],ep,state)
   except (ValueError,KeyError):missing.append([u['id'],arm]);continue
   ex=proof['execution']
   unit_identity=proof['unit_hash']
   if unit_identity in source_units and source_units[unit_identity]!=u['id']:raise ValueError('source evidence cannot count as multiple holdout units')
   source_units[unit_identity]=u['id']
   with database(state) as runs_db:
    started=runs_db.execute('SELECT created FROM runs WHERE id=?',(r['run'],)).fetchone()
   if not started or started[0]<=frozen_at:violations.append([u['id'],arm,'run_precedes_frozen_holdout']);continue
   abstain['total']+=1
   if type(ex.get('abstained')) is bool:abstain['known']+=1;abstain['correct']+=int(ex['abstained']==u['expected_abstain'])
   # This is router abstention, not a claim that the worker returned no artifact.
   if ex.get('before_hash')!=u['before_hash'] or ex.get('acceptance_hash')!=u['acceptance_hash']:violations.append([u['id'],arm,'frozen_contract_mismatch']);continue
   f[arm+'_pass']+=int(proof['behavior']=='pass');f[arm+'_delivered']+=int(proof.get('delivered',False))
   if proof['behavior']=='unknown':missing.append([u['id'],arm,'independent_behavior_unknown'])
   if not proof.get('delivered',False):missing.append([u['id'],arm,'execution_proof_incomplete'])
   if ex.get('claim_contradicted'):violations.append([u['id'],arm,'false_complete'])
   if ex.get('accounting_complete') is True:costs[arm].append(ex['cost']);times[arm].append(ex['latency_ms'])
 n=sum(f['units'] for f in families.values());quality=bool(n) and not missing and not violations and all(f['candidate_pass']/f['units']+spec['noninferiority_margin']>=f['baseline_pass']/f['units'] and f['candidate_delivered']==f['units'] and f['baseline_delivered']==f['units'] for f in families.values())
 complete=n>0 and all(len(costs[a])==n and len(times[a])==n for a in costs)
 def p95(v):return sorted(v)[math.ceil(.95*len(v))-1] if v else None
 latency=(p95(times['candidate'])<=p95(times['baseline'])*spec['max_latency_ratio']) if complete else None
 cost=(sum(costs['candidate'])<=sum(costs['baseline'])*(1-spec['min_cost_reduction'])) if complete else None
 abstain_ok=abstain['total']==2*n and abstain['known']==2*n and abstain['correct']==2*n
 return {'evaluation_id':request['evaluation_id'],'families':families,'missing':missing,'violations':violations,'abstention':abstain,'quality_gate':quality,'latency_gate':latency,'cost_gate':cost,'accounting_complete':complete,'p95':{a:p95(times[a]) for a in times},'accepted_task_cost':{a:sum(costs[a])/n if complete else None for a in costs},'selection':'candidate' if quality and latency and cost and abstain_ok else 'baseline','rollout':'GO' if quality and latency and cost and abstain_ok else 'NO_GO','unknown_is_zero':False}
