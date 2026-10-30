import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {admittedWrite,admittedRead} from './write-scope.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'crew-scope-'));
try{
 fs.writeFileSync(path.join(root,'a.txt'),'a');
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nPUT 1.=1:\n+b'},'edit',['a.txt']),true);
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nREM\n[outside.txt#1234]\nREM'},'edit',['a.txt']),false);
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nMV outside.txt'},'edit',['a.txt']),false);
 assert.equal(admittedWrite(root,{path:'xd://tool'},'write',['a.txt']),false);
 assert.equal(admittedWrite(root,{path:'../a.txt'},'write',['a.txt']),false);
 fs.mkdirSync(path.join(root,'src'));
 fs.writeFileSync(path.join(root,'src','file.py'),'value=1');
 assert.equal(admittedRead(root,{path:'a.txt:1-3'},'read',['a.txt']),true);
 assert.equal(admittedRead(root,{path:'src/file.py'},'read',['src']),true);
 assert.equal(admittedRead(root,{path:'src',pattern:'value'},'grep',['src']),true);
 assert.equal(admittedRead(root,{path:'src/**/*.py'},'glob',['src']),true);
 assert.equal(admittedRead(root,{path:'a.txt;src'},'grep',['a.txt','src']),true);
 assert.equal(admittedRead(root,{path:'src',pat:'value = $X'},'ast_grep',['src']),true);
 assert.equal(admittedRead(root,{path:'src/**/*.py',pat:'value = $X'},'ast_grep',['src']),true);
 assert.equal(admittedRead(root,{path:'a.txt',pat:'$X'},'ast_grep',['src']),false);
 assert.equal(admittedRead(root,{path:'src:1-2',pat:'$X'},'ast_grep',['src']),false);
 for(const name of ['read','grep','glob','ast_grep']){
  for(const value of ['../outside','xd://tool','local://outside','https://example.com/','src/../a.txt','src/*.py/../../a.txt'])assert.equal(admittedRead(root,{path:value},name,['src']),false,value);
  assert.equal(admittedRead(root,{path:'a.txt'},name,['src']),false);
 }
 assert.equal(admittedRead(root,{},'glob',['src']),false);
 assert.equal(admittedRead(root,{path:'*.py'},'glob',['src']),false);
 const outside=fs.mkdtempSync(path.join(os.tmpdir(),'crew-read-outside-'));
 try{
  fs.mkdirSync(path.join(outside,'src'));fs.writeFileSync(path.join(outside,'src','file.py'),'other_project=1');
  assert.equal(admittedRead(root,{path:path.join(outside,'src','file.py')},'read',['src']),false);
  assert.equal(admittedRead(root,{path:'src/file.py'},'read',['src']),true);
  try{fs.symlinkSync(outside,path.join(root,'src','escape'),process.platform==='win32'?'junction':'dir');}
  catch(error){if(error.code!=='EPERM'&&error.code!=='EACCES')throw error;console.log('SKIP: symlink privilege unavailable');}
  if(fs.existsSync(path.join(root,'src','escape'))){
   assert.equal(admittedRead(root,{path:'src/escape'},'read',['src']),false);
   assert.equal(admittedRead(root,{path:'src'},'grep',['src']),false);
   assert.equal(admittedRead(root,{path:'src/**'},'glob',['src']),false);
   assert.equal(admittedRead(root,{path:'src/**',pat:'$X'},'ast_grep',['src']),false);
  }
 }finally{fs.rmSync(outside,{recursive:true,force:true});}
 console.log('PASS: workflow read grants, selectors, scoped search, URI/traversal and symlink escape guards');
 console.log('PASS: current hashline edit API respects all declared targets and rejects moves/escape');
}finally{fs.rmSync(root,{recursive:true,force:true});}
