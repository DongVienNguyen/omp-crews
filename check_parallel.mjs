import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolveRuntime} from './runtime-paths.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),runtime=resolveRuntime(root);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-test-parallel-')),agentDir=path.join(temp,'.omp/agent');fs.mkdirSync(agentDir,{recursive:true});
const env={...process.env,HOME:temp,USERPROFILE:temp,CREWS_OMP_USER_HOME:temp,PI_CONFIG_DIR:'.omp',PI_CODING_AGENT_DIR:agentDir,CREWS_OMP_HOME:temp,CREWS_OMP_PYTHON:runtime.python,CREWS_OMP_AGENT_DIR:agentDir,PYTHONUTF8:'1'};
let server;let waiting=[];let overlapped=false;let deadline;
try{
 fs.writeFileSync(path.join(temp,'left.json'),'{"side":"left"}');fs.writeFileSync(path.join(temp,'right.json'),'{"side":"right"}');
 const script=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom crews import omp_adapter as a\nroles=[dict(name=side+'-reader',kind='research',mission='Read '+side+' fixture JSON',deliverable='facts',scope=[],inputs=[side+'.json'],commands=[],acceptance=['Report '+side+' value'],answers=dict(need='bounded_retrieval',difficulty=1,divisible=0,specific=1)) for side in ['left','right']]\nanswers=dict(need=dict(choice='bounded_retrieval',confidence=1),difficulty=dict(score=1),divisible=dict(noul=1),needs_verifier=dict(noul=0))\np=a.build_plan(dict(task='Read fixture JSON',roles=roles),answers,sys.argv[2],'parallel-proof')\nprint(json.dumps([dict(run=p['run_id'],role=r['name'],session=p['session']) for r in roles]))`;
 const p=spawnSync(runtime.python,['-B','-c',script,root,temp],{env,encoding:'utf8'});assert.equal(p.status,0,p.stderr);const refs=JSON.parse(p.stdout);
 function send(res,body,delta,finish){const base={id:'parallel-fixture',object:'chat.completion.chunk',created:Math.floor(Date.now()/1000),model:body.model};res.writeHead(200,{'Content-Type':'text/event-stream'});res.end('data: '+JSON.stringify({...base,choices:[{index:0,delta,finish_reason:null}]})+'\n\ndata: '+JSON.stringify({...base,choices:[{index:0,delta:{},finish_reason:finish}],usage:{prompt_tokens:1,completion_tokens:1,total_tokens:2}})+'\n\ndata: [DONE]\n\n');}
 server=http.createServer(async(req,res)=>{
  let text='';for await(const b of req)text+=b;const body=JSON.parse(text);const hasTool=body.messages?.some(m=>m.role==='tool');
  if(body.model==='code-sol'){
   send(res,body,hasTool?{role:'assistant',content:'Parallel fixture complete'}:{role:'assistant',tool_calls:refs.map((crew,index)=>({index,id:'dispatch_'+index,type:'function',function:{name:'task',arguments:JSON.stringify({crew})}}))},hasTool?'stop':'tool_calls');return;
  }
  const input=JSON.stringify(body.messages);const side=input.includes('left-reader')?'left':'right';
  const respond=()=>send(res,body,hasTool?{role:'assistant',content:JSON.stringify({status:'COMPLETE',verification:['Observed '+side+' fixture']})}:{role:'assistant',tool_calls:[{index:0,id:'read_'+side,type:'function',function:{name:'read',arguments:JSON.stringify({i:'Reading independent fixture',path:path.join(temp,side+'.json')})}}]},hasTool?'stop':'tool_calls');
  if(hasTool){respond();return;}
  waiting.push(respond);
  if(waiting.length===2){overlapped=true;clearTimeout(deadline);for(const reply of waiting)reply();waiting=[];}
  else deadline=setTimeout(()=>{for(const reply of waiting)reply();waiting=[];},20000);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const models=['code-seek','code-sol','code-astra'].map(id=>({id,name:id,reasoning:true,input:['text'],contextWindow:100000,maxTokens:4096,thinking:{mode:'effort',efforts:['low','medium','high'],defaultLevel:'high',requiresEffort:true},compat:{supportsReasoningEffort:true,supportsReasoningParams:true,thinkingFormat:'openai'}}));
 fs.writeFileSync(path.join(agentDir,'models.yml'),JSON.stringify({providers:{'9router':{baseUrl:'http://127.0.0.1:'+server.address().port+'/v1',apiKey:'local-fixture-only',api:'openai-completions',models}}}));
 const child=spawn('omp',['--cwd',temp,'--no-extensions','-e',root,'-e',path.join(root,'tests/local-provider-probe.ts'),'--model','9router/code-sol:high','--mode','json','--no-session','--max-time','90','-p','Execute parallel native fixture.'],{cwd:temp,env:{...env,CREWS_LOCAL_PROVIDER_URL:'http://127.0.0.1:'+server.address().port+'/v1'},stdio:['ignore','pipe','pipe']});
 let out='',err='';child.stdout.on('data',b=>out+=b);child.stderr.on('data',b=>err+=b);const exit=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('exit',resolve);});assert.equal(exit,0,err+out.slice(-3000));assert.ok(overlapped,'native children did not overlap\n'+out.slice(-6000));
 const proof=`import sys,json\nsys.path.insert(0,sys.argv[1])\nfrom crews import omp_adapter as a\nrows=a.results(sys.argv[2],sys.argv[3],'parallel-proof')\nassert len(rows)==2 and all(r['status']=='completed' and r['result']['host_authenticated'] and r['result']['wire']['role']==r['role_id'] for r in rows),rows\nassert len({r['result']['wire']['token'] for r in rows})==2\nfor r in rows:assert list(r['result']['fingerprints'])==[r['role_id'].split('-')[0]+'.json']\nprint('verified')`;
 const verified=spawnSync(runtime.python,['-B','-c',proof,root,refs[0].run,temp],{env,encoding:'utf8'});assert.equal(verified.status,0,verified.stderr+'\n'+out.slice(-6000));
 console.log('PASS actual two overlapping native Small children, isolated wire tokens/roles/artifact fingerprints; scripted provider only');
}finally{clearTimeout(deadline);if(server)await new Promise(resolve=>server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
