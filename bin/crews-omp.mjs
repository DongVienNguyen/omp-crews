#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const owner = 'crews-omp/package-v1';
const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const readJSON = (file, fallback = {}) => fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : fallback;
export const samePath = (a, b) => {
  const normalize = value => process.platform === 'win32' ? path.resolve(value).toLowerCase() : path.resolve(value);
  return normalize(a) === normalize(b);
};
const options = { json: false, offline: false, dryRun: false, registerPlugin: false };
let command;
function cli() {
try {
  const args = process.argv.slice(2);
  command = args.shift();
  if(command === 'help' || command === '--help' || args.includes('--help')) {
    console.log('Usage: crews-omp setup|doctor|migrate|uninstall|rollback [options]\n\nCommands:\n  setup      Provision isolated Python runtime and owned MCP registration\n  doctor     Check native plugin, model aliases, and live MCP handshake\n  migrate    Replace owned legacy discovery after native plugin registration\n  uninstall  Unlink native plugin and remove owned MCP registration; retain state\n  rollback   Restore unchanged migration snapshot and unlink new plugin\n\nOptions:\n  --python PATH          Python 3.12+ executable\n  --agent-dir PATH       Selected OMP agent directory\n  --state-dir PATH       Persistent Crews state directory\n  --offline              Install dependencies without package indexes\n  --json                 Machine-readable output\n  --dry-run              Inspect migrate/uninstall/rollback without mutation\n  --register-plugin      Explicitly link package using native OMP CLI\n  --expected-hashes FILE  Migration ownership hashes {files:{absolutePath:sha256}}\n  --backup DIRECTORY     Owned migration snapshot for rollback\n  --help                 Show help without provisioning or changing files');
    return;
  }
  if(command==='policy'){
    const action=args.shift()||'show';
    if(!['show','set','reset'].includes(action))throw Error('Usage: crews-omp policy show|set|reset [--provider ID --haiku ID --sonnet ID --opus ID] [--json]');
    if(args.includes('--json'))options.json=true;
    const loc=locations();const file=path.join(loc.state,'policy.json');const defaults={provider:'9router',models:{haiku:'code-seek',sonnet:'code-sol',opus:'code-astra'}};const current=readJSON(file,defaults);
    if(action==='show'){console.log(options.json?JSON.stringify({ok:true,status:'policy',policy:current}):JSON.stringify(current,null,2));return;}
    if(action==='reset')json(file,defaults);else {const value={provider:current.provider,models:{...current.models}};for(const key of ['provider','haiku','sonnet','opus']){const flag='--'+key;const pos=args.indexOf(flag);if(pos>=0&&args[pos+1])key==='provider'?value.provider=args[pos+1]:value.models[key]=args[pos+1];}json(file,value);}
    console.log(options.json?JSON.stringify({ok:true,status:'policy_updated',policy:readJSON(file)}):JSON.stringify(readJSON(file),null,2));return;
  }
  while (args.length) {
    const arg = args.shift();
    if (['--json', '--offline', '--dry-run', '--register-plugin'].includes(arg)) options[{'--json':'json','--offline':'offline','--dry-run':'dryRun','--register-plugin':'registerPlugin'}[arg]] = true;
    else if (['--python', '--agent-dir', '--state-dir', '--expected-hashes', '--backup'].includes(arg) && args[0] && !args[0].startsWith('--')) options[{'--python':'python','--agent-dir':'agentDir','--state-dir':'state','--expected-hashes':'expectedHashes','--backup':'backup'}[arg]] = args.shift();
    else throw new Error(`Unknown or incomplete argument: ${arg}`);
  }
  if (!['setup', 'doctor', 'migrate', 'uninstall', 'rollback'].includes(command)) throw new Error('Usage: crews-omp setup|doctor|migrate|uninstall|rollback [--python PATH] [--agent-dir PATH] [--state-dir PATH] [--offline] [--json] [--dry-run] [--register-plugin] [--expected-hashes FILE] [--backup DIRECTORY]');
  if (options.dryRun && !['migrate', 'uninstall', 'rollback'].includes(command)) throw new Error('--dry-run is supported by migrate, uninstall and rollback');
  const result = main();
  console.log(options.json ? JSON.stringify(result) : `${result.status}\n${JSON.stringify(result, null, 2)}`);
  if (result.ok === false) process.exitCode = 1;
} catch (error) {
  console[options.json ? 'log' : 'error'](options.json ? JSON.stringify({ok:false, status:'error', command, error:error.message}) : `crews-omp: ${error.message}`);
  process.exitCode = 1;
}
}

