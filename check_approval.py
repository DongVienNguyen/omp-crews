"""No agent-visible private key; test unsigned/tampered/replayed administration."""
import copy,json,subprocess,sys,tempfile
from pathlib import Path
from approval_fixture import Signer
from crews import recipes


def reject(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('unauthorized mutation accepted')


def run():
 with tempfile.TemporaryDirectory(prefix='crews-signature-') as folder:
  project=Path(folder)/'project';project.mkdir();state=Path(folder)/'state'
  signer=Signer();request={'operation':'configure','mode':'on','auto_promotion':None}
  reject(lambda:recipes.dispatch({**request,'confirmed':True},str(project),state))
  signed=signer.approve(request,str(project),state)
  before=(state/'operator-public.pem').read_bytes()
  tampered=copy.deepcopy(signed);tampered['mode']='off'
  reject(lambda:recipes.dispatch(tampered,str(project),state))
  assert not (state/'learning.sqlite').exists()
  assert recipes.dispatch(signed,str(project),state)['mode']=='on'
  reject(lambda:recipes.dispatch(signed,str(project),state))
  assert (state/'operator-public.pem').read_bytes()==before
  for operation in ('register','evidence','audit','activate','probe','rollback'):
   reject(lambda operation=operation:recipes.dispatch({'operation':operation,'confirmed':True},str(project),state))
  # CLI and imported Python bridge both lack operator signature.
  unsigned=project/'request.json';unsigned.write_text(json.dumps(request))
  root=Path(__file__).parent
  result=subprocess.run(['node',str(root/'bin/crews-omp.mjs'),'recipes','configure','--project',str(project),'--state-dir',str(state),'--request',str(unsigned),'--yes','--python',sys.executable,'--json'],cwd=root,capture_output=True,text=True)
  assert result.returncode!=0
  bridge=subprocess.run([sys.executable,'-B',str(root/'omp_bridge.py')],input=json.dumps({'op':'recipes','project':str(project),'args':{**request,'confirmed':True}}),cwd=root,env={**__import__('os').environ,'CREWS_OMP_HOME':str(state)},capture_output=True,text=True)
  assert bridge.returncode!=0
  assert recipes.dispatch({'operation':'status'},str(project),state)['mode']=='on'
 print('PASS: unsigned, modified, replayed, CLI --yes and subprocess bridge admin denied; legitimate signed operator change accepted')


if __name__=='__main__':run()
