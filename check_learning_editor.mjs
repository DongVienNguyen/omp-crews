import assert from 'node:assert/strict';
import {manageLearning} from './learning-editor.mjs';

const secret='raw-secret-must-not-appear';
const candidate={run:'run1',role:'writer',session:'session1',observation_id:'obs1',declared_need:'everyday_implementation',declared_difficulty:2,prompt:secret};
const selected=JSON.stringify({run:candidate.run,role:candidate.role,session:candidate.session});
async function exercise({choices=[],inputs=[],confirm=true,candidates=[candidate]}={}){
 const calls=[],display=[];
 const ui={
  select:async(title,options)=>{display.push([title,options]);return choices.shift();},
  input:async title=>{display.push(title);return inputs.shift();},
  confirm:async(title,body)=>{display.push([title,body]);return confirm;},
  notify:(...args)=>display.push(args),
 };
 const result=await manageLearning(ui,async args=>{
  calls.push(args);
  return args.operation==='feedback_options'?{feedback_options:candidates}:{ok:true,raw:secret};
 });
 return {calls,display,result};
}
let check=await exercise();
assert.equal(check.result.changed,false);assert.deepEqual(check.calls,[]);
check=await exercise({choices:['Mode','on'],confirm:false});
assert.equal(check.result.changed,false);assert.deepEqual(check.calls,[]);
check=await exercise({choices:['Mode','on']});
assert.equal(check.result.changed,true);assert.deepEqual(check.calls,[{operation:'configure',mode:'on'}]);
check=await exercise({choices:['Label observation','bounded_retrieval','1','holdout'],inputs:['obs1','unit1','Independent verification']});
assert.deepEqual(check.calls,[{operation:'label',observation_id:'obs1',need:'bounded_retrieval',difficulty:1,split:'holdout',unit_id:'unit1',evidence:'Independent verification'}]);
for(const action of ['Activate rule','Rollback rule']){
 check=await exercise({choices:[action],inputs:['rule1']});
 assert.deepEqual(check.calls,[{operation:action==='Activate rule'?'activate':'rollback',rule_id:'rule1'}]);
}
const readOnly=[{operation:'feedback_options'}];
check=await exercise({choices:['Verified Small result'],candidates:[]});
assert.equal(check.result.changed,false);assert.deepEqual(check.calls,readOnly);
assert.match(JSON.stringify(check.display),/No eligible Small results/);
for(const selection of [undefined,'run1',JSON.stringify({run:'run1',role:'other',session:'session1'}),JSON.stringify({run:'run1',role:'writer',session:'other'})]){
 check=await exercise({choices:['Verified Small result',selection]});
 assert.equal(check.result.changed,false);assert.deepEqual(check.calls,readOnly);
}
// Every input-stage cancellation must leave receipts unlabelled.
const fullChoices=['Verified Small result',selected,'everyday_implementation','1.5','holdout'];
for(let count=2;count<fullChoices.length;count++){
 check=await exercise({choices:fullChoices.slice(0,count)});
 assert.equal(check.result.changed,false);assert.deepEqual(check.calls,readOnly);
}
for(const inputs of [[],['check1']]){
 check=await exercise({choices:[...fullChoices],inputs});
 assert.equal(check.result.changed,false);assert.deepEqual(check.calls,readOnly);
}
check=await exercise({choices:[...fullChoices],inputs:['check1',secret],confirm:false});
assert.equal(check.result.changed,false);assert.deepEqual(check.calls,readOnly);
assert.ok(!JSON.stringify(check.display).includes(secret));
check=await exercise({choices:[...fullChoices],inputs:['check1',secret]});
assert.equal(check.result.changed,true);
assert.deepEqual(check.calls,[...readOnly,{operation:'feedback',run:'run1',role:'writer',session:'session1',verified_small:true,need:'everyday_implementation',difficulty:1.5,split:'holdout',unit_id:'check1',evidence:secret}]);
assert.ok(!JSON.stringify(check.display).includes(secret));
assert.match(JSON.stringify(check.display),/COMPLETE alone is not verification/);
assert.equal(check.display.filter(item=>Array.isArray(item)&&item[0]==='Apply learning change?').length,1);
// Backend remains authority: rejected receipt must not produce success notification.
const notifications=[],rejectedInputs=['unit','evidence'];
await assert.rejects(manageLearning({select:async()=>fullChoices.shift(),input:async()=>rejectedInputs.shift(),confirm:async()=>true,notify:(...args)=>notifications.push(args)},args=>{
 if(args.operation==='feedback_options')return {feedback_options:[candidate]};
 throw new Error('stale receipt');
}),/stale receipt/);
assert.deepEqual(notifications,[]);
console.log('PASS: learning editor cancel, eligible selection, exact confirmed feedback, receipt rejection, privacy, and existing controls');
