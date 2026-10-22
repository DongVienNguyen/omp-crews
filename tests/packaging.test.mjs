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
    const result=execute(process.execPath,[path.join(pkg,'bin','crews-omp.mjs'),command,'--json','--python',python,...args],env);
    let data; try {data=JSON.parse(result.stdout);} catch {assert.fail(result.stdout+result.stderr);}
    return {...result,data};
  };
  try {
    const inventory=plugin('list');
    assert.equal(inventory.status,0,inventory.stderr);
    const entries=JSON.parse(inventory.stdout);
    assert.deepEqual(entries.npm,[], 'PI_CONFIG_DIR must isolate native plugins before any link');
    fs.writeFileSync(path.join(agent,'models.yml'),'providers:\n  9router:\n    apiKey: NEVER_PRINT_THIS_SECRET\n    models:\n      - id: code-seek\n        thinking: {efforts: [high]}\n      - id: code-sol\n        thinking: {efforts: [low, medium, high, xhigh]}\n      - id: code-astra\n        thinking: {efforts: [low, medium, high]}\n');
    const models=fs.readFileSync(path.join(agent,'models.yml'));
    const setup=cli('setup');
    assert.equal(setup.status,0,JSON.stringify(setup.data));
    const runtime=JSON.parse(fs.readFileSync(path.join(state,'runtime.json')));
    assert.ok(runtime.python.startsWith(path.join(state,'venvs')));
    const isolated=execute(runtime.python,['-c','import sys,importlib.metadata as m;assert sys.prefix!=sys.base_prefix;assert m.version("mcp")=="1.27.0";assert m.version("PyYAML")=="6.0.3";assert any(d.metadata["Name"].lower()=="pywin32" for d in m.distributions())==(sys.platform=="win32")'],env);
    assert.equal(isolated.status,0,isolated.stderr);
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
    const policy={provider:'custom-router',models:{haiku:'fast',sonnet:'balanced',opus:'deep'}};
    fs.writeFileSync(policyFile,JSON.stringify(policy));
    const customModels=Buffer.from('providers:\n  custom-router:\n    apiKey: NEVER_PRINT_THIS_SECRET\n    models:\n      - id: fast\n        thinking: {efforts: [high]}\n      - id: balanced\n        thinking: {efforts: [low, medium, high, xhigh]}\n      - id: deep\n        thinking: {efforts: [low, medium, high]}\n');
    fs.writeFileSync(path.join(agent,'models.yml'),customModels);
    const customDoctor=cli('doctor');
    success(customDoctor);
    assert.deepEqual(Object.keys(customDoctor.data.aliases).sort(),['custom-router/balanced','custom-router/deep','custom-router/fast']);
    assert.ok(!customDoctor.stdout.includes('NEVER_PRINT_THIS_SECRET'));
    assert.deepEqual(fs.readFileSync(path.join(agent,'models.yml')),customModels);
    assert.deepEqual(JSON.parse(fs.readFileSync(policyFile)),policy);
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
    upgraded.version='0.2.1';fs.writeFileSync(packageFile,JSON.stringify(upgraded));
    const defaultPolicy={provider:'9router',models:{haiku:'code-seek',sonnet:'code-sol',opus:'code-astra'}};
    fs.writeFileSync(policyFile,JSON.stringify(defaultPolicy));
    success(cli('setup'));
    const newPython=JSON.parse(fs.readFileSync(path.join(state,'runtime.json'))).python;
    assert.notEqual(newPython,oldPython);
    assert.ok(newPython.includes('0.2.1-py'));
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
    assert.ok(fs.existsSync(path.join(state,'run-counter.json')));
    success(cli('setup','--offline','--register-plugin'));
    success(cli('doctor'));
  } finally {
    // Every native operation uses isolated plugin root; never touch user's plugins.
    fs.rmSync(temp,{recursive:true,force:true});
  }
});
