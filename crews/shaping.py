"""Validate task decomposition proposals without inventing or granting authority."""
from copy import deepcopy
from pathlib import Path


def propose(request,project):
    if not isinstance(request,dict) or set(request)-{'operation','task','authority','roles','invariants'}:
        raise ValueError('shape requires task/authority/roles/invariants only')
    task=request.get('task');authority=request.get('authority');roles=request.get('roles');invariants=request.get('invariants')
    if not isinstance(task,str) or not task.strip() or not isinstance(authority,dict) or set(authority)!={'read','write','commands'}:
        raise ValueError('shape requires explicit task and read/write/commands authority')
    for key in authority:
        if not isinstance(authority[key],list) or any(not isinstance(x,str) or not x.strip() for x in authority[key]):raise ValueError('shape authority lists required')
    if not isinstance(roles,list) or not roles or not isinstance(invariants,list) or not invariants or any(not isinstance(x,str) or not x.strip() for x in invariants):raise ValueError('shape roles and cross-cutting invariants required')
    from crews.omp_adapter import scope_path
    from omp_server import RoleSpec
    root=Path(project).resolve()
    for name in authority['read']+authority['write']:scope_path(str(root),name)
    names=set();checks=[];writes=set()
    output=[]
    for candidate in roles:
        role=RoleSpec.model_validate(candidate).model_dump(exclude_unset=True)
        unknown=set(role)-set(RoleSpec.model_fields)
        if unknown:raise ValueError('shape unknown role fields: '+','.join(sorted(unknown)))
        if role['name'] in names:raise ValueError('shape duplicate role')
        names.add(role['name'])
        scope=role.get('scope') or [];inputs=role.get('inputs') or [];commands=role.get('commands') or []
        if not set(scope)<=set(authority['write']) or not set(inputs)<=set(authority['read']+authority['write']) or not set(commands)<=set(authority['commands']):raise ValueError('shape proposal exceeds caller authority')
        if role['kind'] in ('produce','integrate'):
            if writes.intersection(scope):raise ValueError('shape writers overlap')
            writes.update(scope)
            if not role.get('acceptance'):raise ValueError('shape producer needs explicit acceptance')
        elif scope:raise ValueError('shape read-only role cannot write')
        if role['kind']=='check':checks.append(role)
        output.append(role)
    if not writes or not checks:raise ValueError('shape requires producer and independent check')
    if not any(set(writes)<=set(c.get('inputs') or []) and all(i in (c.get('criteria') or []) for i in invariants) for c in checks):raise ValueError('shape missing cross-cutting invariant checker')
    return {'spec':{'task':task,'roles':deepcopy(output)},'invariants':list(invariants),'authority':deepcopy(authority),
            'admitted':False,'requires_main_validation':True,'reason':'Proposal only; fresh canonical plan and role-local safety validation required'}
