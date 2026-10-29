"""Mutable checkout cannot corrupt frozen benchmark; execution/config drift refuses."""
import os
import shutil
import subprocess
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'plans/20261028-sdlc-micro-loops/benchmark'))
import frozen_runtime as frozen


def reject(call,fragment):
    try:call()
    except ValueError as error:assert fragment in str(error),str(error)
    else:raise AssertionError('expected '+fragment)


def run():
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder);source=p/'checkout';source.mkdir();agent=p/'agent';agent.mkdir()
        (source/'package.json').write_text('{}')
        (source/'requirements-omp.lock').write_text('mcp==1.27.0\nPyYAML==6.0.3\n')
        (source/'crews').mkdir();(source/'crews/policy.py').write_text('VALUE=1\n')
        (source/frozen.BENCHMARK).mkdir(parents=True)
        (source/frozen.BENCHMARK/'runner.py').write_text('import argparse,json\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument("--output");p.add_argument("--policy");p.add_argument("--agent-dir");p.add_argument("--snapshot-worker",action="store_true");a=p.parse_args()\nassert a.snapshot_worker and Path(a.policy).parent==Path(a.output)\nassert Path.cwd()==Path(a.output)/"runtime"\n(Path(a.output)/"worker-observed.json").write_text(json.dumps({"policy":a.policy,"agent":a.agent_dir}))\n')
        shutil.copyfile(ROOT/frozen.BENCHMARK/'frozen_runtime.py',source/frozen.BENCHMARK/'frozen_runtime.py')
        (source/'omp_bridge.py').write_text('import os\nfrom pathlib import Path\nprint("bridge observed")\nif os.environ.get("FROZEN_TEST_MUTATE"):\n (Path(__file__).parent/"benchmark-host.ts").write_text("changed during bridge")\n')
        (agent/'config.yml').write_text('task:\n  structured: true\n')
        (agent/'models.yml').write_text('private-config-marker')
        policy=p/'policy.json';policy.write_text(json.dumps({'provider':'9router','combos':{c:{'model':c.lower(),'effort':'Auto'} for c in ('Small','Medium','Large')}}))
        output=p/'evidence';args=SimpleNamespace(output=output,policy=policy,agent_dir=agent,main_model='9router/medium:high',timeout=600)
        assert frozen.launch_snapshot(source,args,['--output='+str(output),'--policy='+str(policy),'--agent-dir='+str(agent)],'host fixture')==0
        assert json.loads((output/'worker-observed.json').read_text())['agent']==str(agent.resolve())
        runtime=output/'runtime';proof=frozen.validate(runtime,output,agent)
        env={**os.environ,'CREWS_OMP_AGENT_DIR':str(agent),'PYTHONDONTWRITEBYTECODE':'1'}
        observed=subprocess.run([sys.executable,'-B',str(runtime/'omp_bridge.py')],env=env,capture_output=True,text=True)
        assert observed.returncode==0 and 'bridge observed' in observed.stdout,observed.stderr
        host=runtime/'benchmark-host.ts';saved=host.read_bytes();host.write_text('changed host')
        observed=subprocess.run([sys.executable,'-B',str(runtime/'omp_bridge.py')],env=env,capture_output=True,text=True)
        assert observed.returncode!=0 and 'bridge observed' not in observed.stdout
        host.write_bytes(saved)
        observed=subprocess.run([sys.executable,'-B',str(runtime/'omp_bridge.py')],env={**env,'FROZEN_TEST_MUTATE':'1'},capture_output=True,text=True)
        assert observed.returncode!=0 and 'bridge observed' in observed.stdout and 'frozen executable snapshot changed' in observed.stderr
        host.write_bytes(saved)
        assert 'private-config-marker' not in (output/'runtime-proof.json').read_text()
        assert not (runtime/'models.yml').exists()
        (source/'crews/policy.py').write_text('VALUE=2\n');assert frozen.validate(runtime,output,agent)==proof
        target=runtime/'crews/policy.py';original=target.read_bytes();target.write_text('VALUE=99\n')
        reject(lambda:frozen.validate(runtime,output,agent),'executable snapshot changed');target.write_bytes(original)
        config=agent/'config.yml';original=config.read_bytes();config.write_text('task:\n  structured: false\n')
        reject(lambda:frozen.validate(runtime,output,agent),'host configuration changed');config.write_bytes(original)
        overlay=output/'native-config.yml';original=overlay.read_bytes();overlay.write_text('task: {}\n')
        reject(lambda:frozen.validate(runtime,output,agent),'strict-output configuration changed');overlay.write_bytes(original)
        (output/'state').mkdir();(output/'state/policy.json').write_text(json.dumps({**proof['policy'],'provider':'changed'}))
        reject(lambda:frozen.validate(runtime,output,agent),'model policy changed')
        (output/'state/policy.json').unlink()
        reject(lambda:frozen.validate(runtime,output,agent),'model policy changed or missing')
        print('PASS checkout drift isolated; source/host/native config/model policy tampering refused; credentials never copied')

if __name__=='__main__':run()
