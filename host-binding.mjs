import {createHash} from 'node:crypto';

const reserved=new Set(['read','grep','glob','find','ls','ast_grep','yield','bash','write','edit','task','eval','workpool','vibe','clone']);
// Canonical JSON tree: type tags, float64 big-endian hex (zero normalized),
// UTF-16BE hex strings/keys. Sort keys by that hex; final JSON is ASCII only.
function stringHex(value){
 const bytes=Buffer.alloc(value.length*2);
 for(let i=0;i<value.length;i++)bytes.writeUInt16BE(value.charCodeAt(i),i*2);
 return bytes.toString('hex');
}
function canonical(value){
 if(value===null)return ['null'];
 if(typeof value==='boolean')return ['boolean',value];
 if(typeof value==='number'){
  if(!Number.isFinite(value))throw Error('Host binding requires finite JSON numbers');
  const bytes=Buffer.alloc(8);bytes.writeDoubleBE(value===0?0:value);
  return ['number',bytes.toString('hex')];
 }
 if(typeof value==='string')return ['string',stringHex(value)];
 if(Array.isArray(value))return ['array',Array.from(value,canonical)];
 if(value&&typeof value==='object'&&(Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null)){
  const entries=Object.keys(value).map(key=>[stringHex(key),canonical(value[key])]);
  entries.sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0);
  return ['object',entries];
 }
 throw Error('Host binding requires JSON values');
}
export function bindingDigest(value){return createHash('sha256').update(JSON.stringify(canonical(value)),'ascii').digest('hex');}
export function prepareHostBinding(options){
 if(!options||!Array.isArray(options.tools))throw Error('Host binding requires original tool definitions');
 const names=new Set();
 const tools=options.tools.map(tool=>{
  const name=tool?.name;
  if(typeof name!=='string'||!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(name)||reserved.has(name.toLowerCase())||name.toLowerCase().startsWith('mcp__')||names.has(name)||typeof tool.execute!=='function'||!tool.parameters||typeof tool.parameters!=='object')throw Error('Invalid trusted host tool');
  names.add(name);return {name,schema_hash:bindingDigest(tool.parameters)};
 });
 const limits=options.limits;
 for(const key of ['max_output_tokens','max_input_bytes','max_output_bytes'])if(!Number.isSafeInteger(limits?.[key])||limits[key]<1)throw Error('Explicit positive host budget required');
 if(!Number.isSafeInteger(options.deadline)||options.deadline<=Date.now())throw Error('Finite future host deadline required');
 const resultSchema=options.resultSchema===undefined?{type:'string'}:structuredClone(options.resultSchema);
 const descriptor={version:1,tools,result_schema:resultSchema,limits:{max_output_tokens:limits.max_output_tokens,max_input_bytes:limits.max_input_bytes,max_output_bytes:limits.max_output_bytes},deadline:options.deadline};
 const digest=bindingDigest(descriptor);
 return {descriptor,digest,tools:[...options.tools],onComplete:options.onComplete};
}
export function assertHostBinding(binding,admitted){
 if(!binding||!admitted||admitted.digest!==binding.digest||bindingDigest(admitted.descriptor)!==binding.digest||bindingDigest(binding.descriptor)!==binding.digest)throw Error('Trusted host binding mismatch');
 for(const tool of binding.tools){const expected=binding.descriptor.tools.find(item=>item.name===tool.name);if(!expected||bindingDigest(tool.parameters)!==expected.schema_hash)throw Error('Trusted host tool schema changed');}
 if(Date.now()>=binding.descriptor.deadline)throw Error('Trusted host deadline expired');
}
export function createHostLedger(binding){
 let outputTokens=0,outputBytes=0,failure;
 const limits=binding.descriptor.limits;
 return {
  request(payload){
   if(failure)throw Error(failure);
   if(Date.now()>=binding.descriptor.deadline)throw Error('host_deadline');
   if(Buffer.byteLength(JSON.stringify(payload),'utf8')>limits.max_input_bytes)throw Error('input_byte_limit');
   const remaining=limits.max_output_tokens-outputTokens;
   if(remaining<1||outputBytes>=limits.max_output_bytes)throw Error('output_budget_exhausted');
   return {...payload,max_tokens:Math.min(remaining,Number.isSafeInteger(payload.max_tokens)&&payload.max_tokens>0?payload.max_tokens:remaining)};
  },
  observe(message){
   const tokens=message.usage?.output;
   outputBytes+=Buffer.byteLength(JSON.stringify(message.content),'utf8');
   if(!Number.isSafeInteger(tokens)||tokens<0||(tokens===0&&Array.isArray(message.content)&&message.content.length))failure='output_usage_unknown';
   else outputTokens+=tokens;
   if(outputTokens>limits.max_output_tokens||outputBytes>limits.max_output_bytes)failure='output_budget_exhausted';
   if(failure)throw Error(failure);
  },
  status(){return {outputTokens,outputBytes,...limits};}
 };
}
