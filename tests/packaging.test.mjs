import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { transact, samePath } from '../bin/crews-omp.mjs';
import { resolveRuntime } from '../runtime-paths.mjs';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.CREWS_OMP_TEST_PYTHON || (process.platform === 'win32' ? path.join(os.homedir(),'.local/share/crews-omp/runtime-venv/Scripts/python.exe') : 'python3');
function execute(exe,args,env) {
  const result=spawnSync(exe,args,{env,encoding:'utf8',shell:false,windowsHide:true,timeout:300000});
  assert.ifError(result.error);
  return result;
}
test('combo commands validate and persist strict policy', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-combo-')); const state=path.join(temp,'state');
  const policyFile=path.join(state,'policy.json');
  const env={...process.env,CREWS_OMP_HOME:state,CREWS_OMP_USER_HOME:temp,PI_CONFIG_DIR:'.omp',OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),...args,'--python',python,'--json'],env);let data;try{data=JSON.parse(result.stdout);}catch{assert.fail(result.stdout+result.stderr);}return {...result,data};};
  try {
    const shown=call('combo','show'); assert.equal(shown.status,0,shown.stdout); assert.equal(shown.data.policy.combos.Small.effort,'Auto');
    assert.ok(!fs.existsSync(state),'show must not create policy or runtime state');
    const changed=call('combo','set','--provider','custom','--small-model','shared','--small-effort','low','--medium-model','balanced','--medium-effort','mEdIuM','--large-model','shared','--large-effort','HIGH');
    assert.equal(changed.status,0,changed.stdout); assert.equal(changed.data.policy.provider,'custom'); assert.equal(changed.data.policy.combos.Small.effort,'Low'); assert.equal(changed.data.policy.combos.Medium.effort,'Medium'); assert.equal(changed.data.policy.combos.Large.effort,'High');
    assert.equal(changed.data.policy.combos.Small.model,changed.data.policy.combos.Large.model,'combo models may be reused');
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),changed.data.policy);
    const auto=call('combo','set','--small-model','new-fast'); assert.equal(auto.status,0,auto.stdout);
    assert.equal(auto.data.policy.combos.Small.effort,'Auto'); assert.equal(auto.data.policy.combos.Large.effort,'High');
    const persisted=fs.readFileSync(policyFile);
    for(const args of [['combo','set','--small-effort','Turbo'],['combo','set','--small-model'],['combo','show','--provider','bad'],['policy','show'],['combo','set','--haiku','old']]) {
      const invalid=call(...args); assert.equal(invalid.status,1,invalid.stdout); assert.deepEqual(fs.readFileSync(policyFile),persisted);
    }
    assert.deepEqual(fs.readdirSync(state).filter(name=>!['runs.sqlite','runs.sqlite-wal','runs.sqlite-shm'].includes(name)),['policy.json'],'serialized atomic policy writes leave no temporary files');
    fs.writeFileSync(policyFile,JSON.stringify({...auto.data.policy,unexpected:true})); const invalidFile=call('combo','show'); assert.equal(invalidFile.status,1); assert.match(invalidFile.data.error,/Invalid combo policy/);
    const corrupt=fs.readFileSync(policyFile); assert.equal(call('combo','set','--provider','other').status,1); assert.deepEqual(fs.readFileSync(policyFile),corrupt);
    const legacy={provider:'legacy',models:{haiku:'legacy-fast',sonnet:'legacy-balanced',opus:'legacy-deep'}};
    fs.writeFileSync(policyFile,JSON.stringify(legacy)); assert.equal(call('combo','show').status,1); assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),legacy);
    const imported=call('combo','set','--large-effort','high'); assert.equal(imported.status,0,imported.stdout);
    assert.deepEqual(imported.data.policy,{provider:'legacy',combos:{Small:{model:'legacy-fast',effort:'Auto'},Medium:{model:'legacy-balanced',effort:'Auto'},Large:{model:'legacy-deep',effort:'High'}}});
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),imported.data.policy);
    fs.writeFileSync(policyFile,'invalid json');
    const reset=call('combo','reset'); assert.equal(reset.status,0,reset.stdout); assert.deepEqual(reset.data.policy,shown.data.policy);
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),shown.data.policy);
    const selected=path.join(temp,'selected-state');
    const explicit=call('combo','set','--state-dir',selected,'--provider','selected'); assert.equal(explicit.status,0,explicit.stdout);
    assert.equal(JSON.parse(fs.readFileSync(path.join(selected,'policy.json'))).provider,'selected');
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),shown.data.policy);
    delete env.CREWS_OMP_HOME;
    const profile=call('combo','set','--profile','work','--provider','profile'); assert.equal(profile.status,0,profile.stdout);
    assert.equal(JSON.parse(fs.readFileSync(path.join(temp,'.omp/profiles/work/crews-omp/policy.json'))).provider,'profile');
    assert.equal(call('combo','show','--profile','../escape').status,1);
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('learning commands require project and explicit admin confirmation before runtime access', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-learning-gates-'));
  const state=path.join(temp,'state');
  const env={...process.env,CREWS_OMP_HOME:state,CREWS_OMP_USER_HOME:temp,OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'learning',...args,'--json'],env);return {...result,data:JSON.parse(result.stdout)};};
  try {
    for(const operation of ['status','observations','rules','report','feedback_options','feedback','label','activate','rollback','purge','configure']) {
      const missing=call(operation); assert.equal(missing.status,1); assert.match(missing.data.error,/require --project/);
    }
    for(const args of [['feedback'],['label'],['activate'],['rollback'],['purge'],['configure','--mode','on']]) {
      const refused=call(...args,'--project',temp); assert.equal(refused.status,1); assert.match(refused.data.error,/requires explicit --yes/);
    }
    for(const args of [['feedback_options','--run','unexpected'],['feedback','--yes'],['feedback','--yes','false'],['feedback','--yes','--run','run','--role','role','--session','session']]) {
      const invalid=call(...args,'--project',temp); assert.equal(invalid.status,1); assert.ok(!/Provision isolated runtime/.test(invalid.data.error));
    }
    const blank=call('feedback','--project',' ','--yes'); assert.equal(blank.status,1); assert.match(blank.data.error,/require --project/);
    const missingRuntime=call('status','--project',temp); assert.equal(missingRuntime.status,1); assert.match(missingRuntime.data.error,/Provision isolated runtime/);
    assert.ok(!fs.existsSync(state),'confirmation and scope failures must not provision runtime or learning data');
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('storage commands validate destructive gates before runtime access without provisioning', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-storage-gates-'));
  const state=path.join(temp,'state');
  const env={...process.env,CREWS_OMP_HOME:state,CREWS_OMP_USER_HOME:temp,OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'storage',...args,'--json'],env);return {...result,data:JSON.parse(result.stdout)};};
  try {
    for(const args of [['unknown'],['compact'],['status','--yes'],['status','--dry-run'],['compact','--yes','--dry-run'],['cleanup','--yes','--dry-run'],['cleanup','--yes','false'],['cleanup','--project',temp],['status','--profile','../bad'],['cleanup','--offline']]) {
      const refused=call(...args); assert.equal(refused.status,1); assert.equal(refused.data.ok,false); assert.ok(!/Provision isolated runtime/.test(refused.data.error));
    }
    for(const args of [[],['status'],['cleanup'],['cleanup','--dry-run'],['cleanup','--yes'],['compact','--yes']]) {
      const missing=call(...args); assert.equal(missing.status,1); assert.match(missing.data.error,/Provision isolated runtime/);
    }
    assert.ok(!fs.existsSync(state),'invalid storage commands and missing runtime must not create state');
    for(const args of [[],['status'],['cleanup'],['cleanup','--dry-run']]) {
      const result=call(...args,'--python',python); assert.equal(result.status,0,result.stdout+result.stderr);
      if(args[0]==='cleanup') assert.equal(result.data.dry_run,true);
      assert.ok(!fs.existsSync(state),'storage status and cleanup preview must not initialize state or learning');
    }
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('storage CLI honors profile and state, previews cleanup, compacts, and preserves unrelated state', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-storage-'));
  const profileState=path.join(temp,'.omp/profiles/work/crews-omp');
  const state=path.join(temp,'selected');
  const env={...process.env,CREWS_OMP_HOME:'',CREWS_OMP_USER_HOME:temp,PI_CONFIG_DIR:'.omp',OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'storage',...args,'--json'],env);return {...result,data:JSON.parse(result.stdout)};};
  const success=result=>assert.equal(result.status,0,result.stdout+result.stderr);
  const snapshot=dir=>fs.readdirSync(dir,{recursive:true,withFileTypes:true}).filter(entry=>entry.isFile()).map(entry=>{const file=path.join(entry.parentPath || entry.path,entry.name);const stat=fs.statSync(file);return [path.relative(dir,file),fs.readFileSync(file).toString('hex'),stat.mtimeMs];}).sort((a,b)=>a[0].localeCompare(b[0]));
  try {
    const profile=call('status','--profile','work','--python',python); success(profile); assert.equal(profile.data.state,profileState); assert.ok(!fs.existsSync(profileState));
    const selected=call('status','--profile','work','--state-dir',state,'--python',python); success(selected); assert.equal(selected.data.state,state); assert.ok(!fs.existsSync(state));
    fs.mkdirSync(state,{recursive:true});
    fs.writeFileSync(path.join(state,'runtime.json'),JSON.stringify({python}));
    const fixture=String.raw`import json,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from crews.omp_adapter import database
from crews.learning import dispatch
state=Path(sys.argv[2])
with database(state) as db:
    db.execute('CREATE TABLE storage_fixture (payload BLOB)')
    db.executemany('INSERT INTO storage_fixture VALUES (?)',[(b'x'*4096,)]*128)
    db.execute('DELETE FROM storage_fixture')
dispatch({'operation':'status','project':sys.argv[3]})
for name in ('tickets','wire','backups'):(state/name).mkdir(exist_ok=True)
token='a'*32
(state/'tickets'/f'{token}.json').write_text(json.dumps({'token':token,'run':'b'*32,'expires':time.time()-7200}))
(state/'wire'/f'{token}.json').write_text('{"private":"NEVER_PRINT_STORAGE_SECRET"}')
(state/'config.json').write_text('{"private":"NEVER_PRINT_STORAGE_SECRET"}')
(state/'backups'/'keep.json').write_text('{"private":"NEVER_PRINT_STORAGE_SECRET"}')
(state/'unknown.json').write_text('NEVER_PRINT_STORAGE_SECRET')`;
    success(execute(python,['-B','-c',fixture,source,state,temp],{...env,CREWS_OMP_HOME:state,PYTHONDONTWRITEBYTECODE:'1'}));
    const protectedFiles=['runtime.json','learning.key','learning.sqlite','config.json','backups/keep.json','unknown.json'];
    const preserved=Object.fromEntries(protectedFiles.map(file=>[file,fs.readFileSync(path.join(state,file))]));
    const before=snapshot(state);
    const status=call('status','--state-dir',state); success(status); assert.equal(status.data.database.exists,true); assert.deepEqual(snapshot(state),before,'status must not write, checkpoint, initialize, or infer');
    for(const args of [[],['--dry-run']]) {
      const preview=call('cleanup',...args,'--state-dir',state); success(preview); assert.equal(preview.data.dry_run,true); assert.ok(preview.data.deleted_files.length>=2); assert.deepEqual(snapshot(state),before,'preview must leave all files unchanged');
    }
    const cleanup=call('cleanup','--yes','--state-dir',state); success(cleanup); assert.equal(cleanup.data.dry_run,false); assert.ok(!fs.existsSync(path.join(state,'tickets',`${'a'.repeat(32)}.json`))); assert.ok(!fs.existsSync(path.join(state,'wire',`${'a'.repeat(32)}.json`)));
    const compact=call('compact','--yes','--state-dir',state); success(compact); assert.ok(compact.data.before_bytes>=compact.data.after_bytes); assert.ok(compact.data.reclaimed_bytes>0);
    for(const [file,content] of Object.entries(preserved)) assert.deepEqual(fs.readFileSync(path.join(state,file)),content,`${file} must remain byte-identical`);
    for(const result of [status,cleanup,compact]) assert.ok(!result.stdout.includes('NEVER_PRINT_STORAGE_SECRET'));
    assert.ok(!fs.existsSync(profileState));
    const active=path.join(state,'tickets',`${'c'.repeat(32)}.json`);
    fs.writeFileSync(active,JSON.stringify({token:'c'.repeat(32),run:'d'.repeat(32),expires:Date.now()/1000+3600,private:'NEVER_PRINT_STORAGE_SECRET'}));
    const refused=call('compact','--yes','--state-dir',state); assert.equal(refused.status,1); assert.equal(refused.data.status,'refused'); assert.ok(refused.data.action); assert.ok(!refused.stdout.includes('NEVER_PRINT_STORAGE_SECRET')); fs.rmSync(active);
    const locked=String.raw`import json,sqlite3,subprocess,sys
db=sqlite3.connect(sys.argv[1])
db.execute('BEGIN IMMEDIATE')
try:
    result=subprocess.run(sys.argv[2:],capture_output=True,text=True,timeout=60)
    print(json.dumps({'status':result.returncode,'stdout':result.stdout,'stderr':result.stderr}))
finally:db.rollback();db.close()`;
    const lockResult=execute(python,['-B','-c',locked,path.join(state,'runs.sqlite'),process.execPath,path.join(source,'bin/crews-omp.mjs'),'storage','compact','--yes','--state-dir',state,'--json'],env); success(lockResult);
    const busy=JSON.parse(lockResult.stdout); assert.equal(busy.status,1); const busyData=JSON.parse(busy.stdout); assert.equal(busyData.status,'busy'); assert.ok(busyData.action); assert.ok(!busy.stdout.includes('NEVER_PRINT_STORAGE_SECRET'));
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('learning CLI keeps labels explicit, activation gated and project data private', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-learning-')); const state=path.join(temp,'state');
  const env={...process.env,CREWS_OMP_HOME:state,CREWS_OMP_USER_HOME:temp,OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'learning',...args,'--project',temp,'--python',python,'--json'],env);return {...result,data:JSON.parse(result.stdout)};};
  const success=result=>assert.equal(result.status,0,result.stdout+result.stderr);
  const observe=()=>{
    const script=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom crews.learning import dispatch\nprint(json.dumps(dispatch({'operation':'observe','project':sys.argv[2],'role':{'kind':'produce','mission':'PRIVATE_TASK_TEXT','answers':{'divisible':0},'facts':{'unknown_cause':False,'consequential_judgment':False,'behavior_undecided':False}},'context_fingerprint':'context','policy_version':'policy','proposal':{'need':'repeatable_task','difficulty':0}})))`;
    const result=execute(python,['-c',script,source,temp],env); success(result); return JSON.parse(result.stdout).observation_id;
  };
  try {
    const initial=call('status'); success(initial); assert.equal(initial.data.mode,'shadow'); assert.equal(initial.data.observations,0); assert.equal(initial.data.labels,0); assert.equal(initial.data.audit_every,10);
    assert.deepEqual(call('observations').data.observations,[]); assert.deepEqual(call('rules').data.rules,[]);
    const feedbackOptions=call('feedback_options'); success(feedbackOptions); assert.ok(!feedbackOptions.stdout.includes('PRIVATE_TASK_TEXT'));
    const label=(id,split,unit)=>call('label','--id',id,'--need','repeatable_task','--difficulty','0','--evidence','PRIVATE_EVIDENCE','--split',split,'--unit-id',unit,'--yes');
    const first=observe();
    const invalid=label(first,'invalid','unit-0'); assert.equal(invalid.status,1); assert.ok(!invalid.stdout.includes('PRIVATE_EVIDENCE')); assert.equal(call('status').data.labels,0);
    const accepted=label(first,'train','unit-0'); success(accepted); assert.equal(accepted.data.rule_id,null);
    success(label(observe(),'train','unit-1'));
    const candidate=label(observe(),'train','unit-2'); success(candidate); const rule=candidate.data.rule_id; assert.ok(rule); assert.equal(candidate.data.state,'candidate');
    assert.equal(call('activate','--id',rule,'--yes').status,1,'insufficient independently labelled evidence must reject activation');
    for(let i=3;i<5;i++) success(label(observe(),'holdout',`unit-${i}`));
    const ready=call('rules'); success(ready); assert.equal(ready.data.rules[0].state,'shadow_ready');
    assert.equal(call('activate','--id',rule).status,1); assert.equal(call('rules').data.rules[0].state,'shadow_ready','readiness must not silently activate');
    success(call('configure','--mode','on','--yes')); assert.equal(call('rules').data.rules[0].state,'shadow_ready','mode on must not silently activate');
    const otherProject=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'learning','status','--project',path.join(temp,'other'),'--python',python,'--json'],env); success(otherProject); assert.equal(JSON.parse(otherProject.stdout).mode,'shadow'); assert.equal(JSON.parse(otherProject.stdout).observations,0);
    success(call('activate','--id',rule,'--yes')); assert.equal(call('rules').data.rules[0].state,'active');
    for(const op of ['status','observations','rules']) {const result=call(op); success(result); assert.ok(!result.stdout.includes('PRIVATE_TASK_TEXT')); assert.ok(!result.stdout.includes('PRIVATE_EVIDENCE'));}
    success(call('rollback','--id',rule,'--yes')); assert.equal(call('rules').data.rules[0].state,'rolled_back');
    success(call('configure','--mode','off')); assert.equal(call('status').data.mode,'off');
    success(call('purge','--yes')); assert.equal(call('status').data.observations,0); assert.deepEqual(call('rules').data.rules,[]);
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('routing report requires project and returns only read-only scoped aggregates', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-report-')); const state=path.join(temp,'state');
  const env={...process.env,CREWS_OMP_HOME:state,CREWS_OMP_USER_HOME:temp,OMP_PROFILE:'',PI_PROFILE:''};
  const call=(...args)=>{const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'report',...args,'--json'],env);return {...result,data:JSON.parse(result.stdout)};};
  try {
    for(const args of [[],['--project',' ']]) {const result=call(...args); assert.equal(result.status,1); assert.match(result.data.error,/require --project/);}
    assert.equal(call('--project',temp,'--yes').status,1);
    assert.equal(call('--project',temp,'--project').status,1);
    const noRuntime=call('--project',temp); assert.equal(noRuntime.status,1); assert.match(noRuntime.data.error,/Provision isolated runtime/);
    assert.ok(!fs.existsSync(state));
    const empty=call('--project',temp,'--python',python); assert.equal(empty.status,0,empty.stdout); assert.equal(empty.data.calls,0); assert.deepEqual(empty.data.native_usage,{});
    assert.ok(!fs.existsSync(state),'report must not create state');
    const script=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom crews import omp_adapter as a\nwith a.database(sys.argv[3]) as db:\n db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run',a.canonical(sys.argv[2]),'private session',0,json.dumps({'waves':[{'calls':[{'role_id':'role','requested_combo':'Medium','effective_combo':'Small','prompt':'PRIVATE_PROMPT','classification':{'outcome':'declared'}}]}]})))\n db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('run','role','private digest','completed',json.dumps({'native':{'usage':{'input':7,'output':2},'durationMs':3},'output':'PRIVATE_OUTPUT'})))\nprint(json.dumps(a.routing_report(sys.argv[2],sys.argv[3])))`;
    const seeded=execute(python,['-c',script,source,temp,state],env); assert.equal(seeded.status,0,seeded.stderr);
    const before=fs.readFileSync(path.join(state,'runs.sqlite'));
    const report=call('--project',temp,'--python',python); assert.equal(report.status,0,report.stdout);
    assert.deepEqual(report.data,JSON.parse(seeded.stdout)); assert.equal(report.data.calls,1);
    assert.deepEqual(report.data.native_usage,{input:7,output:2,durationMs:3});
    assert.ok(!report.stdout.includes('PRIVATE_')); assert.ok(!report.stdout.includes('private session'));
    assert.deepEqual(fs.readFileSync(path.join(state,'runs.sqlite')),before);
    assert.equal(call('--project',path.join(temp,'missing'),'--python',python).status,1);
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('path matching follows platform case rules', () => {
  assert.equal(samePath('/Crews/Package','/crews/package'),process.platform==='win32');
  assert.ok(samePath(source,path.join(source,'.')));
});

test('help exits successfully without creating runtime state', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-help-'));
  try {
    const state=path.join(temp,'state');
    for(const args of [['--help'],['help'],['setup','--help']]) {
      const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),...args],{...process.env,CREWS_OMP_HOME:state});
      assert.equal(result.status,0,result.stderr);
      assert.match(result.stdout,/Usage: crews-omp/);
    }
    assert.ok(!fs.existsSync(state));
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
});

