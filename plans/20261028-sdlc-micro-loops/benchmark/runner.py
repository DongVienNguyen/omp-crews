"""Native OMP paired harness; reconstructed exercises, no production/savings claim.

Run with provisioned runtime Python from repository root:
  python -B plans/20261028-sdlc-micro-loops/benchmark/runner.py --validate-only --output <new-directory>
  python -B plans/20261028-sdlc-micro-loops/benchmark/runner.py --output <new-directory> --policy <reviewed-policy.json> --agent-dir <configured-OMP-agent-directory> --main-model <provider/model:effort>

Profile setup: existing OMP agent directory must contain real model definitions and
credentials for every Combo plus main model. Use installed `crews-omp combo show`
to obtain reviewed provider/Small/Medium/Large model+effort policy, supply its JSON
via --policy. This harness never edits configured profile, imports operator keys,
starts scripted providers, or calls providers directly. `baseline` and
`sdlc_cost_aware` are workflow profiles, NOT different credential profiles. Both
use identical policy/environment. Configured native OMP executable and checkout
extension must be compatible; use provisioned Python 3.12+ with project deps.

Runner reserves fresh output and re-execs from a private executable snapshot.
Host config/model digests, strict native overlay and normalized policy are pinned;
drift refuses before/after bridges and arms. --units selects known regression
exercises, never a new unseen holdout. No live checkout edits affect execution.

Fresh output only: interruption/failure remains terminal evidence. No resume,
retry, replay or implicit recovery. Failed pairs remain in frozen report. Native
main sessions get one admitted workflow at a time; workflow host caps child
concurrency at two (current manifests run each node sequentially). Candidate
adds bounded source scout only where unit asks; no model quotas or cheap-route
facts fabricated. All writing goes through canonical roles and host admission.

Host executable oracle runs arbitrary product code. Crews scopes are NOT OS
isolation. Run benchmark in disposable OS account/container with no unrelated
secrets; model credentials remain governed by configured OMP profile. Read-only
oracles are scope-independent and fingerprinted, not protection against hostile
same-user code. This is evaluation harness, never security sandbox.
"""
import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from corpus import units
from crews import omp_adapter as adapter, workflow, workflow_evaluation as evaluation
from crews.outcomes import digest, fingerprints
from check_effort_policy import task_answers
from frozen_runtime import launch_snapshot, validate as validate_runtime


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def command():
    return shlex.quote(sys.executable.replace('\\', '/')) + ' -B oracle.py'


def manifest(unit, arm, project):
    """One canonical producer route; optional candidate source-backed scout."""
    check_command = command()
    hash_command=shlex.quote(sys.executable.replace('\\','/'))+' -B source_hashes.py'
    reads = list(unit.files) + ['oracle.py','source_hashes.py']
    # Every writer may inspect acceptance and immutable oracle, never solutions.
    need='everyday_implementation' if unit.need=='bounded_retrieval' else unit.need
    writer = dict(name='writer', kind='produce', mission=unit.mission,
                  deliverable='product.py', scope=['product.py'], inputs=reads,
                  commands=[check_command], acceptance=unit.acceptance,
                  answers=dict(need=need, difficulty=unit.difficulty,
                               divisible=0, specific=1))
    if arm=='candidate' and unit.family=='retrieval_docs':
        writer.update(facts=dict(targets_fixed=True,behavior_fixed=True,scope_bounded=True,deterministic_check=True,behavior_undecided=False,unknown_cause=False,consequential_judgment=False,cross_system=False,concurrency_sensitive=False),bounded_check=dict(input='oracle.py',command=check_command),commands=[check_command])
    nodes = []
    deps = []
    if arm == 'candidate' and unit.scout:
        scout = dict(name='scout', kind='research',
                     mission='Read product.py and admitted sources and oracle.py for '+unit.id+'. Run admitted source_hashes.py command for exact sha256 and line counts. Return the required status/verification/context_packet envelope, NOT a bare packet. Nest the packet schema fields under context_packet. Each fact needs nonempty source indices; source ranges must fit command-reported line count. Do not decide uncertain architecture/security or edit files.',
                     deliverable='source-backed context_packet', scope=[], inputs=reads,
                     commands=[hash_command], context_request=True,
                     acceptance=['Source observations accurately cite admitted files; unresolved judgments remain explicit'],
                     answers=dict(need='bounded_retrieval', difficulty=1, divisible=0, specific=1))
        nodes.append(dict(id='scout', stage='discovery', depends_on=[], roles=[scout],
                          answers=task_answers('bounded_retrieval', 1)))
        deps = ['scout']
    nodes.append(dict(id='writer', stage='implementation', depends_on=deps,
                      roles=[writer], answers=task_answers(need, unit.difficulty)))
    checker = dict(name='checker', kind='check', mission='Check product.py using oracle.py for '+unit.id+'. Execute immutable oracle; report each original criterion exactly, with actual host evidence. No edits.',
                   deliverable='independent executable verdict', scope=[], inputs=reads,
                   commands=[check_command], acceptance=unit.acceptance,
                   criteria=unit.acceptance,
                   checker_profile=dict(input='oracle.py', command=check_command, version='reconstructed-20261028-1'),
                   answers=dict(need='mechanical_verification', difficulty=1, divisible=0, specific=1))
    nodes.append(dict(id='checker', stage='acceptance', depends_on=['writer'], roles=[checker],
                      answers=task_answers('mechanical_verification', 1, True)))
    spec = dict(task='Reconstructed independent exercise ' + unit.id + ': ' + unit.mission,
                authority=dict(read=reads, write=['product.py'], commands=[check_command,hash_command]),
                invariants=unit.acceptance, max_calls=len(nodes), nodes=nodes)
    return workflow._validate(spec, str(project))[0]


