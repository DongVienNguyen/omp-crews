import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {admittedWrite} from './write-scope.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'crew-scope-'));
try{
 fs.writeFileSync(path.join(root,'a.txt'),'a');
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nPUT 1.=1:\n+b'},'edit',['a.txt']),true);
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nREM\n[outside.txt#1234]\nREM'},'edit',['a.txt']),false);
 assert.equal(admittedWrite(root,{input:'[a.txt#ABCD]\nMV outside.txt'},'edit',['a.txt']),false);
 assert.equal(admittedWrite(root,{path:'xd://tool'},'write',['a.txt']),false);
 assert.equal(admittedWrite(root,{path:'../a.txt'},'write',['a.txt']),false);
 console.log('PASS: current hashline edit API respects all declared targets and rejects moves/escape');
}finally{fs.rmSync(root,{recursive:true,force:true});}
