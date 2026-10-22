import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolveRuntime} from './runtime-paths.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const runtime=resolveRuntime(root);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-test-native-'));
const agentDir=path.join(temp,'.omp','agent');
fs.mkdirSync(agentDir,{recursive:true});
const env={...process.env,HOME:temp,USERPROFILE:temp,CREWS_OMP_USER_HOME:temp,PI_CONFIG_DIR:'.omp',PI_CODING_AGENT_DIR:agentDir,CREWS_OMP_HOME:temp,CREWS_OMP_PYTHON:runtime.python,CREWS_OMP_AGENT_DIR:agentDir,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'};
const requests=[];
let server;
try{
 fs.writeFileSync(path.join(temp,'fixture.json'),'{"value":47}\n');
 const script=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom omp_server import crew_plan\nrole={'name':'local-fixture-checker','kind':'check','mission':'Read fixture JSON and verify value 47','deliverable':'verdict.json','scope':[],'inputs':['fixture.json'],'criteria':['value equals 47'],'answers':{'need':'mechanical_verification','difficulty':0,'divisible':0,'specific':1}}\na={'need':{'choice':'mechanical_verification','confidence':1,'probabilities':{'mechanical_verification':1}},'difficulty':{'score':0},'divisible':{'noul':0},'needs_verifier':{'noul':1}}\np=crew_plan({'task':'Read fixture and verify value','roles':[role]},a,sys.argv[2],'local-scripted-proof');print(json.dumps({'run':p['run_id'],'role':role['name'],'session':p['session']}))`;
 const plan=spawnSync(runtime.python,['-c',script,root,temp],{env,encoding:'utf8',shell:false});
 assert.equal(plan.status,0,plan.stderr);const ref=JSON.parse(plan.stdout);
 server=http.createServer(async(req,res)=>{
  if(!req.url.endsWith('/chat/completions')){res.writeHead(404);res.end();return;}
  let text='';for await(const chunk of req)text+=chunk;
  const body=JSON.parse(text);requests.push({model:body.model,effort:body.reasoning_effort});
  const messages=body.messages??[];const hasTool=messages.some(m=>m.role==='tool');let delta,finish;
  if(body.model==='code-sol'){
   delta=hasTool?{role:'assistant',content:'Local lifecycle complete'}:{role:'assistant',tool_calls:[{index:0,id:'local_task',type:'function',function:{name:'task',arguments:JSON.stringify({crew:ref})}}]};
   finish=hasTool?'stop':'tool_calls';
  }else{
   const observed=messages.filter(m=>m.role==='tool').map(m=>JSON.stringify(m.content)).join('');
   delta=hasTool?{role:'assistant',content:JSON.stringify({status:observed.includes('47')?'COMPLETE':'FAILED',verification:['Observed actual read result with fixture value=47']})}:{role:'assistant',tool_calls:[{index:0,id:'local_read',type:'function',function:{name:'read',arguments:JSON.stringify({i:'Reading local fixture',path:path.join(temp,'fixture.json')})}}]};
   finish=hasTool?'stop':'tool_calls';
  }
  const base={id:'local-scripted',object:'chat.completion.chunk',created:Math.floor(Date.now()/1000),model:body.model};
  res.writeHead(200,{'Content-Type':'text/event-stream'});
  res.end('data: '+JSON.stringify({...base,choices:[{index:0,delta,finish_reason:null}]})+'\n\ndata: '+JSON.stringify({...base,choices:[{index:0,delta:{},finish_reason:finish}],usage:{prompt_tokens:1,completion_tokens:1,total_tokens:2}})+'\n\ndata: [DONE]\n\n');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const models=['code-seek','code-sol','code-astra'].map(id=>({id,name:id,reasoning:true,input:['text'],contextWindow:100000,maxTokens:4096,thinking:{mode:'effort',efforts:['low','medium','high','xhigh'],defaultLevel:'high',requiresEffort:true},compat:{supportsReasoningEffort:true,supportsReasoningParams:true,thinkingFormat:'openai'}}));
 fs.writeFileSync(path.join(agentDir,'models.yml'),JSON.stringify({providers:{'9router':{baseUrl:'http://127.0.0.1:'+server.address().port+'/v1',apiKey:'local-scripted-no-secret',api:'openai-completions',models}}}));
 const child=spawn(process.env.CREWS_OMP_OMP||'omp',['--cwd',temp,'--no-extensions','-e',root,'-e',path.join(root,'tests/local-provider-probe.ts'),'--model','9router/code-sol:high','--mode','json','--no-session','--max-time','90','-p','Execute local lifecycle fixture.'],{cwd:temp,env:{...env,CREWS_LOCAL_PROVIDER_URL:'http://127.0.0.1:'+server.address().port+'/v1'},shell:false,windowsHide:true,stdio:['ignore','pipe','pipe']});
 let out='',err='';child.stdout.on('data',b=>out+=b);child.stderr.on('data',b=>err+=b);
 const exit=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('exit',resolve);});
 assert.equal(exit,0,err+'\n'+out.slice(-1500));
 const resultScript=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom crews import omp_adapter as a\nr=a.results(sys.argv[2],sys.argv[3],'local-scripted-proof')[0]\nassert r['status']=='completed',r\nassert r['result']['wire']['model']=='code-seek' and r['result']['wire']['effort']=='low',r\nprint('verified')`;
 const check=spawnSync(runtime.python,['-c',resultScript,root,ref.run,temp],{env,encoding:'utf8',shell:false});assert.equal(check.status,0,check.stderr+'\n'+out.split('\n').filter(l=>/tool_execution_end|error|extension/i.test(l)).join('\n').slice(-10000)+'\n'+err);
 assert.deepEqual(requests.map(r=>r.model),['code-sol','code-seek','code-seek','code-sol']);
 assert.deepEqual(requests.map(r=>r.effort),['high','low','low','high']);
 console.log('PASS: actual OMP agent loop, native task child, real read, strict result, matching wire receipt; local scripted provider only');
}finally{if(server)await new Promise(resolve=>server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
