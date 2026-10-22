import assert from 'node:assert/strict';
import {createShadowSampler} from './shadow-sampling.mjs';
const sampler=createShadowSampler();const config={mode:'recommend',mediumShadowPercent:100,mediumShadowMax:1};
const role={kind:'produce',mission:'known local fix'};const declared={tier:'medium',answers:{need:'everyday_implementation',difficulty:1},policy_version:'v1'};
assert.equal(sampler.select(role,declared,'p','s',config,'f'),true);assert.equal(sampler.select(role,declared,'p','s',config,'f'),false);assert.equal(sampler.select({...role,mission:'other'},declared,'p','s',config,'g'),false);
assert.equal(sampler.select(role,declared,'p','s2',{...config,mode:'off'},'f'),false);assert.equal(sampler.select(role,declared,'p','s2',{...config,mediumShadowPercent:0},'f'),false);
assert.equal(sampler.select(role,{...declared,answers:{...declared.answers,difficulty:2}},'p','s2',config,'f'),false);assert.equal(sampler.select({...role,kind:'check'},declared,'p','s2',config,'f'),false);assert.equal(sampler.select(role,{...declared,tier:'large'},'p','s2',config,'f'),false);
assert.equal(sampler.select(role,declared,'other','s',config,'f'),true);
console.log('PASS: declared Medium shadow sampling bounded per session/project, no duplicate/off/high-risk preview selection');
