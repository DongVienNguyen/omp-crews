import fs from 'node:fs';
import path from 'node:path';

export function admittedWrite(cwd, input, name, scope) {
 let targets;
 if(name==='write')targets=[input.path??input.file_path];
 else if(typeof input.input==='string'){
  targets=[...input.input.matchAll(/^\[([^\]\r\n]+)#[0-9a-fA-F]{4}\]\s*$/gm)].map(m=>m[1]);
  if(!targets.length||/^MV\s/m.test(input.input))return false;
 } else targets=[input.path??input.file_path];
 const root=fs.realpathSync(cwd);
 return targets.length>0&&targets.every(value=>{
  if(typeof value!=='string'||!value||/^[a-z]+:\/\//i.test(value))return false;
  const target=path.resolve(cwd,value);
  const rel=path.relative(root,target).replaceAll('\\','/');
  if(!scope.includes(rel))return false;
  let ancestor=target;while(!fs.existsSync(ancestor)){const parent=path.dirname(ancestor);if(parent===ancestor)return false;ancestor=parent;}
  const real=path.relative(root,fs.realpathSync(ancestor));
  return real!== '..'&&!real.startsWith('..'+path.sep)&&!path.isAbsolute(real);
 });
}
