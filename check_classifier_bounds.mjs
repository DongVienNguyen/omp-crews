import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {Classifier,DEFAULT_CLASSIFIER,contextFingerprint,parseRecommendation,loadClassifierConfig} from './classifier.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'crews-bounds-'));
try {
 const role={kind:'research',mission:'Read named file',answers:{divisible:0,specific:1}};
 const off=new Classifier(()=>{throw Error('must not call');});
 assert.equal((await off.recommend(role,root,'s','p',{...DEFAULT_CLASSIFIER,mode:'off'})).outcome,'off');
 assert.equal(fs.existsSync(path.join(root,'classifier.json')),false);assert.equal(off.cache.size,0);
 assert.deepEqual(loadClassifierConfig(root),DEFAULT_CLASSIFIER);
 for(const extra of ['model','kind','scope','commands','authority','tier'])assert.throws(()=>parseRecommendation(JSON.stringify({need:'bounded_retrieval',difficulty:1,reason:'x',[extra]:'evil'})));
 assert.throws(()=>contextFingerprint(root,{inputs:['../secret']}));
 assert.throws(()=>contextFingerprint(root,{inputs:[path.resolve(root,'absolute')]}));
 assert.throws(()=>contextFingerprint(root,{inputs:Array.from({length:129},(_,i)=>'p'+i)}));
 let count=0;
 const cache=new Classifier(async()=>{count++;return {text:'{"need":"bounded_retrieval","difficulty":1,"reason":"read"}',stopReason:'stop'};});
 const cfg={...DEFAULT_CLASSIFIER,mode:'shadow'};
 const first=await cache.recommend(role,root,'s','p',cfg);assert.equal(first.outcome,'shadow');
 for(let i=0;i<256;i++)await cache.recommend({...role,mission:'read '+i},root,'s','p',cfg);
 assert.equal(cache.cache.size,256);await cache.recommend(role,root,'s','p',cfg);assert.equal(count,258);
 await cache.recommend(role,root,'other-session','p',cfg);assert.equal(count,259);
 await assert.rejects(()=>cache.recommend({...role,mission:'x'.repeat(16001)},root,'s','p',cfg),/16000/);
 console.log('PASS: off/no-write, hostile outputs, artifact/brief bounds, cache eviction/session and shadow behavior');
}finally{fs.rmSync(root,{recursive:true,force:true});}
