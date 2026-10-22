import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {resolveRuntime} from './runtime-paths.mjs';
const home=fs.mkdtempSync(path.join(os.tmpdir(),'crews-runtime-'));
try{
 const env={CREWS_OMP_USER_HOME:home,CREWS_OMP_PYTHON:process.execPath};
 const expected=resolveRuntime(home,env);
 fs.mkdirSync(expected.state,{recursive:true});
 const file=path.join(expected.state,'runtime.json');
 fs.writeFileSync(file,JSON.stringify({schemaVersion:1,owner:'unknown',python:process.execPath,state:expected.state,agentDir:expected.agentDir}));
 assert.throws(()=>resolveRuntime(home,env),/invalid or belongs/);
 fs.writeFileSync(file,JSON.stringify({schemaVersion:1,owner:'crews-omp/package-v1',python:process.execPath,state:expected.state,agentDir:expected.agentDir}));
 assert.equal(resolveRuntime(home,env).python,process.execPath);
 assert.throws(()=>resolveRuntime(home,{...env,CREWS_OMP_AGENT_DIR:path.join(home,'other')}),/another profile/);
 const profile=resolveRuntime(home,{CREWS_OMP_USER_HOME:home,OMP_PROFILE:'test',CREWS_OMP_PYTHON:process.execPath});
 assert.equal(profile.agentDir,path.join(home,'.omp/profiles/test/agent'));
 console.log('PASS: runtime owner/schema and profile registration checks');
}finally{fs.rmSync(home,{recursive:true,force:true});}