test('relative config root and named profile share runtime path contract', () => {
  const home=fs.mkdtempSync(path.join(os.tmpdir(),'crews-profile-'));
  try {
    const env={CREWS_OMP_USER_HOME:home,PI_CONFIG_DIR:'.omp',OMP_PROFILE:'work',CREWS_OMP_PYTHON:python};
    const runtime=resolveRuntime(source,env);
    assert.equal(runtime.state,path.join(home,'.omp/profiles/work/crews-omp'));
    assert.equal(runtime.agentDir,path.join(home,'.omp/profiles/work/agent'));
    const result=execute(process.execPath,[path.join(source,'bin/crews-omp.mjs'),'doctor','--json'],{...process.env,...env,HOME:home,USERPROFILE:home,CREWS_OMP_HOME:'',CREWS_OMP_AGENT_DIR:''});
    const data=JSON.parse(result.stdout);
    assert.equal(data.state,runtime.state);
    assert.equal(data.agentDir,runtime.agentDir);
  } finally {fs.rmSync(home,{recursive:true,force:true});}
});


test('migration transaction restores original bytes after mid-commit error', () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-rollback-'));
  const existing=path.join(temp,'config.yml');
  const added=path.join(temp,'mcp.json');
  fs.writeFileSync(existing,'untouched: true\n');
  try {
    assert.throws(()=>transact([existing,added],()=>{
      fs.writeFileSync(existing,'extensions: []\n');
      fs.writeFileSync(added,'{}');
      throw new Error('commit failed');
    },path.join(temp,'state')),/Registration rolled back: commit failed/);
    assert.equal(fs.readFileSync(existing,'utf8'),'untouched: true\n');
    assert.ok(!fs.existsSync(added));
    const backup=path.join(temp,'state','backups',fs.readdirSync(path.join(temp,'state','backups'))[0]);
    assert.equal(fs.readFileSync(path.join(backup,'0'),'utf8'),'untouched: true\n');
  } finally { fs.rmSync(temp,{recursive:true,force:true}); }
});

