"""Portable proposals, never portable execution authority or evidence."""
import copy
import json
import time
import uuid
from crews import outcomes, governance

SCHEMA='CREATE TABLE IF NOT EXISTS rule_exports(id TEXT PRIMARY KEY,project TEXT NOT NULL,packet TEXT NOT NULL,context TEXT NOT NULL,created REAL NOT NULL)'
EDITABLE=('cue','lesson','recipe_steps','negative_examples')


def parse(value):
    if isinstance(value,str):
        if len(value.encode('utf-8'))>262144:raise ValueError('rule packet exceeds 256 KiB')
        value=value.strip()
        if value.startswith('```json\n') and value.endswith('\n```'):value=value[8:-4]
        def pairs(items):
            result={}
            for key,item in items:
                if key in result:raise ValueError('duplicate rule key: '+key)
                result[key]=item
            return result
        value=json.loads(value,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite rule value')))
    if not isinstance(value,dict):raise ValueError('rule packet JSON object required')
    if len(json.dumps(value,allow_nan=False).encode())>262144:raise ValueError('rule packet exceeds 256 KiB')
    if 'packet' in value and 'format' not in value:
        if set(value)!={'changed','packet'} or value['changed'] is not False or not isinstance(value['packet'],dict):
            raise ValueError('invalid rule export envelope; paste a crews-rule packet or {changed:false,packet:{...}}')
        value=value['packet']
    if value.get('format')!='crews-rule':raise ValueError('expected crews-rule packet; format/version belong inside the packet object')
    return value


def revision(db,project,kind,target):
    from crews import recipes
    from crews.classification import policy_version
    from pathlib import Path
    contract=dict(routing=policy_version(),workflow=outcomes.digest((Path(__file__).with_name('workflow.py')).read_text(encoding='utf-8')))
    if kind=='policy':
        row=db.execute('SELECT request FROM automation_grants WHERE id=? AND project=? AND revoked=0',(target,project)).fetchone()
        if not row:raise ValueError('rule policy no longer exists')
        limits=json.loads(row[0]);return outcomes.digest(dict(epoch=limits['epoch'],installation=limits['installation_id'],policy={key:limits[key] for key in governance.DEFAULTS},sdlc_contract=contract))
    row=recipes._row(db,project,target)
    return outcomes.digest(dict(body=json.loads(row['body']),profile_hash=row['profile_hash'],sdlc_contract=contract))


def validate_job(db,request,project):
    if not request.get('external_export'):return
    db.execute(SCHEMA)
    row=db.execute('SELECT packet FROM rule_exports WHERE id=? AND project=?',(request['external_export'],project)).fetchone()
    if not row:raise ValueError('external rule export missing in this project')
    packet=json.loads(row[0]);base=packet['base']
    if revision(db,project,packet['kind'],base['target'])!=base['revision']:raise ValueError('rule changed since export; export fresh packet')


def exchange(request,project,state):
    from crews import automation as auto, recipes
    op=request['operation']
    if op=='export':
        auto.ensure(project,state)
        with auto.database(state) as db:
            db.execute(SCHEMA)
            grant=next((g for g in db.execute('SELECT * FROM automation_grants WHERE project=? AND revoked=0 ORDER BY accepted DESC',(project,)) if auto._local(json.loads(g['request']))),None)
            if not grant:raise ValueError('local governance not initialized; run setup and open project')
            limits=json.loads(grant['request']);kind=request.get('kind','policy');context={}
            if kind=='policy':
                target=grant['id'];proposal={key:limits[key] for key in governance.DEFAULTS};schema=governance.schema()['properties']['policy']
                proposal=copy.deepcopy(proposal)
                proposal['routing']={need:governance.routing_entry(entry) for need,entry in proposal['routing'].items()}
                description='Optimize supported Crews policy. Return this JSON packet, edit ONLY proposal. Preserve every other field. No code, commands, credentials or invented evidence.'
            elif kind=='recipe':
                target=request.get('recipe_id');row=recipes._row(db,project,target);body=json.loads(row['body'])
                if body.get('_delegation_id')!=grant['id']:raise ValueError('recipe belongs to another policy authority')
                for raw, in db.execute("SELECT request FROM automation_jobs WHERE project=? AND state='applied' ORDER BY created",(project,)):
                    candidate=json.loads(raw)
                    if candidate.get('operation')=='recipe_edit':candidate=candidate['registration']
                    if candidate.get('operation')=='register' and candidate['recipe']['features']==body['features'] and candidate['recipe']['version']==body['version']:
                        context=candidate
                if not context:raise ValueError('recipe original reviewed authority unavailable; cannot safely import edits')
                proposal={key:body[key] for key in EDITABLE}
                schema=dict(type='object',additionalProperties=False,required=list(EDITABLE),properties={key:dict(type='array',minItems=1,items=dict(type='string',minLength=1)) if key in ('recipe_steps','negative_examples') else dict(type='string',minLength=1) for key in EDITABLE})
                description='Optimize recipe guidance only. Edit ONLY proposal. Invariant/checker/model/safety/evidence cannot change. Approved edits become new candidate version, not active recipe.'
                context=copy.deepcopy(context);context['recipe']={key:body[key] for key in context['recipe']};context['recipe']['version']=body['version']+1
            else:raise ValueError('rule kind must be policy or recipe')
            packet=dict(format='crews-rule',version=1,export_id=uuid.uuid4().hex,kind=kind,base=dict(target=target,revision=revision(db,project,kind,target)),instructions=description,schema=schema,proposal=proposal)
            packet['workflow_contract']=dict(version=1,profiles=['baseline','sdlc_cost_aware'],default='sdlc_cost_aware',authority='immutable original scope',promotion='operator enablement distinct from frozen quality evidence')
            if kind=='recipe':packet['constraints']={key:body[key] for key in ('features','applicability','exclusions','max_difficulty')}
            db.execute('INSERT INTO rule_exports VALUES(?,?,?,?,?)',(packet['export_id'],project,json.dumps(packet),json.dumps(context),time.time()))
            return packet
    if op!='import' or request.get('confirmed') is not True:raise ValueError('rule import requires explicit confirmation')
    packet=parse(request.get('packet'))
    if type(packet.get('version')) is not int or packet['version']!=1:raise ValueError('unsupported rule version; integer 1 required')
    with auto.database(state) as db:
        db.execute(SCHEMA)
        row=db.execute('SELECT packet,context FROM rule_exports WHERE id=? AND project=?',(packet.get('export_id'),project)).fetchone()
        if not row:raise ValueError('unknown/foreign export; export from target project first')
        original=json.loads(row[0])
        immutable=lambda p:json.dumps({k:v for k,v in p.items() if k!='proposal'},sort_keys=True,separators=(',',':'),allow_nan=False)
        if set(packet)!=set(original) or immutable(packet)!=immutable(original):raise ValueError('immutable packet context/version changed; edit proposal only')
        grant=next((g for g in db.execute('SELECT * FROM automation_grants WHERE project=? AND revoked=0 ORDER BY accepted DESC',(project,)) if auto._local(json.loads(g['request']))),None)
        if not grant:raise ValueError('local policy unavailable')
        _,limits=auto.live(db,grant['id'],project,state,govern=packet['kind']=='policy')
        imported=dict(external_export=packet['export_id'],external_proposal=packet['proposal'])
        validate_job(db,imported,project)
        if packet['kind']=='policy':
            proposal=governance.validate(packet['proposal'],typed_routing=True)
            imported.update(operation='govern',policy=proposal,aggregate=auto._aggregate(db,project,state)[0],policy_binding=limits['policy_binding'])
        else:
            proposal=packet['proposal']
            if not isinstance(proposal,dict) or set(proposal)!=set(EDITABLE):raise ValueError('recipe edits limited to guidance fields')
            for key in EDITABLE:
                values=proposal[key] if key in ('recipe_steps','negative_examples') else [proposal[key]]
                if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v.strip() for v in values):raise ValueError('nonempty recipe text required')
            context=json.loads(row[1]);body=context['recipe'];body.update(proposal)
            recipes._recipe(body,project)
            imported.update(operation='recipe_edit',recipe_id=packet['base']['target'],registration=dict(operation='register',recipe=body,role=context['role'],roles=context['roles'],machine_consent=True))
        auto.enqueue(db,grant,imported,project,state)
        for job in db.execute('SELECT id,state,request FROM automation_jobs WHERE grant_id=? ORDER BY created DESC',(grant['id'],)):
            value=json.loads(job['request'])
            if value.get('external_export')==packet['export_id'] and value.get('external_proposal')==packet['proposal']:
                return dict(job_id=job['id'],state=job['state'],applied=False,note='External proposal queued for independent Large review; no direct apply.')
        raise ValueError('rule proposal could not be queued')
