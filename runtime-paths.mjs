import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export function resolveRuntime(base, env=process.env) {
 const home=env.CREWS_OMP_USER_HOME || os.homedir();
 const configRoot=env.PI_CONFIG_DIR ? path.resolve(home,env.PI_CONFIG_DIR) : path.join(home,'.omp');
 const profile=env.OMP_PROFILE || env.PI_PROFILE;
 const agentDir=path.resolve(env.CREWS_OMP_AGENT_DIR || (profile ? path.join(configRoot,'profiles',profile,'agent') : env.PI_CODING_AGENT_DIR || path.join(configRoot,'agent')));
 const state=path.resolve(env.CREWS_OMP_HOME || (profile ? path.join(configRoot,'profiles',profile,'crews-omp') : path.join(home,'.crews-omp')));
 const runtimeFile=path.join(state,'runtime.json');
 const runtime=fs.existsSync(runtimeFile)?JSON.parse(fs.readFileSync(runtimeFile,'utf8')):{};
 if(fs.existsSync(runtimeFile)&&(runtime.owner!=='crews-omp/package-v1'||runtime.schemaVersion!==1||typeof runtime.python!=='string'||!path.isAbsolute(runtime.python)||path.resolve(runtime.state)!==state||path.resolve(runtime.agentDir)!==agentDir))throw new Error('Crews runtime registration is invalid or belongs to another profile; run setup for this profile.');
 const python=env.CREWS_OMP_PYTHON || runtime.python;
 if(!python)throw new Error('Crews runtime is not provisioned. Run crews-omp setup --python <Python 3.12+ executable> for the active profile.');
 return {python,state,agentDir,config:path.join(agentDir,'config.yml'),packageRoot:path.resolve(base),schemaVersion:1};
}
