import assert from 'node:assert/strict';
import {effortOptions,policyForm,validatePolicyInput} from './policy-form.mjs';
const base={provider:'9router',models:{haiku:'code-seek',sonnet:'code-sol',opus:'code-astra'}};
assert.deepEqual(effortOptions('haiku'),['high']);assert.deepEqual(effortOptions('sonnet'),['low','medium','high','xhigh','max']);assert.deepEqual(effortOptions('opus'),['low','medium','high']);
assert.equal(policyForm(base).find(x=>x.id==='sonnet').model,'code-sol');assert.throws(()=>validatePolicyInput({...base,secret:'x'}));assert.throws(()=>validatePolicyInput({...base,models:{...base.models,haiku:'same',sonnet:'same'}}));assert.throws(()=>validatePolicyInput({...base,models:{...base.models,sonnet:'bad id!'}}));
console.log('PASS: model policy form fields, effort option bands, unknown/duplicate/invalid model rejection');
