import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {callBridge} from './bridge-client.mjs';
import {resolveRuntime} from './runtime-paths.mjs';
import {classifyAdaptive} from './adaptive-classifier.mjs';
import {CLASSIFIER_PROMPT,DEFAULT_CLASSIFIER} from './classifier.mjs';
import {fileURLToPath} from 'node:url';
const base=path.dirname(fileURLToPath(import.meta.url));const runtime=resolveRuntime(base);
const state=fs.mkdtempSync(path.join(os.tmpdir(),'crews-adaptive-'));
const settings={...runtime,state};const project=state;
const bridge=input=>callBridge(settings,base,input);
const learning=args=>bridge({op:'learning',args,project});
const role={kind:'produce',mission:'Select routine implementation for this exact fixture',solution_space:'Known API but choice remains unspecified',classification:true,scope:['fixture.txt'],commands:[],acceptance:['fixture has selected value'],answers:{divisible:0,specific:1},facts:{unknown_cause:false,consequential_judgment:false,behavior_undecided:false}};
let teacherCalls=0;let proposal={need:'everyday_implementation',difficulty:1};
const classifier={recommend:async(_r,_p,_s,_v,_c,_a,_ctx,fresh)=>{teacherCalls++;return {outcome:'recommended',cacheHit:false,recommendation:{...proposal,reason:'scripted independent teacher'},usage:{input:10,output:5},latencyMs:1,fresh};}};
const config={...DEFAULT_CLASSIFIER,mode:'recommend'};
const revalidate=value=>bridge({op:'classify',role:value,project});
async function execute(){const declared=revalidate(role);assert.equal(declared.answers,null);return classifyAdaptive({role,project,session:'acceptance',declared,config:{...config,model:declared.classifier_model},classifier,learning,revalidate});}
try{
 let rule;
 for(let i=0;i<5;i++){
  const result=await execute();assert.equal(result.answers.need,'everyday_implementation');assert.equal(result.semantic.recommendation.reason,'scripted independent teacher');
  const label=learning({operation:'label',observation_id:result.learning.observation_id,...proposal,evidence:'Independent fixture reviewer verified required capability',split:i<3?'train':'holdout',unit_id:'independent-unit-'+i});
  if(label.rule_id)rule=label.rule_id;
 }
 assert.equal(teacherCalls,5);assert.ok(rule);
 assert.equal(learning({operation:'activate',rule_id:rule}).state,'active');learning({operation:'configure',mode:'on'});
 const learned=await execute();assert.equal(learned.outcome,'learned');assert.equal(teacherCalls,5);
 assert.throws(()=>learning({operation:'label',observation_id:learned.learning.observation_id,...proposal,evidence:'Cannot self-reinforce',split:'train',unit_id:'self-rule'}),/cannot label themselves/);
 // Ninth learned hit remains local; tenth bypasses cache and audits against teacher.
 for(let i=0;i<8;i++)assert.equal((await execute()).outcome,'learned');
 const audited=await execute();assert.equal(teacherCalls,6);assert.equal(audited.semantic.fresh,true);
 assert.equal(audited.answers.need,'everyday_implementation');
 for(let i=0;i<9;i++)await execute();proposal={need:'everyday_implementation',difficulty:1.5};
 await execute();assert.equal(teacherCalls,7);assert.equal(learning({operation:'rules'}).rules[0].state,'suspended');
 await execute();assert.equal(teacherCalls,8,'suspended rule must call teacher again');
 const report=learning({operation:'report'});assert.equal(report.teacher_calls_avoided,18);assert.equal(report.labels,5);
 assert.equal(learning({operation:'status'}).label_accuracy.scored,5);
 const raw=fs.readFileSync(path.join(state,'learning.sqlite'));assert.equal(raw.includes(Buffer.from(role.mission)),false);assert.equal(raw.includes(Buffer.from('Independent fixture reviewer')),false);
 learning({operation:'rollback',rule_id:rule});assert.equal(learning({operation:'rules'}).rules[0].state,'rolled_back');
 const fallback=await classifyAdaptive({role,project,session:'broken-store',declared:revalidate(role),config,classifier,learning:()=>{throw Error('broken DB');},revalidate});
 assert.equal(fallback.answers.need,'everyday_implementation');assert.equal(fallback.learning.unavailable,true);
 const declared=revalidate({...role,answers:{...role.answers,need:'everyday_implementation',difficulty:1}});
 const shadow=await classifyAdaptive({role,project,session:'shadow',declared,config:{...config,mode:'shadow'},classifier:{recommend:async()=>({outcome:'shadow',recommendation:{need:'mechanical_verification',difficulty:0}})},learning,revalidate});
 assert.equal(shadow.answers.need,'everyday_implementation');assert.equal(shadow.learning.unavailable,true);
 console.log('PASS: Large teacher -> 3 train/2 holdout -> explicit promotion -> 18 local decisions -> fresh audit/suspend/rollback; no raw task/evidence persisted');
}finally{fs.rmSync(state,{recursive:true,force:true});}