test('real venv setup, repeat, relocate, doctor, migration rollback, uninstall and reinstall', {timeout:600000}, () => {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-package-'));
  const home=path.join(temp,'home');
  const agent=path.join(home,'custom-agent');
  const state=path.join(home,'state');
  let pkg=path.join(temp,'package');
  fs.cpSync(source,pkg,{recursive:true,filter:p=>!p.includes('__pycache__')&&!p.includes(`${path.sep}tests`)});
  fs.mkdirSync(agent,{recursive:true});
  const env={...process.env,HOME:home,USERPROFILE:home,CREWS_OMP_USER_HOME:home,PI_CONFIG_DIR:path.join(home,'.omp'),PI_CODING_AGENT_DIR:agent,CREWS_OMP_HOME:state,CREWS_OMP_AGENT_DIR:agent};
  const omp=process.env.CREWS_OMP_OMP || 'omp';
  const plugin=(...args)=>execute(omp,['plugin',...args,'--json'],{...env,PI_CONFIG_DIR:'.omp'});
  const success=result=>assert.equal(result.status,0,result.stdout+'\n'+result.stderr);
  const cli=(command,...args)=>{
    const result=execute(process.execPath,[path.join(pkg,'bin','crews-omp.mjs'),command,...args,'--json','--python',python],env);
    let data; try {data=JSON.parse(result.stdout);} catch {assert.fail(result.stdout+result.stderr);}
    return {...result,data};
  };
  try {
    const inventory=plugin('list');
    assert.equal(inventory.status,0,inventory.stderr);
    const entries=JSON.parse(inventory.stdout);
    assert.deepEqual(entries.npm,[], 'PI_CONFIG_DIR must isolate native plugins before any link');
    const modelYaml=String.raw`providers:
  9router:
    apiKey: NEVER_PRINT_THIS_SECRET
    models:
      - id: code-seek
        thinking: {efforts: [low, medium, high]}
      - id: code-sol
        thinking: {efforts: [low, medium, high]}
      - id: code-astra
        thinking: {efforts: [low, medium, high]}
`;
    fs.writeFileSync(path.join(agent,'models.yml'),modelYaml);
    const models=Buffer.from(modelYaml);
    const setup=cli('setup');
    assert.equal(setup.status,0,JSON.stringify(setup.data));
    const runtime=JSON.parse(fs.readFileSync(path.join(state,'runtime.json')));
    assert.ok(runtime.python.startsWith(path.join(state,'venvs')));
    const isolated=execute(runtime.python,['-c','import sys,importlib.metadata as m;assert sys.prefix!=sys.base_prefix;assert m.version("mcp")=="1.27.0";assert m.version("PyYAML")=="6.0.3";assert any(d.metadata["Name"].lower()=="pywin32" for d in m.distributions())==(sys.platform=="win32")'],env);
    assert.equal(isolated.status,0,isolated.stderr);
    assert.ok(!fs.existsSync(path.join(state,'learning.sqlite')),'setup must not initialize learning before explicit use');
    const learningFile=path.join(state,'learning.sqlite');
    const learningStatus=cli('learning','status','--project',temp); success(learningStatus); assert.equal(learningStatus.data.mode,'shadow');
    const learningBefore=fs.readFileSync(learningFile);
    const backupCount=fs.readdirSync(path.join(state,'backups')).length;
    assert.equal(cli('setup','--offline').data.status,'unchanged');
    assert.equal(fs.readdirSync(path.join(state,'backups')).length,backupCount);
    success(plugin('link',pkg,'--scope','user'));
    success(cli('doctor'));
    const currentMcpPath=path.join(agent,'mcp.json');
    const currentMcp=JSON.parse(fs.readFileSync(currentMcpPath));
    currentMcp.mcpServers['crews-omp']=Object.fromEntries(Object.entries(currentMcp.mcpServers['crews-omp']).reverse());
    fs.writeFileSync(currentMcpPath,JSON.stringify(currentMcp));
    success(cli('doctor'));
    assert.ok(!cli('doctor').stdout.includes('NEVER_PRINT_THIS_SECRET'));
    const policyFile=path.join(state,'policy.json');
    const policy={provider:'custom-router',combos:{Small:{model:'fast',effort:'Auto'},Medium:{model:'balanced',effort:'Low'},Large:{model:'deep',effort:'High'}}};
    const customModels=Buffer.from('providers:\n  custom-router:\n    apiKey: NEVER_PRINT_THIS_SECRET\n    models:\n      - id: fast\n        thinking: {efforts: [low, medium, high]}\n      - id: balanced\n        thinking: {efforts: [low, medium, high]}\n      - id: deep\n        thinking: {efforts: [low, medium, high]}\n');
    fs.writeFileSync(policyFile,JSON.stringify(policy));
    fs.writeFileSync(path.join(agent,'models.yml'),customModels);
    const customDoctor=cli('doctor');
    success(customDoctor);
    assert.deepEqual(Object.keys(customDoctor.data.aliases).sort(),['custom-router/balanced','custom-router/deep','custom-router/fast']);
    assert.ok(!customDoctor.stdout.includes('NEVER_PRINT_THIS_SECRET'));
    assert.deepEqual(fs.readFileSync(path.join(agent,'models.yml')),customModels);
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),policy);
    assert.deepEqual(customDoctor.data.aliases['custom-router/balanced'].requiredEfforts,['low']);
    assert.deepEqual(customDoctor.data.aliases['custom-router/deep'].requiredEfforts,['high']);
    assert.deepEqual(customDoctor.data.aliases['custom-router/fast'].requiredEfforts,['low','medium','high']);
    const sharedPolicy={provider:'custom-router',combos:{Small:{model:'shared',effort:'Low'},Medium:{model:'shared',effort:'High'},Large:{model:'shared',effort:'Low'}}};
    fs.writeFileSync(policyFile,JSON.stringify(sharedPolicy));
    fs.writeFileSync(path.join(agent,'models.yml'),'providers:\n  custom-router:\n    models:\n      - id: shared\n        thinking: {efforts: [low, high]}\n');
    const sharedDoctor=cli('doctor'); success(sharedDoctor);
    assert.deepEqual(Object.keys(sharedDoctor.data.aliases),['custom-router/shared']);
    assert.deepEqual(sharedDoctor.data.aliases['custom-router/shared'].combos,['Small','Medium','Large']);
    assert.deepEqual(sharedDoctor.data.aliases['custom-router/shared'].requiredEfforts,['low','high']);
    assert.deepEqual(sharedDoctor.data.aliases['custom-router/shared'].missingEfforts,[]);
    sharedPolicy.combos.Medium.effort='Auto'; fs.writeFileSync(policyFile,JSON.stringify(sharedPolicy));
    const missingAuto=cli('doctor'); assert.equal(missingAuto.status,1);
    assert.deepEqual(missingAuto.data.aliases['custom-router/shared'].missingEfforts,['medium']);
    fs.writeFileSync(policyFile,JSON.stringify(policy));
    fs.writeFileSync(path.join(agent,'models.yml'),customModels);
    fs.writeFileSync(policyFile,JSON.stringify({...policy,unexpected:'NEVER_PRINT_THIS_SECRET'}));
    const invalidPolicy=cli('doctor');
    assert.equal(invalidPolicy.status,1);
    assert.ok(!invalidPolicy.stdout.includes('NEVER_PRINT_THIS_SECRET'));
    fs.unlinkSync(policyFile);
    fs.writeFileSync(path.join(agent,'models.yml'),models);
    fs.writeFileSync(path.join(agent,'models.yml'),'apiKey: [NEVER_PRINT_THIS_SECRET\n');
    const invalidModels=cli('doctor');
    assert.equal(invalidModels.status,1);
    assert.ok(!invalidModels.stdout.includes('NEVER_PRINT_THIS_SECRET'));
    fs.writeFileSync(path.join(agent,'models.yml'),models);
    fs.writeFileSync(path.join(state,'run-counter.json'),'{"runs":73}');
    const relocated=path.join(temp,'relocated');
    fs.renameSync(pkg,relocated);
    pkg=relocated;
    assert.equal(cli('doctor').status,1);
    success(cli('setup','--offline','--register-plugin'));
    assert.deepEqual(fs.readFileSync(learningFile),learningBefore,'relocation retains learning DB');
    success(cli('doctor'));
    assert.equal(JSON.parse(fs.readFileSync(path.join(state,'runtime.json'))).packageRoot,pkg);
    const oldRoot=path.join(home,'.local/share/crews-omp');
    const release=path.join(oldRoot,'releases/0.1.0');
    fs.mkdirSync(release,{recursive:true});
    fs.writeFileSync(path.join(release,'runtime.json'),JSON.stringify({python:path.join(oldRoot,'runtime-venv',process.platform==='win32'?'Scripts/python.exe':'bin/python'),config:path.join(agent,'config.yml'),state}));
    fs.writeFileSync(path.join(agent,'config.yml'),`extensions:\n  - ${JSON.stringify(path.join(release,'extension.ts'))}\nmodelRoles: {default: untouched}\n`);
    const mcpPath=path.join(agent,'mcp.json');
    const unrelated={command:'unrelated-server',args:[]};
    const oldMcp={mcpServers:{unrelated,'crews-omp':{command:path.join(oldRoot,'bin','crews-mcp.exe'),args:[python,path.join(release,'omp_server.py')],env:{CREWS_OMP_HOME:state}}}};
    fs.writeFileSync(mcpPath,JSON.stringify(oldMcp));
    fs.mkdirSync(path.join(agent,'agents'),{recursive:true});
    const name=fs.readdirSync(path.join(pkg,'agents'))[0];
    fs.copyFileSync(path.join(pkg,'agents',name),path.join(agent,'agents',name));
    const skill=path.join(agent,'skills','crew-omp','SKILL.md');
    fs.mkdirSync(path.dirname(skill),{recursive:true});
    fs.copyFileSync(path.join(pkg,'skills','crew-omp','SKILL.md'),skill);
    const before=fs.readFileSync(path.join(agent,'config.yml'));
    assert.equal(cli('migrate','--dry-run').status,0);
    assert.deepEqual(fs.readFileSync(path.join(agent,'config.yml')),before);
    // Modified discovery copy must refuse without changing registration or state.
    fs.appendFileSync(path.join(agent,'agents',name),'\nuser edit');
    assert.equal(cli('migrate').status,1);
    assert.deepEqual(fs.readFileSync(path.join(agent,'config.yml')),before);
    fs.copyFileSync(path.join(pkg,'agents',name),path.join(agent,'agents',name));
    const migrated=cli('migrate');
    assert.equal(migrated.status,0,JSON.stringify(migrated.data));
    assert.ok(!fs.existsSync(path.join(agent,'agents',name)));
    assert.ok(!fs.existsSync(skill));
    assert.deepEqual(JSON.parse(fs.readFileSync(mcpPath)).mcpServers.unrelated,unrelated);
    assert.ok(!fs.readFileSync(path.join(agent,'config.yml'),'utf8').includes('extension.ts'));
    assert.equal(fs.readFileSync(path.join(state,'run-counter.json'),'utf8'),'{"runs":73}');
    assert.deepEqual(fs.readFileSync(path.join(agent,'models.yml')),models);
    success(cli('rollback','--backup',migrated.data.backup,'--dry-run'));
    const migratedConfig=fs.readFileSync(path.join(agent,'config.yml'));
    fs.appendFileSync(path.join(agent,'config.yml'),'# user change\n');
    const refused=cli('rollback','--backup',migrated.data.backup);
    assert.equal(refused.status,1);
    assert.match(refused.data.error,/Modified file preserved/);
    fs.writeFileSync(path.join(agent,'config.yml'),migratedConfig);
    // Explicit rollback also recovers a crash snapshot whose expected hashes were persisted pre-commit.
    const migrationManifest=path.join(migrated.data.backup,'manifest.json');
    const snapshot=JSON.parse(fs.readFileSync(migrationManifest));
    snapshot.status='preparing';fs.writeFileSync(migrationManifest,JSON.stringify(snapshot));
    success(cli('rollback','--backup',migrated.data.backup));
    assert.deepEqual(fs.readFileSync(path.join(agent,'config.yml')),before);
    assert.deepEqual(JSON.parse(fs.readFileSync(mcpPath)),oldMcp);
    assert.ok(fs.existsSync(skill));
    success(plugin('link',pkg,'--scope','user'));
    success(cli('migrate'));
    const oldPython=JSON.parse(fs.readFileSync(path.join(state,'runtime.json'))).python;
    const packageFile=path.join(pkg,'package.json');
    const upgraded=JSON.parse(fs.readFileSync(packageFile));
    const nextVersion=upgraded.version.split('.').map((value,index)=>index===2?Number(value)+1:Number(value)).join('.');
    upgraded.version=nextVersion;fs.writeFileSync(packageFile,JSON.stringify(upgraded));
    const defaultPolicy={provider:'9router',models:{haiku:'code-seek',sonnet:'code-sol',opus:'code-astra'}};
    fs.writeFileSync(policyFile,JSON.stringify(defaultPolicy));
    success(cli('setup'));
    assert.deepEqual(fs.readFileSync(learningFile),learningBefore,'upgrade retains learning DB');
    const newPython=JSON.parse(fs.readFileSync(path.join(state,'runtime.json'))).python;
    assert.notEqual(newPython,oldPython);
    assert.ok(newPython.includes(`${nextVersion}-py`));
    assert.ok(fs.existsSync(oldPython));
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),defaultPolicy);
    assert.equal(fs.readFileSync(path.join(state,'run-counter.json'),'utf8'),'{"runs":73}');
    assert.deepEqual(fs.readFileSync(path.join(agent,'models.yml')),models);
    success(cli('uninstall','--dry-run'));
    success(cli('doctor'));
    const beforeFailedUninstall=fs.readFileSync(mcpPath);
    const preload=path.join(temp,'fail-native-uninstall.mjs');
    fs.writeFileSync(preload,`import cp from 'node:child_process';import {syncBuiltinESMExports} from 'node:module';const spawn=cp.spawnSync;cp.spawnSync=function(exe,args,options){const result=spawn(exe,args,options);if(args?.[0]==='plugin'&&args?.[1]==='uninstall')return {...result,status:1,stderr:'injected native failure after unlink'};return result;};syncBuiltinESMExports();`);
    env.NODE_OPTIONS=`--import=${pathToFileURL(preload).href}`;
    const failedUninstall=cli('uninstall');
    delete env.NODE_OPTIONS;
    assert.equal(failedUninstall.status,1);
    assert.match(failedUninstall.data.error,/Registration rolled back/);
    assert.deepEqual(fs.readFileSync(mcpPath),beforeFailedUninstall);
    success(cli('doctor'));
    success(cli('uninstall'));
    assert.deepEqual(fs.readFileSync(learningFile),learningBefore,'uninstall retains learning DB');
    assert.ok(fs.existsSync(path.join(state,'run-counter.json')));
    success(cli('setup','--offline','--register-plugin'));
    assert.deepEqual(fs.readFileSync(learningFile),learningBefore,'reinstall retains learning DB');
    success(cli('doctor'));
  } finally {
    // Every native operation uses isolated plugin root; never touch user's plugins.
    fs.rmSync(temp,{recursive:true,force:true});
  }
});
