"""Operator-signed administration. Agent tool confirmation is not human consent.

Trust boundary: public-key trust is provisioned by the operator before agent use.
Private signing keys never belong in agent-readable state/context/environment.
This is not protection against arbitrary same-user filesystem compromise.
"""
import base64,hashlib,json,os,subprocess,time
from pathlib import Path


def canonical(value):
    def normalize(item):
        if isinstance(item,float) and item.is_integer():return int(item)
        if isinstance(item,list):return [normalize(v) for v in item]
        if isinstance(item,dict):return {k:normalize(v) for k,v in item.items()}
        return item
    return json.dumps(normalize(value),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def authorize(request,project,state,accepted_at=None):
    grant=request.get('approval')
    if not isinstance(grant,dict) or set(grant)!={'payload','signature'}:raise ValueError('operator-signed approval required; confirmed is not authorization')
    payload=grant['payload']
    if not isinstance(payload,dict) or set(payload)!={'request_hash','project','expires','nonce'}:raise ValueError('invalid approval payload')
    reference=time.time() if accepted_at is None else accepted_at
    if not isinstance(payload['expires'],(int,float)) or isinstance(payload['expires'],bool) or not reference<payload['expires']<=reference+3600:raise ValueError('approval expired or too long-lived')
    if not isinstance(payload['nonce'],str) or len(payload['nonce'])<32:raise ValueError('approval nonce invalid')
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('approval','confirmed','recipe_approval','recipe_confirmed')}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    body=clean(request)
    if payload['request_hash']!=hashlib.sha256(canonical(body)).hexdigest() or payload['project']!=os.path.normcase(str(Path(project).resolve())):raise ValueError('approval request/project mismatch')
    trust=Path(state)/'operator-public.pem'
    if not trust.is_file():raise ValueError('operator trust not provisioned outside model execution')
    code="const fs=require('fs'),crypto=require('crypto');const x=JSON.parse(fs.readFileSync(0,'utf8'));if(!crypto.verify(null,Buffer.from(x.payload,'base64'),x.publicKey,Buffer.from(x.signature,'base64')))process.exit(2);"
    data={'payload':base64.b64encode(canonical(payload)).decode(),'signature':grant['signature'],'publicKey':trust.read_text(encoding='utf-8')}
    result=subprocess.run(['node','-e',code],input=json.dumps(data),capture_output=True,text=True,timeout=10)
    if result.returncode:raise ValueError('operator approval signature invalid')
    return payload['nonce']


def consume(db,nonce):
    db.execute('CREATE TABLE IF NOT EXISTS operator_approvals(nonce TEXT PRIMARY KEY,used REAL NOT NULL)')
    try:db.execute('INSERT INTO operator_approvals VALUES(?,?)',(nonce,time.time()))
    except __import__('sqlite3').IntegrityError:raise ValueError('operator approval already used') from None
