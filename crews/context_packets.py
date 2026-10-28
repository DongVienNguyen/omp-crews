"""Bounded source observations. Packets are context, never execution authority."""
import hashlib,json
from pathlib import Path

MAX_BYTES=8192
MAX_REFS=32


def schema():
    text={'type':'string','minLength':1}
    ref={'type':'object','additionalProperties':False,'required':['path','sha256','start','end'],'properties':{'path':text,'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'start':{'type':'integer','minimum':1},'end':{'type':'integer','minimum':1}}}
    fact={'type':'object','additionalProperties':False,'required':['text','sources'],'properties':{'text':text,'sources':{'type':'array','minItems':1,'items':{'type':'integer','minimum':0,'maximum':31}}}}
    return {'type':'object','additionalProperties':False,'required':['version','sources','observations','inferences','unresolved','needs_more_context'],'properties':{'version':{'type':'integer','enum':[1]},'sources':{'type':'array','maxItems':MAX_REFS,'items':ref},'observations':{'type':'array','items':fact},'inferences':{'type':'array','items':fact},'unresolved':{'type':'array','items':text},'needs_more_context':{'type':'boolean'}}}


def validate(packet,cell,project):
    if not isinstance(packet,dict) or set(packet)!={'version','sources','observations','inferences','unresolved','needs_more_context'} or type(packet['version']) is not int or packet['version']!=1:raise ValueError('context packet version/fields invalid')
    if len(json.dumps(packet,ensure_ascii=False,allow_nan=False).encode())>MAX_BYTES:raise ValueError('context packet too large; request bounded expansion')
    refs=packet['sources']
    if not isinstance(refs,list) or len(refs)>MAX_REFS or type(packet['needs_more_context']) is not bool:raise ValueError('context refs or expansion flag invalid')
    allowed=set(cell.get('read_scope') or [])
    root=Path(project).resolve()
    for ref in refs:
        if not isinstance(ref,dict) or set(ref)!={'path','sha256','start','end'} or ref['path'] not in allowed:raise ValueError('context source outside admitted inputs')
        path=(root/ref['path']).resolve()
        if Path(ref['path']).is_absolute() or '..' in Path(ref['path']).parts or not path.is_relative_to(root) or not path.is_file():raise ValueError('context source missing or escapes project')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:raise ValueError('context source hash stale')
        if type(ref['start']) is not int or type(ref['end']) is not int or not 1<=ref['start']<=ref['end']<=len(path.read_text(encoding='utf-8').splitlines()):raise ValueError('context source line range invalid')
    for key in ('observations','inferences'):
        if not isinstance(packet[key],list):raise ValueError('context fact list required')
        for fact in packet[key]:
            if not isinstance(fact,dict) or set(fact)!={'text','sources'} or not isinstance(fact['text'],str) or not fact['text'].strip() or not isinstance(fact['sources'],list) or not fact['sources'] or any(type(i) is not int or not 0<=i<len(refs) for i in fact['sources']):raise ValueError('context fact requires admitted source references')
    if not isinstance(packet['unresolved'],list) or any(not isinstance(t,str) or not t.strip() for t in packet['unresolved']):raise ValueError('context unresolved list invalid')
    return packet


def handoff(run,role,project,state):
    from crews import omp_adapter as a
    with a.database(state) as db:
        row=db.execute('SELECT plan FROM runs WHERE id=? AND project=?',(run,a.canonical(project))).fetchone()
        if not row:raise ValueError('context source run not found')
        plan=json.loads(row[0]);cell=next(c for w in plan['waves'] for c in w['calls'] if c['role_id']==role)
        record=db.execute('SELECT status,result FROM calls WHERE run=? AND role=?',(run,role)).fetchone()
        if not record or record[0]!='completed':raise ValueError('context source not completed')
        result=json.loads(record[1])
        if not result.get('host_authenticated'):raise ValueError('context source lacks host proof')
        packet=validate(result.get('context_packet'),cell,project)
        return packet
