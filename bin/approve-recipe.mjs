#!/usr/bin/env node
// Run by operator in a separate terminal. Never pass private keys to model tools.
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
const [operation,...args]=process.argv.slice(2);
if(operation==='init'){
 const [privateFile,publicFile]=args;
 for(const file of [privateFile,publicFile])if(file&&fs.existsSync(file)&&fs.statSync(file).isDirectory())throw Error('Key path is a directory; provide a NEW file path, for example DIRECTORY/operator-private.pem. Normal setup requires no key.');
 if(!privateFile||!publicFile||fs.existsSync(privateFile)||fs.existsSync(publicFile))throw Error('init requires two NEW key paths');
 const keys=crypto.generateKeyPairSync('ed25519');
 fs.writeFileSync(privateFile,keys.privateKey.export({type:'pkcs8',format:'pem'}),{mode:0o600,flag:'wx'});
 fs.writeFileSync(publicFile,keys.publicKey.export({type:'spki',format:'pem'}),{flag:'wx'});
 console.log('Operator key created. Keep private file outside all agent-accessible paths. Provision public key as selected state/operator-public.pem.');
}else if(operation==='sign'){
 const [requestFile,project,privateFile,outputFile]=args;
 if(!requestFile||!project||!privateFile||!outputFile||fs.existsSync(outputFile))throw Error('sign REQUEST PROJECT PRIVATE_KEY NEW_OUTPUT required');
 if(!fs.statSync(privateFile).isFile())throw Error('PRIVATE_KEY must be a PEM file, not a directory. Normal setup requires no key.');
 const request=JSON.parse(fs.readFileSync(requestFile,'utf8'));
 delete request.approval;delete request.confirmed;
 const canonical=v=>JSON.stringify(v&&typeof v==='object'?Array.isArray(v)?v.map(normalize):normalize(v):v);
 function normalize(v){if(Array.isArray(v))return v.map(normalize);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).filter(k=>!['approval','confirmed','recipe_approval','recipe_confirmed'].includes(k)).sort().map(k=>[k,normalize(v[k])]));return v;}
 const payload={request_hash:crypto.createHash('sha256').update(canonical(request)).digest('hex'),project:process.platform==='win32'?path.resolve(project).toLowerCase():path.resolve(project),expires:Math.floor(Date.now()/1000)+900,nonce:crypto.randomBytes(24).toString('hex')};
 const signature=crypto.sign(null,Buffer.from(canonical(payload)),fs.readFileSync(privateFile)).toString('base64');
 fs.writeFileSync(outputFile,JSON.stringify({...request,confirmed:true,approval:{payload,signature}},null,2),{flag:'wx'});
 console.log('Signed one exact request for 15 minutes; replay is refused.');
}else throw Error('Usage: approve-recipe.mjs init PRIVATE PUBLIC | sign REQUEST PROJECT PRIVATE NEW_OUTPUT');
