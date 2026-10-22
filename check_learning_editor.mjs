import assert from 'node:assert/strict';
import {manageLearning} from './learning-editor.mjs';
let calls=[];const request=p=>{calls.push(p);return {ok:true};};
assert.equal((await manageLearning({select:async()=>undefined},request)).changed,false);assert.equal(calls.length,0);
let choices=['Mode','on'];assert.equal((await manageLearning({select:async()=>choices.shift(),confirm:async()=>false},request)).changed,false);assert.equal(calls.length,0);
choices=['Mode','on'];assert.equal((await manageLearning({select:async()=>choices.shift(),confirm:async()=>true,notify:()=>{}},request)).changed,true);assert.deepEqual(calls.pop(),{operation:'configure',mode:'on'});
choices=['Label observation','bounded_retrieval','1','holdout'];let inputs=['obs1','unit1','Independent verification'];await manageLearning({select:async()=>choices.shift(),input:async()=>inputs.shift(),confirm:async()=>true,notify:()=>{}},request);assert.deepEqual(calls.pop(),{operation:'label',observation_id:'obs1',need:'bounded_retrieval',difficulty:1,split:'holdout',unit_id:'unit1',evidence:'Independent verification'});
console.log('PASS: learning editor cancel/confirmation and explicit label payload');
