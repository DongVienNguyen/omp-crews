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

// Workflow reads stay inside both lexical grants and their resolved targets.
export function admittedRead(cwd, input, name, scope) {
 try {
  const root=fs.realpathSync(cwd);
  const inside=(base,target)=>{const rel=path.relative(base,target);return rel!=='..'&&!rel.startsWith('..'+path.sep)&&!path.isAbsolute(rel);};
  const local=value=>{
   if(typeof value!=='string'||!value||value.includes('\0')||/^[a-z][a-z0-9+.-]*:/i.test(value)&&!path.isAbsolute(value))throw Error('Nonlocal path');
   const target=path.resolve(root,value);
   if(!inside(root,target))throw Error('Path escapes project');
   return target;
  };
  const grants=(scope??[]).flatMap(value=>{const target=local(value);if(!fs.existsSync(target))return [];const real=fs.realpathSync(target);if(!inside(root,real))throw Error('Grant escapes project');return [{target,real,dir:fs.statSync(real).isDirectory()}];});
  const allowed=target=>{
   const real=fs.realpathSync(target);
   return inside(root,real)&&grants.some(g=>g.dir?inside(g.target,target)&&inside(g.real,real):g.target===target&&g.real===real);
  };
  const safeTree=(target,seen=new Set())=>{
   if(!allowed(target))return false;
   const real=fs.realpathSync(target);
   if(!fs.statSync(real).isDirectory()||seen.has(real))return true;
   seen.add(real);
   return fs.readdirSync(target).every(entry=>safeTree(path.join(target,entry),seen));
  };
  let values;
  if(name==='read')values=[input.path??input.file_path];
  else if(name==='grep'||name==='glob')values=(input.path??'.').split(';');
  else return false;
  return values.length>0&&values.every(value=>{
   if(typeof value!=='string')return false;
   if(name!=='read'&&value.startsWith('!'))value=value.slice(1);
   if(/^[a-z][a-z0-9+.-]*:\/\//i.test(value))return false;
   if(name==='read')value=value.replace(/:(?:(?:raw|img|conflicts)|(?:\d[^:\/?]*|-[0-9]+))(?::(?:raw|img|conflicts|\d[^:\/?]*|-[0-9]+))*$/,'').split('?')[0];
   if(value.replaceAll('\\','/').split('/').includes('..')||/^[a-z][a-z0-9+.-]*:\/\//i.test(value))return false;
   if(name!=='read'&&value.replace(/^[a-z]:[\\/]/i,'').includes(':'))return false;
   if(name!=='read'){
    // Bare patterns recurse from cwd; scoped patterns must name a granted root.
    const wildcard=value.search(/[*?\[\]{}]/);
    if(wildcard!==-1){const prefix=value.slice(0,wildcard);const slash=Math.max(prefix.lastIndexOf('/'),prefix.lastIndexOf('\\'));value=slash<0?'.':prefix.slice(0,slash+1);}
   }
   return safeTree(local(value));
  });
 } catch { return false; }
}
