import path from 'node:path';
import {execFileSync} from 'node:child_process';

export function callBridge(settings, base, input) {
 let out;
 try {
  out=execFileSync(settings.python,[path.join(base,'omp_bridge.py')],{input:JSON.stringify(input),encoding:'utf8',windowsHide:true,timeout:30000,env:{...process.env,CREWS_OMP_HOME:settings.state}});
 } catch (error) {
  let failure;
  try { failure=JSON.parse(String(error.stdout??'')); } catch {}
  if(typeof failure?.error==='string')throw new Error(`Crews bridge ${input.op}: ${failure.error}`,{cause:error});
  throw error;
 }
 const data=JSON.parse(out);
 if(data.error)throw new Error(`Crews bridge ${input.op}: ${data.error}`);
 return data;
}