function run(executable, args, env = process.env, allowFailure = false) {
  const result = spawnSync(executable, args, {encoding:'utf8', shell:false, windowsHide:true, env, maxBuffer:8*1024*1024});
  if (!allowFailure && (result.error || result.status !== 0)) throw new Error(`${path.basename(executable)} failed (${result.status ?? result.error?.code}): ${(result.stderr || result.stdout || result.error?.message || '').slice(-2000)}`);
  return result;
}
function locations() {
  const home = process.env.CREWS_OMP_USER_HOME || os.homedir();
  const configRoot = path.resolve(home,process.env.PI_CONFIG_DIR || '.omp');
  const profile = process.env.OMP_PROFILE || process.env.PI_PROFILE;
  const agentDir = path.resolve(options.agentDir || process.env.CREWS_OMP_AGENT_DIR || (profile ? path.join(configRoot,'profiles',profile,'agent') : process.env.PI_CODING_AGENT_DIR || path.join(configRoot,'agent')));
  const state = path.resolve(options.state || process.env.CREWS_OMP_HOME || (profile ? path.join(configRoot,'profiles',profile,'crews-omp') : path.join(home,'.crews-omp')));
  return {home,configRoot,agentDir,state,config:path.join(agentDir,'config.yml'),mcp:path.join(agentDir,'mcp.json'),runtime:path.join(state,'runtime.json'),legacy:path.join(home,'.local','share','crews-omp')};
}
function write(file, data) {
  fs.mkdirSync(path.dirname(file), {recursive:true});
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, data);
  fs.renameSync(tmp, file);
}
function json(file, data) { write(file, `${JSON.stringify(data,null,2)}\n`); }
function discoverPython() {
  const probes = options.python ? [[options.python,[]]] : [['python',[]],['py',['-3']]];
  for (const [exe, prefix] of probes) {
    const p = run(exe,[...prefix,'-c','import sys,json;print(json.dumps({"exe":sys.executable,"version":list(sys.version_info[:3])}))'],process.env,true);
    if (p.status === 0) {
      const result = JSON.parse(p.stdout);
      if (result.version[0] === 3 && result.version[1] >= 12) return result;
    }
  }
  throw new Error('Python 3.12+ required; pass --python with its executable path');
}
function dependencies(python) {
  const p = run(python,['-c','import importlib.metadata as m; assert m.version("mcp")=="1.27.0"; assert m.version("PyYAML")=="6.0.3"; import yaml,mcp; print("ok")'],process.env,true);
  return p.status === 0;
}
function provision(loc) {
  const found = discoverPython();
  const lock = fs.readFileSync(path.join(root,'requirements-omp.lock'),'utf8').split(/\r?\n/).filter(line => line.trim()).join('\n')+'\n';
  if (!/^mcp==1\.27\.0$/m.test(lock) || !/^PyYAML==6\.0\.3$/m.test(lock)) throw new Error('Runtime lock must pin mcp==1.27.0 and PyYAML==6.0.3');
  const venv = path.join(loc.state,'venvs',`${version}-py${found.version[0]}.${found.version[1]}-${hash(lock).slice(0,12)}`);
  const python = path.join(venv,process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  if (!fs.existsSync(python)) {
    fs.mkdirSync(path.dirname(venv),{recursive:true});
    run(found.exe,['-m','venv',venv]);
  }
  if (!dependencies(python)) {
    const runtimeLock = path.join(venv,'requirements-omp.lock');
    write(runtimeLock,lock);
    const args = ['-m','pip','--isolated','install','--no-deps','--disable-pip-version-check','--requirement',runtimeLock];
    if (options.offline) args.push('--no-index');
    if (process.env.CREWS_OMP_WHEELHOUSE) args.push('--find-links',path.resolve(process.env.CREWS_OMP_WHEELHOUSE));
    const installed=run(python,args,{...process.env,PYTHONUTF8:'1',PYTHONNOUSERSITE:'1'},true);
    if(installed.error || installed.status !== 0) throw new Error('Isolated dependency installation failed; check offline wheelhouse and package index access');
    if (!dependencies(python)) throw new Error('Isolated runtime dependency validation failed');
  }
  return python;
}
const yamlScript = String.raw`
import sys,json,pathlib,yaml
req=json.loads(sys.argv[1]); p=pathlib.Path(req['file']); doc=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}
doc=doc or {}
if not isinstance(doc,dict): raise ValueError('Configuration must be a mapping')
op=req['op']
if op=='extensions': print(json.dumps(doc.get('extensions',[])))
elif op=='remove':
 old=doc.get('extensions',[])
 doc['extensions']=[x for x in old if x not in req['values']]
 print(yaml.safe_dump(doc,sort_keys=False),end='')
elif op=='models':
 sys.path.insert(0,req['values']['packageRoot'])
 from crews.omp_adapter import model_policy
 policy=model_policy(req['values']['state'])
 providers=doc.get('providers',{})
 models=providers.get(policy['provider'],{}).get('models',[])
 if isinstance(models,dict): models=[dict(v,id=k) for k,v in models.items()]
 out={}
 for seat,needed in {'haiku':['high'],'sonnet':['low','medium','high','xhigh'],'opus':['low','medium','high']}.items():
  name=policy['models'][seat]
  model=next((m for m in models if m.get('id')==name),None)
  efforts=(model or {}).get('thinking',{}).get('efforts',[])
  out[policy['provider']+'/'+name]={'present':model is not None,'missingEfforts':[x for x in needed if x not in efforts]}
 print(json.dumps(out))
`;
function yaml(python,file,op,values) {
  const result = run(python,['-c',yamlScript,JSON.stringify({file,op,values})],process.env,true);
  if(result.status !== 0) throw new Error(`Cannot parse ${path.basename(file)} configuration`);
  return result.stdout;
}
function pluginEnv(loc) {
  const configRoot = loc.configRoot;
  // OMP's plugin CLI resolves PI_CONFIG_DIR relative to user home, including on Windows.
  const relative = path.relative(loc.home, configRoot);
  if(path.isAbsolute(relative)) throw new Error('OMP plugin config must be on same drive as user home');
  return {...process.env,PI_CODING_AGENT_DIR:loc.agentDir,PI_CONFIG_DIR:relative || '.',CREWS_OMP_AGENT_DIR:loc.agentDir,CREWS_OMP_HOME:loc.state};
}
function pluginList(loc) {
  const result = run(process.env.CREWS_OMP_OMP || 'omp',['plugin','list','--json'],pluginEnv(loc));
  return JSON.parse(result.stdout);
}
function pluginPresent(list) {
  const entries = [...(list.npm || []),...(list.marketplace || [])];
  return entries.some(entry => {
    if(!entry.path || entry.enabled === false) return false;
    try { return samePath(fs.realpathSync(entry.path),fs.realpathSync(root)); } catch { return false; }
  });
}
function registered(loc, register = false) {
  if (register) run(process.env.CREWS_OMP_OMP || 'omp',['plugin','link',root,'--scope','user','--json'],pluginEnv(loc));
  return pluginPresent(pluginList(loc));
}
function registration(loc) {
  return {command:process.execPath,args:[path.join(root,'bin','mcp-launcher.mjs')],env:{CREWS_OMP_HOME:loc.state,CREWS_OMP_AGENT_DIR:loc.agentDir},'x-crews-omp-owner':owner};
}
function ownedMcp(entry) { return entry?.['x-crews-omp-owner'] === owner; }
function legacyPlan(loc, python) {
  const extensions = JSON.parse(yaml(python,loc.config,'extensions'));
  if (!Array.isArray(extensions) || extensions.some(x => typeof x !== 'string')) throw new Error('config.extensions must contain paths');
  const releases = path.join(loc.legacy,'releases');
  const oldExtensions = extensions.filter(p => {
    const relative = path.relative(releases,path.resolve(p));
    return relative && !relative.startsWith('..') && !path.isAbsolute(relative) && path.basename(p) === 'extension.ts';
  });
  for(const extension of oldExtensions) {
    const legacyRuntime=readJSON(path.join(path.dirname(extension),'runtime.json'));
    const legacyPython=path.join(loc.legacy,'runtime-venv',process.platform === 'win32'?'Scripts/python.exe':'bin/python');
    if(!legacyRuntime.python || !legacyRuntime.config || !legacyRuntime.state || !samePath(legacyRuntime.python,legacyPython) || !samePath(legacyRuntime.config,loc.config) || !samePath(legacyRuntime.state,loc.state)) throw new Error(`Unowned legacy release registration; preserved: ${extension}`);
  }
  const expectedHashes=options.expectedHashes?readJSON(path.resolve(options.expectedHashes)):{};
  if(options.expectedHashes && (!expectedHashes.files || typeof expectedHashes.files !== 'object')) throw new Error('--expected-hashes requires {"files":{"absolute-path":"sha256"}}');
  const manifest = readJSON(path.join(loc.legacy,'migration.json'));
  const baseline=readJSON(path.join(root,'legacy-owned.json'));
  const files = [];
  const candidates = fs.readdirSync(path.join(root,'agents')).filter(n=>n.endsWith('.md')).map(n=>[path.join(loc.agentDir,'agents',n),path.join(root,'agents',n)]);
  candidates.push([path.join(loc.agentDir,'skills','crew-omp','SKILL.md'),path.join(root,'skills','crew-omp','SKILL.md')]);
  for (const [target,source] of candidates) {
    if (!fs.existsSync(target)) continue;
    const actual = hash(fs.readFileSync(target));
    const expected = [expectedHashes.files?.[target],manifest.new?.[target],baseline.files?.[path.relative(loc.agentDir,target).split(path.sep).join('/')]].filter(value=>value != null);
    if(expected.some(value=>typeof value !== 'string' || !/^[a-f0-9]{64}$/i.test(value))) throw new Error(`Invalid expected hash for ${target}`);
    if (actual !== hash(fs.readFileSync(source)) && !expected.includes(actual)) throw new Error(`Unowned or modified native discovery copy; preserved: ${target}`);
    files.push({path:target,hash:actual});
  }
  const mcp = readJSON(loc.mcp);
  const entry = mcp.mcpServers?.['crews-omp'];
  if (entry && !ownedMcp(entry)) {
    const args = entry.args || [];
    const known = typeof entry.command === 'string' && samePath(entry.command,path.join(loc.legacy,'bin','crews-mcp.exe')) && args.some(a=>typeof a === 'string' && oldExtensions.some(e=>samePath(a,path.join(path.dirname(e),'omp_server.py'))));
    if (!known) throw new Error('Unowned crews-omp MCP registration; preserved');
  }
  return {extensions:oldExtensions,files,legacyMcp:!!entry && !ownedMcp(entry)};
}
export function transact(files, action, state, metadata={}) {
  const originals = files.map(file => ({file,bytes:fs.existsSync(file)?fs.readFileSync(file):null}));
  const backup = path.join(state,'backups',`${Date.now()}-${process.pid}-${crypto.randomUUID().slice(0,8)}`);
  fs.mkdirSync(backup,{recursive:true});
  const manifest={schemaVersion:1,owner,status:'preparing',...metadata,files:originals.map(({file,bytes},index)=>({file,hash:bytes===null?null:hash(bytes),backup:bytes===null?null:String(index),expected:metadata.expected && Object.hasOwn(metadata.expected,file) ? metadata.expected[file] : bytes===null?null:hash(bytes)}))};
  delete manifest.expected;
  originals.forEach(({bytes},index)=>{if(bytes!==null)fs.writeFileSync(path.join(backup,String(index)),bytes);});
  json(path.join(backup,'manifest.json'),manifest);
  try {
    action();
    manifest.status='committed';
    for(const file of manifest.files) file.expected=fs.existsSync(file.file)?hash(fs.readFileSync(file.file)):null;
    json(path.join(backup,'manifest.json'),manifest);
  } catch(error) {
    for(const {file,bytes} of originals) { if(bytes===null) fs.rmSync(file,{force:true}); else write(file,bytes); }
    manifest.status='rolled_back';json(path.join(backup,'manifest.json'),manifest);
    throw new Error(`Registration rolled back: ${error.message}`);
  }
  return backup;
}
function restorePlugin(loc) {
  if(!registered(loc)) {
    run(process.env.CREWS_OMP_OMP || 'omp',['plugin','link',root,'--scope','user','--json'],pluginEnv(loc));
    if(!registered(loc)) throw new Error('Native plugin restoration failed');
  }
}
function unlinkPlugin(loc) {
  try {
    run(process.env.CREWS_OMP_OMP || 'omp',['plugin','uninstall','crews-omp','--scope','user','--json'],pluginEnv(loc));
    if(registered(loc)) throw new Error('Native plugin remained linked after uninstall');
  } catch(error) {
    try {restorePlugin(loc);} catch(restore) {throw new Error(`Native uninstall failed; plugin restoration failed: ${restore.message}`);}
    throw error;
  }
}
function rollback(loc) {
  if(!options.backup) throw new Error('rollback requires --backup DIRECTORY');
  const backup=fs.realpathSync(path.resolve(options.backup));
  const backupRoot=fs.realpathSync(path.join(loc.state,'backups'));
  const relative=path.relative(backupRoot,backup);
  if(!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Rollback snapshot must be inside selected state backups');
  const manifest=readJSON(path.join(backup,'manifest.json'));
  if(manifest.owner!==owner || manifest.schemaVersion!==1 || manifest.command!=='migrate' || !samePath(manifest.agentDir || '',loc.agentDir) || !samePath(manifest.state || '',loc.state) || !Array.isArray(manifest.files)) throw new Error('Unowned or incompatible migration snapshot');
  const allowed=new Set([loc.runtime,loc.mcp,loc.config,...fs.readdirSync(path.join(root,'agents')).filter(name=>name.endsWith('.md')).map(name=>path.join(loc.agentDir,'agents',name)),path.join(loc.agentDir,'skills','crew-omp','SKILL.md')]);
  const restore=manifest.files.map(entry=>{
    if(typeof entry.file!=='string' || ![...allowed].some(file=>samePath(file,entry.file))) throw new Error('Snapshot target outside owned migration files');
    if(![entry.hash,entry.expected].every(value=>value===null || typeof value==='string' && /^[a-f0-9]{64}$/.test(value))) throw new Error('Invalid snapshot hashes');
    let bytes=null;
    if(entry.hash!==null) {
      if(typeof entry.backup!=='string' || !/^\d+$/.test(entry.backup)) throw new Error('Invalid snapshot backup path');
      bytes=fs.readFileSync(path.join(backup,entry.backup));
      if(hash(bytes)!==entry.hash) throw new Error('Snapshot backup hash mismatch');
    }
    const actual=fs.existsSync(entry.file)?hash(fs.readFileSync(entry.file)):null;
    if(actual!==entry.hash && actual!==entry.expected) throw new Error(`Modified file preserved; rollback refused: ${entry.file}`);
    return {file:entry.file,bytes};
  });
  if(options.dryRun) return {ok:true,status:'dry_run',command,backup,restore:restore.map(entry=>entry.file),preservedState:loc.state};
  const linked=registered(loc);
  transact(restore.map(entry=>entry.file),()=>{
    for(const {file,bytes} of restore) {if(bytes===null)fs.rmSync(file,{force:true});else write(file,bytes);}
    if(linked) unlinkPlugin(loc);
  },loc.state);
  manifest.status='rolled_back';json(path.join(backup,'manifest.json'),manifest);
  return {ok:true,status:'rolled_back',command,backup,preservedState:loc.state};
}
function mcpProbe(python,loc) {
  const script = String.raw`
import asyncio,sys,os
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
 params=StdioServerParameters(command=sys.argv[1],args=[sys.argv[2]],env=dict(os.environ))
 async with stdio_client(params) as (reader,writer):
  async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=20)) as session:
   await session.initialize()
   tools=await session.list_tools()
   names={t.name for t in tools.tools}
   assert {'crew_catalog','crew_plan','crew_results','crew_escalate'}<=names
   plan=next(t for t in tools.tools if t.name=='crew_plan')
   assert {'spec','answers','project','session'}<=set(plan.inputSchema['properties'])
   result=await session.call_tool('crew_catalog',{})
   assert not result.isError
asyncio.run(main())
`;
  const result=run(python,['-c',script,process.execPath,path.join(root,'bin','mcp-launcher.mjs')],{...process.env,CREWS_OMP_HOME:loc.state,CREWS_OMP_AGENT_DIR:loc.agentDir,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'},true);
  return result.status === 0;
}
function main() {
  const loc = locations();
  if(command === 'rollback') return rollback(loc);
  const saved = readJSON(loc.runtime);
  if (command === 'doctor') {
    const problems = [];
    const python = saved.python;
    if (!python || !dependencies(python)) problems.push('Isolated Python runtime missing or dependency pins invalid');
    let plugin = false;
    try { plugin = registered(loc); } catch { problems.push('Native plugin inventory unavailable'); }
    if (!plugin) problems.push('Native plugin not linked to this package root; run omp plugin link <package-root> --scope user');
    const entry = readJSON(loc.mcp).mcpServers?.['crews-omp'];
    if (!ownedMcp(entry) || !isDeepStrictEqual(entry,registration(loc))) problems.push('Owned MCP registration missing or stale; run setup');
    let aliases = {};
    if (python && dependencies(python)) {
      if(!mcpProbe(python,loc)) problems.push('MCP stdio initialize/schema/catalog handshake failed');
      aliases = JSON.parse(yaml(python,path.join(loc.agentDir,'models.yml'),'models',{state:loc.state,packageRoot:root}));
      for(const [name,result] of Object.entries(aliases)) if(!result.present || result.missingEfforts.length) problems.push(`Unsupported alias ${name}: ${!result.present?'missing':`missing efforts ${result.missingEfforts.join(',')}`}`);
      const plan = legacyPlan(loc,python);
      if(plan.extensions.length || plan.files.length) problems.push('Legacy registration or duplicate discovery files remain; run migrate');
    }
    return {ok:problems.length===0,status:problems.length?'not_ready':'ready',command,packageRoot:root,state:loc.state,agentDir:loc.agentDir,aliases,problems};
  }
  if (command === 'uninstall') {
    const mcp = readJSON(loc.mcp);
    const entry = mcp.mcpServers?.['crews-omp'];
    if(entry && !ownedMcp(entry)) throw new Error('Unowned crews-omp MCP registration; uninstall refused');
    const linked = registered(loc);
    if(options.dryRun) return {ok:true,status:'dry_run',command,removeMcp:!!entry,unlinkPlugin:linked,preservedState:loc.state};
    const backup=transact([loc.mcp],()=>{
      if(entry) {delete mcp.mcpServers['crews-omp'];json(loc.mcp,mcp);}
      if(linked) unlinkPlugin(loc);
    },loc.state,{command,agentDir:loc.agentDir,state:loc.state});
    return {ok:true,status:'uninstalled',command,backup,preservedState:loc.state};
  }
  // A dry migration must never provision, link, write, or replay runtime state.
  const python = options.dryRun ? saved.python || discoverPython().exe : provision(loc);
  if(!python || !dependencies(python)) throw new Error('Provision runtime with setup before migration dry-run');
  const plan = legacyPlan(loc,python);
  if(command === 'setup' && (plan.extensions.length || plan.files.length || plan.legacyMcp)) throw new Error('Legacy Crews installation detected; use migrate (or migrate --dry-run)');
  const linked = registered(loc,options.registerPlugin && !options.dryRun);
  if(command === 'migrate' && !linked) throw new Error('Migration requires native plugin linked to exact package root; run omp plugin link <package-root> --scope user first');
  if(options.dryRun) return {ok:true,status:'dry_run',command,packageRoot:root,state:loc.state,remove:plan};
  const mcp = readJSON(loc.mcp);
  mcp.mcpServers ??= {};
  mcp.mcpServers['crews-omp'] = registration(loc);
  const runtime = {schemaVersion:1,owner,python,state:loc.state,agentDir:loc.agentDir,packageRoot:root};
  const unchanged = isDeepStrictEqual(saved,runtime) && fs.existsSync(loc.mcp) && isDeepStrictEqual(readJSON(loc.mcp),mcp);
  if(command === 'setup' && unchanged) return {ok:true,status:'unchanged',command,packageRoot:root,state:loc.state,agentDir:loc.agentDir,python,pluginLinked:linked};
  const targets = [loc.runtime,loc.mcp,...(command==='migrate'?[loc.config,...plan.files.map(f=>f.path)]:[])];
  const renderedConfig=command==='migrate' && plan.extensions.length ? yaml(python,loc.config,'remove',plan.extensions) : null;
  const expected=Object.fromEntries(targets.map(file=>[file,fs.existsSync(file)?hash(fs.readFileSync(file)):null]));
  expected[loc.runtime]=hash(`${JSON.stringify(runtime,null,2)}\n`);
  expected[loc.mcp]=hash(`${JSON.stringify(mcp,null,2)}\n`);
  if(renderedConfig!==null) expected[loc.config]=hash(renderedConfig);
  for(const file of plan.files) expected[file.path]=null;
  const backup = transact(targets,()=>{
    json(loc.runtime,runtime);
    json(loc.mcp,mcp);
    if(command === 'migrate') {
      // New native plugin and owner-marked MCP registration exist before removing old discovery.
      if(!registered(loc)) throw new Error('Native plugin disappeared before migration commit');
      if(renderedConfig!==null) write(loc.config,renderedConfig);
      for(const file of plan.files) {
        if(hash(fs.readFileSync(file.path))!==file.hash) throw new Error(`File changed during migration: ${file.path}`);
        fs.unlinkSync(file.path);
      }
    }
  },loc.state,{command,agentDir:loc.agentDir,state:loc.state,expected});
  return {ok:true,status:command==='migrate'?'migrated':'configured',command,packageRoot:root,state:loc.state,agentDir:loc.agentDir,python,pluginLinked:linked,backup,note:linked?'Restart OMP to load package agents and skills':'Link package with omp plugin link <package-root> --scope user, then restart OMP'};
}

if(process.argv[1] && samePath(fileURLToPath(import.meta.url),process.argv[1])) cli();
