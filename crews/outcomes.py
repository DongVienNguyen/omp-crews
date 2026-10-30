"""Behavior evidence derived from admitted checker receipts, never producer claims."""
import hashlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path
from contextlib import closing

SCHEMA_VERSION = 1
EXECUTIONS = {'completed','provider_error','tool_error','cancelled','interrupted','schema_error','task_failed','dispatch_error'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def fingerprints(project, paths):
    root=Path(project).resolve();result={}
    def fingerprint(path, ancestors=frozenset()):
        try:resolved=path.resolve()
        except (OSError,RuntimeError) as exc:raise ValueError('evidence link cycle') from exc
        if not resolved.is_relative_to(root):raise ValueError('evidence path escapes project via link')
        link=os.readlink(path) if path.is_symlink() else None
        if resolved.is_dir():
            if resolved in ancestors:raise ValueError('evidence link cycle')
            children=[]
            for child in sorted(path.iterdir(),key=lambda item:item.name):
                kind='link' if child.is_symlink() else 'directory' if child.is_dir() else 'file'
                children.append([child.name,kind,fingerprint(child,ancestors|{resolved})])
            value='directory:'+digest(children)
        elif resolved.is_file():
            with resolved.open('rb') as source:value=hashlib.file_digest(source,'sha256').hexdigest()
        elif not resolved.exists():value=None
        else:raise ValueError('unsupported evidence file type')
        return digest(['link',link,value]) if link is not None else value
    for name in dict.fromkeys(paths):
        if not isinstance(name,str) or not name or ':' in name:raise ValueError('evidence path must be local')
        path=Path(name.replace('\\','/'))
        if path.is_absolute() or '..' in path.parts:raise ValueError('evidence path escapes project')
        result[name]=fingerprint(root/path)
    return result


def profile(role, project, roles):
    value=role.get('checker_profile')
    if value is None:return None
    if role.get('kind')!='check' or not isinstance(value,dict) or set(value)!={'input','command','version'}:
        raise ValueError('checker_profile requires read-only check role and input/command/version')
    from crews.omp_adapter import explicit_file
    if not explicit_file(value['input']) or not isinstance(value['version'],str) or not value['version'].strip():
        raise ValueError('checker_profile input/version invalid')
    if value['input'] not in (role.get('inputs') or []) or value['command'] not in (role.get('commands') or []):
        raise ValueError('checker_profile must be an admitted input and command')
    import shlex
    command=value['command']
    if any(char in command for char in ';|><`$&\n\r'):raise ValueError('checker profile shell syntax forbidden')
    argv=shlex.split(command);args=argv[1:]
    while args and args[0] in ('-B','-I','-u'):args=args[1:]
    if not argv or Path(argv[0]).name.lower().removesuffix('.exe') not in ('python','python3','node','bun') or not args or args[0].startswith('-') or args[0]!=value['input']:raise ValueError('checker profile requires direct admitted script')
    root=Path(project).resolve();script=(root/value['input']).resolve()
    if not script.is_relative_to(root) or not script.is_file():raise ValueError('checker profile script missing')
    for writer in roles:
        if writer.get('kind') not in ('produce','integrate'):continue
        for name in writer.get('scope') or []:
            target=(root/name).resolve()
            if script==target or script.is_relative_to(target):raise ValueError('checker profile is writable')
    return {**value,'sha256':fingerprints(project,[value['input']])[value['input']],'criteria':list(role.get('criteria') or [])}


def model_proof(cell,result):
    n=result.get('native') or {};w=result.get('wire') or {}
    model=cell.get('provider','9router')+'/'+cell.get('model','')
    return (n.get('exitCode')==0 and type(n.get('exitCode')) is int and
            n.get('resolvedModel') in (model,model+':'+cell.get('reasoning_effort','off')) and
            n.get('resolvedThinkingLevel')==cell.get('reasoning_effort') and
            w.get('model')==cell.get('model') and w.get('provider')==cell.get('provider') and
            w.get('effort')==cell.get('reasoning_effort') and w.get('role')==cell.get('role_id'))


def derive(cell,result,project):
    execution=result.get('failure_kind') or ('completed' if result.get('status')=='COMPLETE' else 'task_failed')
    if execution not in EXECUTIONS:execution='task_failed'
    observed=result.get('tool_receipts') or []
    if any(r.get('error') for r in observed):execution='tool_error' if execution!='cancelled' else execution
    p=cell.get('checker_profile');behavior='unknown';verification={'kind':'unverified','criteria':[]}
    verdicts=None
    if p and model_proof(cell,result):
        current=fingerprints(project,[p['input']]).get(p['input'])
        receipts=[r for r in observed if r.get('source')=='host_profile' and r.get('command')==p['command'] and r.get('profile_hash')==digest(p) and r.get('role')==cell['role_id'] and r.get('artifacts')==fingerprints(project,list(dict.fromkeys(cell['write_scope']+cell.get('read_scope',[]))))]
        valid=bool(receipts) and type(receipts[-1].get('exit_code')) is int
        if receipts:verdicts=receipts[-1].get('criterion_results')
        criteria=p['criteria']
        exact=isinstance(verdicts,list) and len(verdicts)==len(criteria) and all(isinstance(v,dict) and set(v)=={'criterion','status'} and v['criterion']==c and v['status'] in ('pass','fail') for v,c in zip(verdicts,criteria))
        if current==p['sha256'] and valid and exact and criteria:
            behavior='fail' if receipts[-1]['exit_code']!=0 or any(v['status']=='fail' for v in verdicts) else 'pass'
            verification={'kind':'independent_executable','profile_hash':digest(p),'script_hash':p['sha256'],'criteria':verdicts,'command_receipts':receipts}
    usage=(result.get('native') or {}).get('usage') or {}
    cost={k:usage.get(k) if isinstance(usage.get(k),(int,float)) and not isinstance(usage.get(k),bool) and math.isfinite(usage[k]) and usage[k]>=0 else None for k in ('input','output','cacheRead','cacheWrite')}
    return {'version':SCHEMA_VERSION,'execution':execution,'behavior':behavior,'verification':verification,
            'process_claim':result.get('producer_claim',result.get('status')),'cost':{'child':cost,'main_orchestration':None,'pricing_verified':False},'recorded_at':time.time()}


def verified_pair(run,producer,checker,project,state=None):
    from crews.omp_adapter import home,canonical
    root=Path(state or home());db=root/'runs.sqlite'
    if not db.is_file():raise ValueError('verified pair run missing')
    with closing(sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        row=c.execute('SELECT project,plan FROM runs WHERE id=?',(run,)).fetchone()
        if not row or row[0]!=canonical(project):raise ValueError('verified pair project/run mismatch')
        plan=json.loads(row[1]);cells={x['role_id']:(i,x) for i,w in enumerate(plan['waves']) for x in w['calls']}
        checker_ref=checker if isinstance(checker,dict) else {'run':run,'role':checker}
        checker_run=checker_ref.get('run');checker=checker_ref.get('role')
        if producer not in cells:raise ValueError('verified pair producer missing')
        pi,p=cells[producer]
        if checker_run==run:
            if checker not in cells:raise ValueError('verified pair checker missing')
            ci,ch=cells[checker]
            if ci<=pi or producer not in ch.get('verify_targets',[]):raise ValueError('independent later checker required')
        else:
            other=c.execute('SELECT project,plan FROM runs WHERE id=?',(checker_run,)).fetchone()
            if not other or other[0]!=canonical(project):raise ValueError('verified checker project/run mismatch')
            ch=next((x for w in json.loads(other[1])['waves'] for x in w['calls'] if x['role_id']==checker),None)
            if not ch or not p.get('workflow_id') or ch.get('workflow_id')!=p['workflow_id'] or {'run':run,'role':producer} not in ch.get('workflow_targets',[]):raise ValueError('checker workflow linkage missing')
            from crews.workflow import _manifest,_validate_frozen,_validate_artifacts,_rows
            manifest=_manifest(c,p['workflow_id']);_validate_frozen(manifest,project,state);_validate_artifacts(c,manifest)
            if _rows(c,manifest)[ch['node_id']]['state'] not in ('completed','failed'):raise ValueError('checker invalidated or incomplete')
        if not p['agent_type'].startswith(('crew-produce-','crew-integrate-')) or not ch['agent_type'].startswith('crew-check-') or ch.get('write_scope'):raise ValueError('independent read-only checker required')
        if not set(p.get('acceptance') or [])<=set(ch.get('acceptance') or []) or not set(p['write_scope'])<=set(ch.get('read_scope') or []):raise ValueError('checker original acceptance/artifacts missing')
        values={};attempt_refs={}
        for name,cell,ref_run,key in [(producer,p,run,'producer'),(checker,ch,checker_run,'checker')]:
            r=c.execute('SELECT status,result FROM calls WHERE run=? AND role=?',(ref_run,name)).fetchone()
            if not r or not r[1]:raise ValueError('verified pair missing result')
            result=json.loads(r[1]);values[key]=(r[0],result)
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='execution_attempts'").fetchone():
                attempt=c.execute('SELECT id,created,cell,result FROM execution_attempts WHERE run=? AND role=? ORDER BY ordinal DESC LIMIT 1',(ref_run,name)).fetchone()
                if not attempt:raise ValueError('verified pair attempt missing')
                frozen_cell=json.loads(attempt[2]);frozen_result=json.loads(attempt[3])
                if frozen_cell!=cell or any(frozen_result.get(k)!=result.get(k) for k in ('native','wire','fingerprints','host_authenticated','status')):raise ValueError('latest result differs from immutable attempt')
                if key=='checker' and checker_ref.get('attempt',attempt[0])!=attempt[0]:raise ValueError('checker attempt reference stale')
                attempt_refs[key]={'run':ref_run,'role':name,'attempt':attempt[0],'created':attempt[1]}
            if not model_proof(cell,result):raise ValueError('verified pair model proof missing')
            if not result.get('host_authenticated'):raise ValueError('verified pair lacks authenticated host completion')
            expected=result.get('fingerprints') or {}
            if fingerprints(project,list(expected))!=expected:raise ValueError('verified pair evidence stale')
        if attempt_refs and (attempt_refs['checker']['attempt']<=attempt_refs['producer']['attempt'] or attempt_refs['checker']['created']<attempt_refs['producer']['created']):raise ValueError('checker predates current producer attempt')
        ps,pr=values['producer'];cs,cr=values['checker'];outcome=derive(ch,cr,project)
        behavior=outcome.get('behavior','unknown')
        if outcome['execution']!='completed' or pr.get('failure_kind') or pr.get('status')!='COMPLETE':behavior='unknown'
        verified=(ps=='completed' and cs=='completed' and behavior=='pass')
        artifact={k:v for k,v in pr.get('fingerprints',{}).items() if k in p['write_scope']}
        if not artifact or any(v is None for v in artifact.values()):raise ValueError('verified pair artifacts missing')
        p_profile=ch.get('checker_profile') or {}
        binding_value={'provider':p['provider'],'model':p['model'],'effort':p['reasoning_effort'],'policy':p.get('routing_policy_version')}
        if p.get('model_revision') is not None:binding_value['revision']=p['model_revision']
        binding=digest(binding_value)
        latency=sum((r.get('native') or {}).get('durationMs',0) or 0 for _,r in values.values())
        costs=[(r.get('native') or {}).get('usage',{}).get('cost',{}).get('total') for _,r in values.values()]
        known_cost=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 for v in costs) and all((r.get('native') or {}).get('pricing_verified') is True for _,r in values.values())
        before=digest({'acceptance':p.get('acceptance',[]),'before':p.get('input_fingerprints',{})})
        accounting=None
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='run_accounting'").fetchone():
            accounted=c.execute('SELECT metrics FROM run_accounting WHERE run=?',(run,)).fetchone()
            if accounted:accounting=json.loads(accounted[0])
        return {'verified':verified,'delivered':ps=='completed' and cs in ('completed','failed') and behavior in ('pass','fail'),'behavior':behavior,'unit_hash':digest({'before_content':sorted(str(v) for v in (p.get('input_fingerprints') or {}).values())}),
                'artifacts':artifact,'profile_hash':digest(p_profile),'model_binding':binding,'execution':{'status':outcome.get('execution','unknown'),'before_hash':before,'acceptance_hash':digest(p.get('acceptance',[])),'abstained':p.get('policy_abstained'),'claim_contradicted':pr.get('outcome',{}).get('claim_contradicted',False),'latency_ms':accounting['latency_ms'] if accounting else latency if latency>0 else None,'cost':accounting['cost'] if accounting else sum(costs) if known_cost else None,'accounting_complete':accounting is not None},
                'reference':{'version':2,'workflow':p.get('workflow_id'),**attempt_refs},'combo':p.get('policy_combo'),'model_revision':p.get('model_revision'),'source_group':p.get('source_group') or digest({'before_content':sorted(str(v) for v in (p.get('input_fingerprints') or {}).values())}),'source':'independent_checker','learned':bool(p.get('recipe_id') or p.get('classification',{}).get('outcome')=='learned')}


def verified_reference(reference,project,state=None):
    if not isinstance(reference,dict) or set(reference)!={'version','workflow','producer','checker'} or reference['version']!=2:raise ValueError('canonical attempt pair reference required')
    p=reference['producer'];ch=reference['checker']
    if not isinstance(p,dict) or not isinstance(ch,dict) or not {'run','role','attempt'}<=set(p) or not {'run','role','attempt'}<=set(ch):raise ValueError('attempt-bound producer/checker required')
    proof=verified_pair(p['run'],p['role'],ch,project,state)
    if proof['reference']!=reference:raise ValueError('canonical pair stale or changed')
    return proof

def process_alive(pid):
    if type(pid) is not int or pid<=0:raise ValueError('host_pid must be positive integer')
    if os.name=='nt':
        import ctypes
        handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
        if not handle:return ctypes.windll.kernel32.GetLastError()!=87
        code=ctypes.c_ulong();ok=ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code));ctypes.windll.kernel32.CloseHandle(handle)
        return not ok or code.value==259
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    except PermissionError:return True
    return True
