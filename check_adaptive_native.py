"""Actual native Crews/model smoke over three independent behavior families."""
import json,os,subprocess,sys,tempfile,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PY=sys.executable
cases=[('mapping','def transform(value):\n    return value\n',"Implement transform(value): dict input else TypeError; return new dict with key count default0 and explicit None preserved; do not mutate input.","from target import transform\nassert transform({})=={'count':0}\nassert transform({'count':None})=={'count':None}\nx={'count':2};assert transform(x)==x and transform(x) is not x\ntry: transform([])\nexcept TypeError: pass\nelse: raise AssertionError('type')\n"),('parser','def transform(value):\n    return value\n',"Implement transform(value): strings only else TypeError; strip whitespace, parse base10 ASCII digits into nonnegative int; empty, negative, non-ASCII or other characters ValueError.","from target import transform\nassert transform(' 42 ')==42\nassert transform('0')==0\nfor v in ['', '-1','1.2','１２']:\n try: transform(v)\n except ValueError: pass\n else: raise AssertionError(v)\ntry: transform(None)\nexcept TypeError: pass\nelse: raise AssertionError('type')\n"),('formatting','def transform(value):\n    return value\n',"Implement transform(value): list of strings only else TypeError; stable equality-based deduplication, retaining first occurrence and not mutating list.","from target import transform\nx=['b','a','b'];assert transform(x)==['b','a'] and x==['b','a','b']\nassert transform([])==[]\nfor v in [['x',1],None,'abc']:\n try: transform(v)\n except TypeError: pass\n else: raise AssertionError(v)\n")]
base=Path(os.environ.get('CREWS_ADAPTIVE_SMOKE_ROOT',str(Path(tempfile.gettempdir())/'crews-adaptive-native-proof')))
base.mkdir(exist_ok=True);state=base/'state';state.mkdir(exist_ok=True)
env={**os.environ,'CREWS_OMP_HOME':str(state),'CREWS_OMP_PYTHON':PY,'PYTHONUTF8':'1'}
results=[]
for family,before,criterion,check in cases:
 p=base/family;p.mkdir(exist_ok=True)
 assert not (p/'plan.json').exists(),'native smoke already exists; preserve evidence before rerun'
 (p/'target.py').write_text(before);(p/'verify.py').write_text('import json\n'+check+'print(json.dumps({"criterion_results":[{"criterion":'+repr(criterion)+',"status":"pass"}]}))\n')
 command=PY.replace('\\','/')+' -B verify.py'
 producer={'name':family+'-producer','kind':'produce','mission':criterion+' Read target.py and verify.py. Write only target.py; run admitted checker and report real result. No other commands or agents.','deliverable':'target.py','scope':['target.py'],'inputs':['target.py','verify.py'],'commands':[command],'acceptance':[criterion],'routine_check':family+'-check','model_revision':'smoke-20261027','facts':dict(targets_fixed=True,behavior_fixed=True,scope_bounded=True,behavior_undecided=False,unknown_cause=False,consequential_judgment=False,cross_system=False,concurrency_sensitive=False),'answers':dict(need='everyday_implementation',difficulty=1,divisible=0,specific=1)}
 checker={'name':family+'-check','kind':'check','mission':'Independently verify: '+criterion+' Inspect checker meaning then run exact admitted command. Return original criterion in criterion_results with pass/fail. No edits or agents.','deliverable':'verdict','scope':[],'inputs':['target.py','verify.py'],'commands':[command],'criteria':[criterion],'checker_profile':dict(input='verify.py',command=command,version='1'),'verify_targets':[producer['name']],'answers':dict(need='mechanical_verification',difficulty=1,divisible=0,specific=1)}
 req=dict(op='plan',spec=dict(task=criterion,roles=[producer,checker]),answers=dict(need=dict(choice='everyday_implementation',confidence=1,probabilities={'everyday_implementation':1}),difficulty=dict(score=1),divisible=dict(noul=0),needs_verifier=dict(noul=1)),project=str(p),session='adaptive-'+family+'-smoke')
 r=subprocess.run([PY,'-B','omp_bridge.py'],cwd=ROOT,input=json.dumps(req),capture_output=True,text=True,encoding='utf-8',env=env);assert r.returncode==0,r.stdout+r.stderr
 plan=json.loads(r.stdout);(p/'plan.json').write_text(json.dumps(plan,indent=2));refs=[dict(run=plan['run_id'],role=c['role_id'],session=plan['session']) for w in plan['waves'] for c in w['calls']]
 prompt='Execute only canonical task top-level crew references in order '+json.dumps(refs)+'. No planning, edits, other tools or ordinary agents. Stop if failed, return actual outputs. Main model unchanged.'
 with (p/'host.log').open('w') as log:
  host=subprocess.run([shutil.which('omp'),'--cwd',str(p),'--no-extensions','-e',str(ROOT),'--no-session','--no-title','--max-time','600','-p',prompt],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=660)
 observed=subprocess.run([PY,'-B','verify.py'],cwd=p,capture_output=True,text=True)
 script="import json,sys;from crews.outcomes import verified_pair;print(json.dumps(verified_pair(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])))"
 evidence=subprocess.run([PY,'-B','-c',script,plan['run_id'],producer['name'],checker['name'],str(p),str(state)],cwd=ROOT,env=env,capture_output=True,text=True)
 proof=json.loads(evidence.stdout) if evidence.returncode==0 else {'verified':False,'error':evidence.stderr}
 results.append(dict(family=family,run=plan['run_id'],host_exit=host.returncode,behavior_exit=observed.returncode,proof=proof));(base/'summary.json').write_text(json.dumps(results,indent=2));print(json.dumps(results[-1]),flush=True)
assert len(results)==3 and all(r['proof']['verified'] and r['behavior_exit']==0 for r in results),'native smoke incomplete; preserve evidence and use explicit recovery'
print('PASS: three native Small producers and independent executable checker profiles, matching proof and behavior')
