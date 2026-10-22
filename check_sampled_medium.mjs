import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {classifyAdaptive} from './adaptive-classifier.mjs';
import {DEFAULT_CLASSIFIER} from './classifier.mjs';
import {sessionRoutingReport} from './routing-evidence.mjs';
const project=fs.mkdtempSync(path.join(os.tmpdir(),'crews-sampling-'));
try{
 const role={kind:'produce',mission:'implement local change',scope:[],answers:{need:'everyday_implementation',difficulty:1,divisible:0,specific:1}};
 const declared={tier:'medium',outcome:'declared',answers:role.answers,policy_version:'v1'};
 const config={...DEFAULT_CLASSIFIER,mediumShadowPercent:100,mediumShadowMax:1};let calls=0;const stored=[];
 const options={role,project,session:'s',declared,config,classifier:{recommend:async(_r,_p,_s,_v,c)=>{calls++;assert.equal(c.mode,'shadow');return {outcome:'shadow',recommendation:{need:'repeatable_task',difficulty:0},cacheHit:false};}},learning:p=>{stored.push(p);return {observation_id:'o'};},revalidate:()=>{throw Error('shadow cannot reclassify');}};
 const sampled=await classifyAdaptive(options);assert.equal(sampled.shadow_sampled,true);assert.equal(sampled.answers.need,'everyday_implementation');assert.equal(sampled.answers.difficulty,1);assert.equal(stored.at(-1).metrics.shadow_sampled,true);
 await classifyAdaptive(options);assert.equal(calls,1);
 await classifyAdaptive({...options,session:'preview',preview:true});assert.equal(calls,1);
 await classifyAdaptive({...options,session:'off',config:{...config,mode:'off'}});assert.equal(calls,1);
 const report=sessionRoutingReport([{type:'custom',customType:'crews-routing',data:{project,path:'main',model:'sol'}},{type:'custom',customType:'crews-routing',data:{project,path:'crew',model:'small'}},{type:'custom',customType:'crews-routing',data:{project:'other',path:'crew'}}],project);
 assert.deepEqual(report.paths,{main:1,crew:1});assert.equal(report.model_events.sol,1);
 console.log('PASS: sampled Medium teacher disagreement never changes routing, preview/off/dedup bounds, session path projection');
}finally{fs.rmSync(project,{recursive:true,force:true});}
