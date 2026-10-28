"""Restart-safe run slots: never overwrite an existing plan or replay admitted work."""
import json,os,time
from pathlib import Path
from crews.outcomes import fingerprints,digest


def dispatch(request,project,state=None):
 from crews import omp_adapter as a
 if not isinstance(request,dict):raise ValueError('runner request required')
 if 'workflow' in request or request.get('operation') in ('workflow_prepare','workflow_status','workflow_next','workflow_recheck','workflow_recover'):
  from crews.workflow import dispatch as workflow_dispatch
  return workflow_dispatch(request,project,state)
 project=a.canonical(project);slot=request.get('slot');op=request.get('operation')
 if not isinstance(slot,str) or not slot or len(slot)>120 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in slot):raise ValueError('runner slot must be bounded identifier')
 root=Path(state or a.home());manifest=root/'runner'/ (slot+'.json')
 if op=='prepare':
  if request.get('confirmed') is not True:raise ValueError('runner prepare requires explicit confirmation')
  if manifest.exists():
   prior=json.loads(manifest.read_text(encoding='utf-8'))
   expected=digest({'project':project,'spec':request.get('spec'),'answers':request.get('answers'),'session':request.get('session')})
   if prior.get('identity')!=expected:raise ValueError('runner slot request changed; new explicit slot required')
   return inspect(manifest,project,root)
  spec=request.get('spec');answers=request.get('answers');session=request.get('session')
  if not isinstance(spec,dict) or not isinstance(session,str):raise ValueError('runner requires complete canonical spec/session')
  paths=list(dict.fromkeys(p for role in spec.get('roles',[]) for p in (role.get('scope') or [])+(role.get('inputs') or [])))
  before=fingerprints(project,paths);identity=digest({'project':project,'spec':spec,'answers':answers,'session':session})
  manifest.parent.mkdir(parents=True,exist_ok=True)
  # Reservation is persisted before planning; crash leaves an explicit blocker, not a duplicate run.
  value={'version':1,'project':project,'identity':identity,'before':before,'run':None,'session':session,'reserved_at':time.time()}
  try:
   with manifest.open('x',encoding='utf-8') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
  except FileExistsError:
   prior=json.loads(manifest.read_text(encoding='utf-8'))
   if prior.get('identity')!=identity:raise ValueError('runner concurrent request identity mismatch')
   return inspect(manifest,project,root)
  plan=a.prepare_plan(spec,answers,project,session,root)
  value['run']=plan['run_id'];pending=manifest.with_suffix('.pending')
  with pending.open('w',encoding='utf-8') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
  os.replace(pending,manifest)
  return inspect(manifest,project,root)
 if op=='status':return inspect(manifest,project,root)
 raise ValueError('runner operation must be prepare/status; execution only via returned native crew reference')


def inspect(manifest,project,state):
 from crews import omp_adapter as a
 if not manifest.is_file():return {'exists':False,'next':None,'replay':False}
 value=json.loads(manifest.read_text(encoding='utf-8'))
 if value.get('project')!=project:raise ValueError('runner slot belongs to another project')
 if not value.get('run'):return {'exists':True,'blocked':'reservation_without_run; inspect recorded plan history before explicit recovery','next':None,'replay':False}
 rows=a.results(value['run'],project,value['session'],state)
 if any(r['status']=='admitted' for r in rows):return {'exists':True,'run':value['run'],'blocked':'admitted_role_requires_explicit_recovery','roles':rows,'next':None,'replay':False}
 if any(r['status']=='failed' for r in rows):return {'exists':True,'run':value['run'],'blocked':'failed_role_requires_explicit_repair_or_escalation','roles':rows,'next':None,'replay':False}
 with a.database(state) as db:plan=a.load_run(db,value['run'],project,value['session'])
 statuses={r['role_id']:r['status'] for r in rows}
 for wave in plan['waves']:
  for call in wave['calls']:
   if statuses[call['role_id']]=='planned':return {'exists':True,'run':value['run'],'next':{'run':value['run'],'role':call['role_id'],'session':value['session']},'roles':rows,'replay':False}
 return {'exists':True,'run':value['run'],'complete':True,'roles':rows,'next':None,'replay':False}