def install_unit(unit, project):
    project.mkdir(parents=True)
    for name, text in unit.files.items():
        (project / name).write_text(text, encoding='utf-8')
    oracle = project / 'oracle.py'
    oracle.write_text(unit.oracle(), encoding='utf-8')
    # Reject accidental writable-oracle scope during canonical validation too.
    oracle.chmod(0o444)
    (project/'source_hashes.py').write_text('import hashlib,json\nfrom pathlib import Path\nprint(json.dumps({name:{"sha256":hashlib.sha256(Path(name).read_bytes()).hexdigest(),"lines":len(Path(name).read_text(encoding="utf-8").splitlines())} for name in '+repr(list(unit.files)+['oracle.py','source_hashes.py'])+'}))\n',encoding='utf-8')


def offline_check(unit, project):
    """Require failing original and all-criteria passing known solution, no models."""
    oracle_hash = fingerprints(str(project), ['oracle.py'])
    outputs = []
    for label, text in (('original', unit.initial), ('solution', unit.solution)):
        (project / 'product.py').write_text(dedent(text).lstrip(), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', 'oracle.py'], cwd=project,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise ValueError(unit.id + ' ' + label + ' oracle failed to emit JSON: ' + result.stderr) from exc
        rows = payload['criterion_results']
        if [r['criterion'] for r in rows] != unit.acceptance:
            raise ValueError(unit.id + ' oracle criterion mismatch')
        passed = result.returncode == 0 and all(r['status'] == 'pass' for r in rows)
        if passed != (label == 'solution'):
            raise ValueError(unit.id + ' expected ' + label + ' ' + ('pass' if label == 'solution' else 'fail') + ': ' + result.stdout + result.stderr)
        if fingerprints(str(project), ['oracle.py']) != oracle_hash:
            raise ValueError('oracle changed during validation')
        outputs.append(dict(case=label, exit_code=result.returncode, **payload))
    (project / 'product.py').write_text(dedent(unit.initial).lstrip(), encoding='utf-8')
    return outputs


# Host-only tool exposes workflow progression, not direct provider/model execution.
HOST_EXTENSION = '''import {spawnSync} from 'node:child_process';
export default function(pi) {
  pi.registerTool({name:'benchmark_next',label:'Next frozen benchmark cells',
    description:'Return next canonical crew references from frozen benchmark workflow. Invoke task with exact crew reference, at most two child calls. Never plan replacement work.',
    parameters:pi.zod.object({}),
    async execute() {
      const r=spawnSync(process.env.CREWS_OMP_PYTHON,[process.env.BENCHMARK_RUNNER,'--bridge',process.env.BENCHMARK_PROJECT,process.env.BENCHMARK_SLOT,process.env.BENCHMARK_SESSION],{encoding:'utf8',env:process.env});
      if(r.status!==0)throw Error(r.stderr||r.stdout||'benchmark bridge failed');
      const value=JSON.parse(r.stdout);
      return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
    }});
}
'''


def native_run(args, output, project, unit, arm, spec, state, host_extension):
    validate_runtime(ROOT,output,args.agent_dir)
    session = 'benchmark-' + unit.id + '-' + arm
    profile = 'baseline' if arm == 'baseline' else 'sdlc_cost_aware'
    request = dict(operation='workflow_prepare', slot='benchmark', session=session,
                   profile=profile, confirmed=True, workflow=spec)
    prepared = workflow.dispatch(request, str(project), str(state))
    save(output / (unit.id + '-' + arm + '-prepared.json'), prepared)
    env = dict(os.environ, CREWS_OMP_HOME=str(state), CREWS_OMP_PYTHON=sys.executable,
               CREWS_OMP_AGENT_DIR=str(args.agent_dir.resolve()),PI_CODING_AGENT_DIR=str(args.agent_dir.resolve()),
               BENCHMARK_RUNNER=str(Path(__file__).resolve()), BENCHMARK_PROJECT=str(project),
               BENCHMARK_SLOT='benchmark', BENCHMARK_SESSION=session, PYTHONUTF8='1',
               PYTHONDONTWRITEBYTECODE='1')
    native_config=output/'native-config.yml'
    if not native_config.exists():raise ValueError('frozen native configuration missing')
    argv = [args.omp, '--cwd', str(project), '--no-extensions', '-e', str(ROOT),
            '-e', str(host_extension), '--config',str(native_config),'--model', args.main_model, '--mode', 'json',
            '--no-session', '--max-time', str(args.timeout), '-p',
            'Execute ONLY frozen benchmark workflow. Call benchmark_next, then task with each exact returned crew reference {run,role,session}. Never use ordinary task, intake, replacement plan, direct writes, provider calls, repair or escalation. Repeat benchmark_next until complete or blocked. At most two native children concurrently. On blocked/failed stop and preserve evidence. This is reconstructed benchmark, not production.']
    # Persist before launch; killed process remains launched, never auto-replayed.
    launch = output / (unit.id + '-' + arm + '-launch.json')
    save(launch, dict(argv=argv, state='launched', workflow_id=prepared['workflow_id']))
    print(json.dumps(dict(event='arm_started',unit=unit.id,arm=arm,workflow_id=prepared['workflow_id'])),flush=True)
    log = output / (unit.id + '-' + arm + '-native.jsonl')
    err = output / (unit.id + '-' + arm + '-stderr.txt')
    try:
        with log.open('w', encoding='utf-8') as stdout, err.open('w', encoding='utf-8') as stderr:
            process = subprocess.run(argv, cwd=project, env=env, stdout=stdout, stderr=stderr,
                                     timeout=args.timeout + 60)
        result = dict(exit_code=process.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = dict(error=str(exc))
    validate_runtime(ROOT,output,args.agent_dir)
    status = workflow.dispatch(dict(operation='workflow_status', slot='benchmark', session=session),
                               str(project), str(state))
    save(output / (unit.id + '-' + arm + '-terminal.json'), dict(process=result, workflow=status))
    print(json.dumps(dict(event='arm_finished',unit=unit.id,arm=arm,complete=status.get('complete',False),blocked=status.get('blocked'),process=result)),flush=True)
    return dict(unit=unit.id, arm=arm, workflow_id=prepared['workflow_id'], project=str(project))


def run(args):
    output = args.output.resolve()
    validate_runtime(ROOT,output,args.agent_dir)
    state = output / 'state'
    state.mkdir()
    os.environ['CREWS_OMP_HOME'] = str(state)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    if args.policy:
        policy = adapter.validate_policy(json.loads(args.policy.read_text(encoding='utf-8')))
        save(state / 'policy.json', policy)
    elif not args.validate_only:
        raise ValueError('--policy required: no implicit default models for native execution')
    if not args.validate_only and (not args.agent_dir or not args.agent_dir.is_dir() or not args.main_model):
        raise ValueError('--agent-dir and --main-model required for real native execution')
    corpus = units()
    if args.units:
        requested=set(args.units)
        if len(requested)!=len(args.units) or not requested<={unit.id for unit in corpus}:raise ValueError('unique existing regression unit IDs required')
        corpus=tuple(unit for unit in corpus if unit.id in requested)
    specs, projects, frozen_units = {}, {}, []
    validation = []
    for index, unit in enumerate(corpus):
        for arm in ('baseline', 'candidate'):
            project = output / 'projects' / unit.id / arm
            install_unit(unit, project)
            projects[unit.id, arm] = project
            specs[unit.id, arm] = manifest(unit, arm, project)
        baseline = projects[unit.id, 'baseline']
        spec = specs[unit.id, 'baseline']
        before = fingerprints(str(baseline), list(dict.fromkeys(spec['authority']['read'] + spec['authority']['write'])))
        other = projects[unit.id, 'candidate']
        if before != fingerprints(str(other), list(before)):
            raise ValueError('paired initial snapshot mismatch')
        frozen_units.append(dict(id=unit.id, family=unit.family, source_group='reconstructed-' + unit.id,
                                 split='holdout', expected_abstain=False,
                                 before_hash=digest(dict(acceptance=unit.acceptance, before=before)),
                                 acceptance_hash=digest(unit.acceptance)))
        # Persist canonical manifests outside all writer scopes.
        for arm in ('baseline', 'candidate'):
            save(output / (unit.id + '-' + arm + '-manifest.json'), specs[unit.id, arm])
        if args.validate_only:
            validation.append(dict(unit=unit.id, cases=offline_check(unit, baseline)))
    environment = dict(python=sys.version, platform=platform.platform())
    controls = [workflow._policy(str(p), str(state)) for p in projects.values()]
    if any(policy != controls[0] for policy in controls):
        raise ValueError('all arms/units require identical frozen policy')
    arms = {arm: dict(profile=profile, model=controls[0]['model'], policy=controls[0], environment=environment)
            for arm, profile in (('baseline', 'baseline'), ('candidate', 'sdlc_cost_aware'))}
    frozen = dict(units=frozen_units, arms=arms, noninferiority_margin=0,
                  max_latency_ratio=args.max_latency_ratio, evaluation_mode='quality_only')
    # Test-only signer is legal ONLY in this newly created isolated state.
    from approval_fixture import Signer
    signer = Signer()
    signed = signer.approve(dict(operation='freeze', spec=frozen), str(output), str(state))
    frozen_result = evaluation.dispatch(signed, str(output), str(state))
    save(output / 'frozen.json', dict(result=frozen_result, request=signed,
                                    claim='reconstructed benchmark only; money not evaluated'))
    # Drop private signing material before any native process starts.
    del signer, signed
    if args.validate_only:
        save(output / 'validation.json', validation)
        print(json.dumps(dict(status='COMPLETE', mode='validate_only', units=len(corpus),
                              canonical_manifests=len(specs), checks='original fails; solution passes all normal/error/boundary criteria; signed quality_only freeze; no provider calls')))
        return
    host_extension = ROOT / 'benchmark-host.ts'
    schedule = [(unit, arm) for index, unit in enumerate(corpus)
                for arm in (('baseline', 'candidate') if index % 2 == 0 else ('candidate', 'baseline'))]
    save(output / 'schedule.json', [dict(unit=u.id, arm=arm) for u, arm in schedule])
    refs = []
    for unit, arm in schedule:
        if (output/'STOP').exists():
            save(output/'stopped.json',dict(reason='operator stop marker',completed_arms=len(refs)));break
        try:
            refs.append(native_run(args, output, projects[unit.id, arm], unit, arm,
                                   specs[unit.id, arm], state, host_extension))
        except Exception as exc:
            # Retain exact failure; never retry or omit it from interpretation.
            save(output / (unit.id + '-' + arm + '-harness-failure.json'), dict(error=str(exc)))
            validate_runtime(ROOT,output,args.agent_dir)
    validate_runtime(ROOT,output,args.agent_dir)
    request = dict(operation='report', evaluation_id=frozen_result['evaluation_id'], results=refs)
    save(output / 'report-request.json', request)
    try:
        report = evaluation.dispatch(request, str(output), str(state))
    except Exception as exc:
        report = dict(rollout='NO_GO', error=str(exc), missing_pairs=2*len(corpus)-len(refs),
                      evaluation_mode='quality_only', money_status='not_evaluated')
    report['runtime_provenance']=dict(source_digest=digest(validate_runtime(ROOT,output,args.agent_dir)['source']),host_configuration_pinned=True,strict_native_output=True)
    report['benchmark_claim'] = 'Previously seen reconstructed regression tasks only; no unseen holdout, production or savings claim'
    save(output / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bridge', nargs=3, metavar=('PROJECT', 'SLOT', 'SESSION'), help=argparse.SUPPRESS)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--snapshot-worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--agent-dir', type=Path)
    parser.add_argument('--main-model')
    parser.add_argument('--omp', default='omp')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--max-latency-ratio', type=float, default=1.2)
    parser.add_argument('--units',nargs='+',help='Explicit known regression unit IDs; never new unseen holdout')
    args = parser.parse_args()
    if args.bridge:
        project, slot, session = args.bridge
        validate_runtime(ROOT,ROOT.parent,os.environ.get('CREWS_OMP_AGENT_DIR'))
        value=workflow.dispatch(dict(operation='workflow_next',slot=slot,session=session,confirmed=True),project)
        validate_runtime(ROOT,ROOT.parent,os.environ.get('CREWS_OMP_AGENT_DIR'))
        print(json.dumps(value))
        return
    if args.output is None:
        parser.error('--output new directory required')
    if args.timeout < 1 or not 1 <= args.max_latency_ratio <= 2:
        parser.error('timeout must be positive; max-latency-ratio must be 1..2')
    if not args.snapshot_worker:
        raise SystemExit(launch_snapshot(ROOT,args,sys.argv[1:],HOST_EXTENSION))
    if Path(__file__).resolve()!=args.output.resolve()/'runtime'/Path('plans/20261028-sdlc-micro-loops/benchmark/runner.py'):
        raise ValueError('snapshot worker must execute reserved runtime copy')
    run(args)


if __name__ == '__main__':
    main()
