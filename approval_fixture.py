"""Test-only signer. Ephemeral key retained in parent, never child agent context."""
import base64,json,hashlib,os,subprocess,time,uuid
from pathlib import Path
from crews.approval import canonical

class Signer:
 def __init__(self):
  code="const c=require('crypto');const k=c.generateKeyPairSync('ed25519');console.log(JSON.stringify({private:k.privateKey.export({type:'pkcs8',format:'pem'}),public:k.publicKey.export({type:'spki',format:'pem'})}));"
  self.keys=json.loads(subprocess.run(['node','-e',code],capture_output=True,text=True,check=True).stdout)
 def approve(self,request,project,state):
  root=Path(state);root.mkdir(exist_ok=True)
  trust=root/'operator-public.pem'
  if not trust.exists():trust.write_text(self.keys['public'])
  def clean(v):
   if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in ('approval','confirmed','recipe_approval','recipe_confirmed')}
   if isinstance(v,list):return [clean(x) for x in v]
   return v
  body=clean(request)
  payload={'request_hash':hashlib.sha256(canonical(body)).hexdigest(),'project':os.path.normcase(str(Path(project).resolve())),'expires':int(time.time())+900,'nonce':uuid.uuid4().hex}
  code="const fs=require('fs'),c=require('crypto');const x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(c.sign(null,Buffer.from(x.payload,'base64'),x.key).toString('base64'));"
  signature=subprocess.run(['node','-e',code],input=json.dumps({'payload':base64.b64encode(canonical(payload)).decode(),'key':self.keys['private']}),capture_output=True,text=True,check=True).stdout.strip()
  return {**body,'confirmed':True,'approval':{'payload':payload,'signature':signature}}
