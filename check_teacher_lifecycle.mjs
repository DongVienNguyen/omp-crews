import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolveRuntime} from './runtime-paths.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));const runtime=resolveRuntime(root);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'crews-test-teacher-'));const agentDir=path.join(temp,'.omp','agent');fs.mkdirSync(agentDir,{recursive:true});
const env={...process.env,HOME:temp,USERPROFILE:temp,CREWS_OMP_USER_HOME:temp,PI_CONFIG_DIR:'.omp',PI_CODING_AGENT_DIR:agentDir,CREWS_OMP_HOME:temp,CREWS_OMP_PYTHON:runtime.python,CREWS_OMP_AGENT_DIR:agentDir,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'};
const role={name:'teacher-fixture-reader',kind:'research',mission:'Read fixture.json and report exact value47',deliverable:'verdict.json',solution_space:'Read named fixture; need not declared',classification:true,scope:[],commands:[],inputs:['fixture.json'],acceptance:['Actual read value47'],facts:{unknown_cause:false,consequential_judgment:false,behavior_undecided:false},answers:{divisible:0,specific:1}};
const intake={intake:{spec:{task:'Read fixture source value',roles:[role]},answers:{need:{choice:'bounded_retrieval',confidence:1,probabilities:{bounded_retrieval:1}},difficulty:{score:1},divisible:{noul:0},needs_verifier:{noul:0}},session:'teacher-native-proof'}};
const requests=[];let server;
try{
 fs.writeFileSync(path.join(temp,'fixture.json'),'{"value":47}\n');
 server=http.createServer(async(req,res)=>{
  let raw='';for await(const b of req)raw+=b;const body=JSON.parse(raw);requests.push({model:body.model,effort:body.reasoning_effort,maxTokens:body.max_tokens??body.max_completion_tokens});
  const tools=body.messages.filter(m=>m.role==='tool');let content,call;
  if(body.model==='code-astra')content=JSON.stringify({need:'bounded_retrieval',difficulty:1,reason:'Known read-only fixture'});
  else if(body.model==='code-sol'){
   if(!tools.length)call={name:'task',args:intake};
   else if(tools.length===1){const all=JSON.stringify(tools).replaceAll('\\"','"');const run=all.match(/"run"\s*:\s*"([a-f0-9]{32})"/);assert.ok(run,all);call={name:'task',args:{crew:{run:run[1],role:role.name,session:'teacher-native-proof'}}};}
   else content='Teacher and native child complete';
  }else if(!tools.length)call={name:'read',args:{i:'Reading teacher fixture',path:path.join(temp,'fixture.json')}};
  else{assert.ok(JSON.stringify(tools).includes('47'));content=JSON.stringify({status:'COMPLETE',verification:['Observed fixture value47 through real read']});}
  const message=call?{role:'assistant',tool_calls:[{id:'call-'+requests.length,type:'function',function:{name:call.name,arguments:JSON.stringify(call.args)}}]}:{role:'assistant',content};
  const finish=call?'tool_calls':'stop';const base={id:'teacher-scripted',created:Math.floor(Date.now()/1000),model:body.model};
  if(!body.stream){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({...base,object:'chat.completion',choices:[{index:0,message,finish_reason:finish}],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15}}));return;}
  const delta=call?{...message,tool_calls:message.tool_calls.map((v,index)=>({...v,index}))}:message;
  res.writeHead(200,{'Content-Type':'text/event-stream'});res.end('data: '+JSON.stringify({...base,object:'chat.completion.chunk',choices:[{index:0,delta,finish_reason:null}]})+'\n\ndata: '+JSON.stringify({...base,object:'chat.completion.chunk',choices:[{index:0,delta:{},finish_reason:finish}],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15}})+'\n\ndata: [DONE]\n\n');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const models=['code-seek','code-sol','code-astra'].map(id=>({id,name:id,reasoning:true,input:['text'],contextWindow:100000,maxTokens:4096,thinking:{mode:'effort',efforts:['low','medium','high'],defaultLevel:'high',requiresEffort:true},compat:{supportsReasoningEffort:true,supportsReasoningParams:true,thinkingFormat:'openai'}}));fs.writeFileSync(path.join(agentDir,'models.yml'),JSON.stringify({providers:{'9router':{baseUrl:'http://127.0.0.1:'+server.address().port+'/v1',apiKey:'local-no-secret',api:'openai-completions',models}}}));
 const child=spawn(process.env.CREWS_OMP_OMP||'omp',['--cwd',temp,'--no-extensions','-e',root,'--model','9router/code-sol:high','--mode','json','--no-session','--max-time','120','-p','Run canonical teacher fixture.'],{env,cwd:temp,shell:false,windowsHide:true,stdio:['ignore','pipe','pipe']});let out='',err='';child.stdout.on('data',b=>out+=b);child.stderr.on('data',b=>err+=b);const exit=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('exit',resolve);});assert.equal(exit,0,err+'\n'+out.slice(-6000));
 const script=`import sys,sqlite3,json\nsys.path.insert(0,sys.argv[1])\nfrom crews import omp_adapter as a\nfrom crews.learning import dispatch\ndb=sqlite3.connect(sys.argv[2]+'/runs.sqlite');run=db.execute('SELECT id FROM runs').fetchone()[0];r=a.results(run,sys.argv[2],'teacher-native-proof')[0];assert r['status']=='completed',r\nassert r['result']['wire']['model']=='code-seek' and r['result']['wire']['effort']=='medium',r\nreport=dispatch({'operation':'report'},sys.argv[2]);assert report['teacher_calls_observed']==1,report;assert report['labels']==0,report;print(json.dumps(report))`;
 const result=spawnSync(runtime.python,['-c',script,root,temp],{env,encoding:'utf8'});assert.equal(result.status,0,result.stderr+'\n'+out.slice(-8000));
 assert.equal(requests.filter(r=>r.model==='code-astra').length,1);assert.equal(requests.find(r=>r.model==='code-astra').effort,'high');assert.deepEqual(requests.filter(r=>r.model==='code-seek').map(r=>r.effort),['medium','medium']);
 console.log('PASS: actual OMP Large/high teacher -> bounded Small/medium native role -> completed receipt; observation stored, zero automatic labels');
}finally{if(server)await new Promise(resolve=>server.close(resolve));fs.rmSync(temp,{recursive:true,force:true});}
