"""Private executable snapshots; hashes detect drift, never grant task authority."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BENCHMARK = Path('plans/20261028-sdlc-micro-loops/benchmark')


def hashes(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def host_hashes(agent_dir):
    """Store digests only; model config may contain credentials and is never copied."""
    agent_dir = Path(agent_dir)
    names = ['config.yml', 'models.yml']
    return {name: hashlib.sha256((agent_dir / name).read_bytes()).hexdigest()
            if (agent_dir / name).is_file() else None for name in names}


def launch_snapshot(root, args, argv, host_source=''):
    """Reserve fresh output, snapshot only executable inputs, then re-exec there."""
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / 'runtime'
    runtime.mkdir()
    root = Path(root).resolve()
    files = [p for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.mjs', '.ts')]
    files += [root / 'package.json', root / 'requirements-omp.lock']
    for directory, patterns in [('crews', ('*.py', '*.json')), ('agents', ('*.md',)),
                                ('skills/crew-omp', ('SKILL.md',)), (str(BENCHMARK), ('*.py',))]:
        for pattern in patterns:
            files.extend((root / directory).glob(pattern))
    for source in files:
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('benchmark source link escapes checkout')
        target = runtime / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (runtime/'benchmark-host.ts').write_text(host_source,encoding='utf-8')
    bridge=runtime/'omp_bridge.py'
    if bridge.exists():
        bridge.rename(runtime/'omp_bridge_impl.py')
        bridge.write_text('import os,sys,runpy\nfrom pathlib import Path\nroot=Path(__file__).resolve().parent\nsys.path.insert(0,str(root/"plans/20261028-sdlc-micro-loops/benchmark"))\nfrom frozen_runtime import validate\nvalidate(root,root.parent,os.environ.get("CREWS_OMP_AGENT_DIR"))\ntry:\n runpy.run_path(str(root/"omp_bridge_impl.py"),run_name="__main__")\nfinally:\n validate(root,root.parent,os.environ.get("CREWS_OMP_AGENT_DIR"))\n',encoding='utf-8')
    overlay = output / 'native-config.yml'
    overlay.write_text('task:\n  structured: true\n', encoding='utf-8')
    from crews.omp_adapter import validate_policy
    policy = validate_policy(json.loads(args.policy.read_text(encoding='utf-8'))) if args.policy else None
    proof = dict(version=1, source=hashes(runtime), host=host_hashes(args.agent_dir) if args.agent_dir else {},
                 native_config=hashlib.sha256(overlay.read_bytes()).hexdigest(), policy=policy,
                 python=sys.version, executable=str(Path(sys.executable).resolve()),
                 main_model=args.main_model, timeout=args.timeout)
    (output / 'runtime-proof.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    command = [sys.executable, '-u', '-B', str(runtime / BENCHMARK / 'runner.py'), *argv, '--snapshot-worker']
    def replace_option(flag,value):
        for index,item in enumerate(command):
            if item==flag:command[index+1]=str(value);return
            if item.startswith(flag+'='):command[index]=flag+'='+str(value);return
        raise ValueError('missing option '+flag)
    for flag,value in (('--output',output),('--agent-dir',args.agent_dir.resolve() if args.agent_dir else None)):
        if value is not None:replace_option(flag,value)
    # Policy file contents are pinned before worker launch. Never read a later edited policy path.
    if args.policy:
        pinned = output / 'model-policy.json'
        pinned.write_text(json.dumps(policy, indent=2)+'\n', encoding='utf-8')
        replace_option('--policy',pinned)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.call(command, cwd=runtime, env=env)


def validate(root, output, agent_dir=None):
    output = Path(output)
    proof = json.loads((output / 'runtime-proof.json').read_text(encoding='utf-8'))
    if hashes(root) != proof['source']:
        raise ValueError('frozen executable snapshot changed')
    if agent_dir and host_hashes(agent_dir) != proof['host']:
        raise ValueError('frozen native host configuration changed')
    overlay = output / 'native-config.yml'
    if not overlay.is_file() or hashlib.sha256(overlay.read_bytes()).hexdigest() != proof['native_config']:
        raise ValueError('frozen native strict-output configuration changed')
    if proof['python'] != sys.version or proof['executable'] != str(Path(sys.executable).resolve()):
        raise ValueError('frozen Python runtime changed')
    state_policy = output / 'state/policy.json'
    if proof['policy'] is not None and state_policy.parent.exists():
        if not state_policy.is_file() or json.loads(state_policy.read_text(encoding='utf-8')) != proof['policy']:
            raise ValueError('frozen model policy changed or missing')
    return proof
