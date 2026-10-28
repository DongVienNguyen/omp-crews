import {AsyncLocalStorage} from 'node:async_hooks';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {verifiedCompletion} from './result-policy.mjs';
import {createPlanRecovery,isCrewPlanCall} from './routing-policy.mjs';
import {callBridge} from './bridge-client.mjs';
import {resolveRuntime} from './runtime-paths.mjs';
import {Classifier,loadClassifierConfig} from './classifier.mjs';
import {completeSimple} from '@oh-my-pi/pi-ai';
import {editCombos} from './combo-editor.mjs';
import {classifyAdaptive} from './adaptive-classifier.mjs';
import {manageLearning} from './learning-editor.mjs';
import {sessionRoutingReport} from './routing-evidence.mjs';
import {admittedWrite,admittedRead} from './write-scope.mjs';
import {manageRecipes} from './recipe-editor.mjs';
import {manageRules} from './rule-editor.mjs';
const base=path.dirname(fileURLToPath(import.meta.url));
let settings:any;
try{settings=resolveRuntime(base);}catch{settings=null;}
function requireRuntime(){
 if(!settings)throw Error('Crews runtime is not provisioned. Run crews-omp setup --python <Python 3.12+ executable>, then restart OMP.');
 return settings;
}
function bridge(input:any){return callBridge(requireRuntime(),base,input);}
export default function(pi:any){
 const z=pi.zod;let child:any=null,wireOK=false,conflict=false;
 const dispatches=new Map<string,any>();const dispatchContext=new AsyncLocalStorage<any>();
 const recovery=createPlanRecovery();let mainReceipt=false;
 let classifierRequest=false;
 let automationDraining=false;
 const classifier=new Classifier(async(request:any)=>{
  const requestContext=request.context;
  const resolved=requestContext.models.resolve(request.model);
  if(!resolved)throw Error('Classifier model is unavailable: '+request.model);
  classifierRequest=true;
  try{
   const effort=request.model.slice(request.model.lastIndexOf(':')+1);
   if(effort!=='low'&&effort!=='medium'&&effort!=='high')throw Error('Classifier requires a valid Combo effort');
   const message=await completeSimple(resolved,{systemPrompt:[request.prompt],messages:[{role:'user',content:JSON.stringify(request.input),timestamp:Date.now()}]},{apiKey:requestContext.modelRegistry.resolver(resolved,requestContext.sessionManager.getSessionId()),reasoning:effort,maxTokens:request.maxTokens,signal:request.signal});
   return {text:message.content.filter((p:any)=>p.type==='text').map((p:any)=>p.text).join(''),stopReason:message.stopReason,usage:message.usage};
  }finally{classifierRequest=false;}
 });
 async function classifyRole(role:any,ctx:any,signal?:AbortSignal,preview=false,roles?:any[]){
  if((role.answers?.need==null||role.answers?.difficulty==null)&&role.classification!==true)throw Error('Automatic classification requires classification:true; otherwise supply need/difficulty');
  const declared=bridge({op:'classify',role,roles,project:ctx.cwd});
  const result=await classifyAdaptive({role,project:ctx.cwd,session:ctx.sessionManager.getSessionId(),declared,config:loadClassifierConfig(settings.state,declared.classifier_model),classifier,learning:(args:unknown)=>bridge({op:'learning',args,project:ctx.cwd}),revalidate:(value:unknown)=>bridge({op:'classify',role:value,roles,project:ctx.cwd}),signal,context:ctx,preview});
  routeEvidence(ctx,{path:result.semantic?'classifier':result.outcome==='learned'?'learned-classification':'classification',outcome:result.outcome,shadow_sampled:result.shadow_sampled,observation_id:result.learning?.observation_id,rule_id:result.learning?.rule_id,latencyMs:result.semantic?.latencyMs,cacheHit:result.semantic?.cacheHit,usage:result.semantic?.usage});
  return result;
 }
 function routeEvidence(ctx:any,entry:any){pi.appendEntry('crews-routing',{...entry,project:ctx.cwd,time:Date.now()});}
 function isChild(ctx:any){return ctx.agent?.kind==='sub';}
 function checkConflict(cwd?:string){
  const config=fs.existsSync(settings.config)?fs.readFileSync(settings.config,'utf8'):'';
  const router=path.join(path.dirname(settings.config),'extensions','omp-auto-router');
  conflict=/^\s*-\s*[^\n]*omp-auto-router/m.test(config)||fs.existsSync(router);
  if(pi.getCommands?.().some((command:any)=>command.name==='task-router'))conflict=true;
  if(pi.getAllTools().some((t:any)=>['router_control','router_review'].includes(t.name)))conflict=true;
  if(cwd){
   for(const file of ['.omp/config.yml','.omp/agent/config.yml']){
    const p=path.join(cwd,file);if(fs.existsSync(p)&&/omp-auto-router/.test(fs.readFileSync(p,'utf8')))conflict=true;
   }
  }
  if(conflict)throw Error('Crews and auto-router cannot run together. Restore or finish migration.');
 }
 pi.on('session_start',(_event:any,ctx:any)=>{recovery.reset();mainReceipt=false;try{checkConflict();}catch{conflict=true;}routeEvidence(ctx,{path:'main',model:ctx.model?.id,provider:ctx.model?.provider});});
 pi.on('before_agent_start',async(event:any,ctx:any)=>{
  if(!isChild(ctx)){
   recovery.reset();
   bridge({op:'automation_ensure',project:ctx.cwd});
   const pending=bridge({op:'automation',request:{operation:'status'},project:ctx.cwd});
   const resume=pending.enabled&&pending.jobs?.some((job:any)=>['queued','reviewing'].includes(job.state));
   return {message:{customType:'crews-routing-policy',content:'Crew work: read crew_catalog canonical schema and rubric before planning. Assign each role to Combo Small, Medium or Large using task capability; effort is Low/Medium/High or Auto from role difficulty. Auto: below1 low, below2 medium, otherwise high. Explicit Combo effort wins. Classify each role, not the entire project. Repair failed crew_plan before delegation; ordinary tasks receive no Crews routing. Main chat model stays unchanged.'+(resume?' Operator-authorized automation queue pending. Before other work invoke task with ONLY {automation:true}; host selects frozen jobs and enforces signed authority. Do not create replacement plans or approve requests yourself.':''),display:false}};
  }
  const token=((event.prompt||'')+'\n'+(event.systemPrompt||[]).join('\n')).match(/\[crew-ticket:([a-f0-9]{32})\]/)?.[1];
  if(!ctx.agent.name?.startsWith('crew-'))return;
  if(!token){ctx.abort();throw Error('Crew child has no admission ticket');}
  child=bridge({op:'ticket',token,project:ctx.cwd});
  if(child.call.agent_type!==ctx.agent.name){ctx.abort();throw Error('Crew child identity mismatch');}
 });
 pi.on('before_subagent_spawn',(event:any,ctx:any)=>{
  if(isChild(ctx)&&ctx.agent.name?.startsWith('crew-'))return {block:true,reason:'Crew depth is one'};
  if(!event.agent?.startsWith('crew-')){
   if(dispatches.size)return {block:true,reason:'Active crew requires planned seats'};
   return;
  }
  const active=dispatchContext.getStore();
  if(conflict||!active||event.agent!==active.call.agent_type)return {block:true,reason:'Crew spawn requires current native admission'};
  if(event.invocationKind&&event.invocationKind!=='task')return {block:true,reason:'Crews uses the native task path only'};
  if(active.spawnUsed)return {block:true,reason:'Admission already consumed for one child'};
  active.spawnUsed=true;
  return {model:`${active.call.provider??'9router'}/${active.call.model}:${active.call.reasoning_effort??'off'}`,note:'Crews planned effort policy'};
 });
 pi.on('before_provider_request',(event:any,ctx:any)=>{
  if(!isChild(ctx)){
   if(classifierRequest){routeEvidence(ctx,{path:'classifier-request',model:event.payload.model,provider:ctx.model?.provider,effort:event.payload.reasoning_effort??event.payload.reasoning?.effort??null});return;}
   if(!mainReceipt){routeEvidence(ctx,{path:'main',model:event.payload.model,provider:ctx.model?.provider,effort:event.payload.reasoning_effort??event.payload.reasoning?.effort??null});mainReceipt=true;}
   return;
  }
  if(!ctx.agent.name?.startsWith('crew-'))return;
  if(!child){ctx.abort();throw Error('Crew admission missing at provider boundary');}
  const model=event.payload.model,effort=event.payload.reasoning_effort??event.payload.reasoning?.effort??null;
  wireOK=model===child.call.model&&effort===child.call.reasoning_effort&&ctx.model?.provider===(child.call.provider??'9router');
  if(!wireOK){ctx.abort();throw Error('Crew model or effort drift');}
  const receipt={model,effort,provider:ctx.model?.provider,role:child.role,token:child.token,time:Date.now()};
  bridge({op:'store_receipt',token:child.token,project:ctx.cwd,payload:receipt});
 });
 pi.on('tool_call',(event:any,ctx:any)=>{
  if(!isChild(ctx)){
   if(isCrewPlanCall(event.toolName,event.input))recovery.begin(event.toolCallId);
   if(['eval','workpool','vibe','clone','task'].includes(event.toolName)&&!(event.toolName==='task'&&event.input?.intake)){
    const reason=recovery.blockReason();if(reason)return {block:true,reason};
   }
  }
  if(!isChild(ctx)&&dispatches.size>=2&&['eval','workpool','vibe','clone','task'].includes(event.toolName))return {block:true,reason:'Two crew dispatches already running'};
  if(!isChild(ctx)||!ctx.agent.name?.startsWith('crew-'))return;
  if(!child||!wireOK)return {block:true,reason:'Crew admission/wire verification missing'};
  try{bridge({op:'ticket',token:child.token,project:ctx.cwd});}catch{return {block:true,reason:'Crew admission expired/revoked'};}
  const name=event.toolName,input=event.input;
  const reads=['read','grep','glob','find','ls','ast_grep','yield'];
  if(reads.includes(name)&&(!child.call.workflow_id||name==='yield'||admittedRead(ctx.cwd,input,name,child.call.read_scope)))return;
  if(name==='bash'&&child.call.commands.includes(input.command))return;
  if(['write','edit'].includes(name)&&/^crew-(produce|integrate)-/.test(ctx.agent.name)&&admittedWrite(ctx.cwd,input,name,child.call.write_scope))return;
  return {block:true,reason:'Tool/command/file is outside admitted Crews authority'};
 });
 pi.on('tool_result',(event:any,ctx:any)=>{
  if(isChild(ctx)){
   if(child&&wireOK&&event.toolName==='bash'&&child.call.commands.includes(event.input?.command)){
    bridge({op:'store_tool_receipt',token:child.token,project:ctx.cwd,payload:{tool:'bash',command:event.input.command,exit_code:typeof event.details?.exitCode==='number'?event.details.exitCode:null,error:Boolean(event.isError||event.details?.timedOut),tool_call_id:event.toolCallId}});
   }
   return;
  }
  const nested=event.details?.xdev?.inner?.isError;
  recovery.result(event.toolCallId,Boolean(event.isError||nested));
 });
 async function dispatchCrew(ref:any,ctx:any,signal?:AbortSignal,update?:any){
  if(!ctx.invokeTool)throw Error('Native task delegation API unavailable; Crews disabled');
  checkConflict(ctx.cwd);if(isChild(ctx)||dispatches.size>=2)throw Error('Only main session with available native slot dispatches Crews');
  const active=bridge({op:'dispatch',run:ref.run,role:ref.role,session:ref.session,project:ctx.cwd});
  dispatches.set(active.token,active);
  try{
  routeEvidence(ctx,{path:'crew',run:ref.run,role:ref.role,requested_combo:active.call.requested_combo,effective_combo:active.call.policy_combo,bounded_small:active.call.bounded_small,model:active.call.model,effort:active.call.reasoning_effort,classification:active.call.role_answers,reason:active.call.routing_reason});
   if(active.call.stage||active.call.workflow_stage)ctx.ui?.notify?.(`[ROUTE: ${active.call.policy_combo} | KEY: ${active.call.role_answers.need} | STAGE: ${active.call.stage??active.call.workflow_stage} | TASK: ${active.call.role_id}]`,'info');
   const projectAgent=path.join(ctx.cwd,'.omp/agents',active.call.agent_type+'.md');
   const managedAgent=path.join(base,'agents',active.call.agent_type+'.md');
   for(const override of [projectAgent,path.join(settings.agentDir,'agents',active.call.agent_type+'.md')])if(fs.existsSync(override)&&fs.readFileSync(override,'utf8')!==fs.readFileSync(managedAgent,'utf8'))throw Error('Project/user shadows managed crew agent; review configuration');
   const started=performance.now();
   const criterionSchema={type:'array',items:{type:'object',properties:{criterion:{type:'string'},status:{type:'string',enum:['pass','fail']}},required:['criterion','status'],additionalProperties:false}};
   const outputSchema:any={type:'object',properties:{status:{type:'string',enum:['COMPLETE','PARTIAL','BLOCKED','FAILED']},verification:{type:'array',items:{type:'string'}},criterion_results:criterionSchema},required:active.call.checker_profile?['status','verification','criterion_results']:['status','verification']};
   if(active.call.automation_governance){outputSchema.properties.policy_decision=bridge({op:'automation_schema'});outputSchema.required.push('policy_decision');}
   if(active.call.context_request){outputSchema.properties.context_packet=bridge({op:'context_schema'});outputSchema.required.push('context_packet');}
   const result=await dispatchContext.run(active,()=>ctx.invokeTool({context:`Independent role; use only its brief. [crew-ticket:${active.token}]`,tasks:[{agent:active.call.agent_type,task:active.call.prompt,solutionSpace:'Execute explicit role authority. Model/effort from admission.',outputSchema,schemaMode:'strict'}]},{signal,onUpdate:update}));
   const rows=result.details?.results;
   const row=rows?.[0];const proof=bridge({op:'receipt',token:active.token,project:ctx.cwd});
   let payload=row?.structuredOutput?.data;
   if(!payload){try{payload=JSON.parse(row?.output||'');}catch{}}
   const hostVerification=active.call.checker_profile?bridge({op:'verify_profile',token:active.token,host_key:active.host_key,project:ctx.cwd}):null;
   const toolReceipts=bridge({op:'tool_receipts',token:active.token,project:ctx.cwd});
   const verified=proof?.model===active.call.model&&proof?.effort===active.call.reasoning_effort;
   const hostCriteria=hostVerification?.receipt?.criterion_results;
   const profileOk=!active.call.checker_profile||(hostVerification?.receipt?.exit_code===0&&Array.isArray(hostCriteria)&&hostCriteria.length===active.call.checker_profile.criteria.length&&hostCriteria.every((r:any,i:number)=>r.criterion===active.call.checker_profile.criteria[i]&&r.status==='pass'));
   const good=verifiedCompletion(row,payload,proof,active.call)&&profileOk;
   const durationMs=performance.now()-started;
   bridge({op:'record',run:ref.run,role:ref.role,session:ref.session,host_key:active.host_key,project:ctx.cwd,result:{status:good?'COMPLETE':'FAILED',producer_claim:payload?.status??null,context_packet:payload?.context_packet??null,policy_decision:active.call.automation_governance?payload?.policy_decision:null,criterion_results:hostCriteria??payload?.criterion_results??null,tool_receipts:toolReceipts,host_verification:hostVerification,failure_kind:row?.aborted?'cancelled':row?.error?'provider_error':!payload?'schema_error':toolReceipts.some((r:any)=>r.error)?'tool_error':good?null:'task_failed',verification:payload?.verification||['Native result incomplete or missing verified structured evidence'],native:{exitCode:row?.exitCode,resolvedModel:row?.resolvedModel,resolvedThinkingLevel:row?.resolvedThinkingLevel,usage:row?.usage,durationMs},wire:proof}});
   if(automationDraining&&!good)automationNotice(ctx,'failed',{run:ref.run,role:ref.role,reason:'Native review failed verified completion'});
   routeEvidence(ctx,{path:'crew-result',run:ref.run,role:ref.role,effective_combo:active.call.policy_combo,bounded_small:active.call.bounded_small,status:good?'COMPLETE':'FAILED',native:{model:row?.resolvedModel,effort:row?.resolvedThinkingLevel,exitCode:row?.exitCode,usage:row?.usage,durationMs},wire:proof});
   return result;
  }catch(err){
   try{bridge({op:'record',run:ref.run,role:ref.role,session:ref.session,host_key:active.host_key,project:ctx.cwd,result:{status:'FAILED',failure_kind:signal?.aborted?'cancelled':'dispatch_error',verification:['Dispatch cancelled or failed; retry requires explicit repair']}});}catch{}
   throw err;
  }finally{dispatches.delete(active.token);}
 }
 function automationNotice(ctx:any,status:string,detail:any){
  const message='Crews automation '+status+': '+JSON.stringify(detail);
  try{routeEvidence(ctx,{path:'crew-automation',status,detail});}catch{}
  try{pi.sendMessage({customType:'crews-automation',content:message,display:true},{triggerTurn:false});}catch{try{ctx.ui?.notify(message,'error');}catch{}}
 }
 async function drainAutomation(ctx:any,signal?:AbortSignal,update?:any){
  if(isChild(ctx)||dispatches.size||automationDraining)return;
  automationDraining=true;
  try{
   checkConflict(ctx.cwd);
   if(!ctx.invokeTool)throw Error('Native task delegation API unavailable; automation paused');
   for(let jobs=0;jobs<8&&!signal?.aborted;jobs++){
    const ref=bridge({op:'automation_next',project:ctx.cwd});
    if(!ref)return;
    if(ref.blocked){automationNotice(ctx,'blocked',ref.blocked);return;}
    await dispatchCrew(ref,ctx,signal,update);
    const status=bridge({op:'automation',request:{operation:'status'},project:ctx.cwd});
    const recorded=status.jobs?.find((job:any)=>job.run===ref.run);
    if(recorded){
     const applied=bridge({op:'automation_finish',job_id:recorded.id,project:ctx.cwd});
     if(applied.state==='blocked'){automationNotice(ctx,'blocked',applied.result);return;}
    }
   }
  }catch(error){automationNotice(ctx,'failed',error instanceof Error?error.message:String(error));}
  finally{automationDraining=false;}
 }
 pi.registerTool({name:'task',label:'Task / Crews dispatch',description:'Native task, admitted crew reference, canonical intake, or automation:true to drain only operator-authorized frozen Large reviews.',parameters:z.object({automation:z.boolean().optional(),crew:z.object({run:z.string(),role:z.string(),session:z.string()}).optional(),intake:z.object({spec:z.any(),answers:z.any(),session:z.string()}).optional(),context:z.string().optional(),tasks:z.array(z.any()).optional(),agent:z.string().optional(),task:z.string().optional(),solutionSpace:z.string().optional()}).passthrough(),async execute(_id:any,p:any,signal:any,update:any,ctx:any){
  if(!ctx.invokeTool)throw Error('Native task delegation API unavailable; Crews disabled');
  if(p.automation){
   if(Object.keys(p).some(key=>key!=='automation'))throw Error('automation cannot combine with task selectors');
   if(isChild(ctx)||dispatches.size)throw Error('Only idle main host drains automation');
   await drainAutomation(ctx,signal,update);
   const value=bridge({op:'automation',request:{operation:'status'},project:ctx.cwd});
   return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
  }
  if(p.intake){
   checkConflict(ctx.cwd);if(isChild(ctx)||dispatches.size)throw Error('Only idle main session may create a crew intake');
   if(p.crew||p.tasks||p.agent||p.task||p.model)throw Error('Intake cannot be combined with native selectors or existing crew reference');
   recovery.begin(_id);
   try{
   const spec=structuredClone(p.intake.spec);
   if(!Array.isArray(spec?.roles)||!spec.roles.length)throw Error('intake.spec.roles must be nonempty');
   for(const [index,role] of spec.roles.entries()){
    const required=['name','kind','mission','deliverable','scope','commands','answers'];
    const missing=required.filter(k=>!Object.hasOwn(role,k));
    if(!Object.hasOwn(role,role.kind==='check'?'criteria':'acceptance'))missing.push(role.kind==='check'?'criteria':'acceptance');
    if(role.model||role.agent)throw Error(`intake.spec.roles[${index}] cannot override model/agent`);
    if(missing.length)throw Error(`intake.spec.roles[${index}] missing: ${missing.join(', ')}`);
    const result=await classifyRole(role,ctx,signal,false,spec.roles);
    if(!result.answers)throw Error(`intake.spec.roles[${index}] requires_classification: ${result.semantic?.reason??result.reason}`);
    role.declared_answers={...role.answers};
    role.classification_evidence=result;
    role.answers=result.answers;
   }
   const plan=bridge({op:'plan',spec,answers:p.intake.answers,project:ctx.cwd,session:p.intake.session});
   recovery.result(_id,false);
   routeEvidence(ctx,{path:'crew-intake',toolCallId:_id,run:plan.run_id,roles:spec.roles.map((r:any)=>({name:r.name,answers:r.answers}))});
   return {content:[{type:'text',text:JSON.stringify({run:plan.run_id,session:plan.session,warnings:spec.roles.flatMap((r:any)=>r.classification_evidence?.warnings??[]),waves:plan.waves.map((w:any)=>({kind:w.kind,calls:w.calls.map((c:any)=>({role:c.role_id,model:c.model,effort:c.reasoning_effort,requested_combo:c.requested_combo,effective_combo:c.effective_combo,small_route:c.small_route,small_blockers:c.small_blockers,crew:{run:plan.run_id,role:c.role_id,session:plan.session}}))}))})}],details:{plan}};
   }catch(error){recovery.result(_id,true);throw error;}
  }
  if(!p.crew){
   const blocked=recovery.blockReason();if(blocked)throw Error(blocked);
   routeEvidence(ctx,{path:'native-task',note:'No Crews model remap applies'});
   if(p.agent?.startsWith('crew-')||p.tasks?.some((t:any)=>t.agent?.startsWith('crew-')))throw Error('Crew agent requires planned admission');
   const result=await ctx.invokeTool(p,{signal,onUpdate:update});
   routeEvidence(ctx,{path:'native-task-result',models:result.details?.results?.map((row:any)=>({model:row.resolvedModel,effort:row.resolvedThinkingLevel,exitCode:row.exitCode})),note:'Native delegation; no Crews plan or remap'});
   return result;
  }
  try{return await dispatchCrew(p.crew,ctx,signal,update);}
  finally{await drainAutomation(ctx,signal,update);}
 }});
 pi.registerTool({name:'crew_automation',label:'Local Large policy governance',description:'Keyless governance status/enable/disable and portable rule export/import proposals. Imported rules require independent Large review before apply.',parameters:z.object({request:z.object({operation:z.enum(['enable','disable','status','export','import','grant','revoke'])}).passthrough()}),async execute(_id:any,p:any,_signal:any,_update:any,ctx:any){
  if(isChild(ctx))throw Error('Automation administration belongs to main session');
  const value=bridge({op:'automation',request:p.request,project:ctx.cwd});
  return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
 }});
 pi.registerTool({name:'crew_recipe_preview',label:'Recipe candidates',description:'Read-only current-project recipe status or candidate lookup; no labels, hits or authority changes.',parameters:z.object({operation:z.enum(['status','report','lookup']),role:z.any().optional(),roles:z.array(z.any()).optional()}),async execute(_id:any,p:any,_signal:any,_update:any,ctx:any){
  if(isChild(ctx))throw Error('Recipe administration belongs to main session');
  const value=bridge({op:'recipes',args:p,project:ctx.cwd});return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
 }});
 pi.registerTool({name:'crew_learning',label:'Verified classification learning',description:'Read-only current-project learning status, feedback options, observations, rules or report. Mutations require explicit user CLI or /crew learning confirmation.',parameters:z.object({operation:z.enum(['status','observations','rules','report','feedback_options'])}),async execute(_id:unknown,input:{operation:string},_signal:unknown,_update:unknown,ctx:any){
  if(isChild(ctx))throw Error('Learning administration belongs to main session');
  const value=bridge({op:'learning',args:input,project:ctx.cwd});
  return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
 }});
 pi.registerTool({name:'crew_preview',label:'Crew classification preview',description:'Preview classification/seat or inspect routing report without admission/spawn. Operations status/test/history/report/reload.',parameters:z.object({operation:z.enum(['status','test','history','report','reload']),role:z.any().optional()}).passthrough(),async execute(_id:any,p:any,signal:any,_update:any,ctx:any){
  if(isChild(ctx))throw Error('Preview is a main-session capability');
  const value=await preview(p.operation,p.role,ctx,signal);
  return {content:[{type:'text',text:JSON.stringify(value)}],details:value};
 }});
 async function preview(operation:string,role:any,ctx:any,signal?:AbortSignal){
  const policy=bridge({op:'policy'});
  if(operation==='status')return {config:loadClassifierConfig(settings.state,policy.classifier_model),policy,runtime:{state:settings.state,agentDir:settings.agentDir},mainModelUnchanged:true};
  if(operation==='reload'){loadClassifierConfig(settings.state,policy.classifier_model);classifier.reload();return {reloaded:true,ticketsUnchanged:true};}
  if(operation==='history')return bridge({op:'history',project:ctx.cwd,limit:200});
  if(operation==='report')return {crews:bridge({op:'routing_report',project:ctx.cwd}),session:sessionRoutingReport(ctx.sessionManager.getBranch(),ctx.cwd)};
  if(operation!=='test'||!role)throw Error('crew test requires canonical role JSON; no task text is converted to authority');
  const result=await classifyRole(role,ctx,signal,true);
  return {classification:result,seat:result.answers?bridge({op:'preview',role:{...role,answers:result.answers},project:ctx.cwd}):null,spawned:false};
 }
 pi.registerCommand('crew',{description:'Crews combos/status/test/history/reload or plan a task',handler:async(args:any,ctx:any)=>{
  const [op,...rest]=args.trim().split(/\s+/);
  if(op==='rules'){
   if(!ctx.hasUI){ctx.ui.notify('Use crews-omp automation export/import --project PATH --request FILE','info');return;}
   try{const value=await manageRules(ctx.ui,(request:any)=>bridge({op:'automation',request,project:ctx.cwd}));ctx.ui.notify(JSON.stringify(value),'info');}catch(error:any){ctx.ui.notify(error.message,'error');}return;
  }
  if(op==='recipes'){
   if(!ctx.hasUI){ctx.ui.notify('Use crews-omp recipes --project PATH --request FILE --yes','info');return;}
   try{const value=await manageRecipes(ctx.ui,(args:any)=>bridge({op:'recipes',args,project:ctx.cwd}));ctx.ui.notify(JSON.stringify(value),'info');}catch(error:any){ctx.ui.notify(error.message,'error');}return;
  }
  if(op==='learning'){
   if(!ctx.hasUI){ctx.ui.notify('Use crews-omp learning status|label|activate|rollback in headless mode','error');return;}
   try{await manageLearning(ctx.ui,(args:unknown)=>bridge({op:'learning',args,project:ctx.cwd}));classifier.reload();}catch(error:unknown){ctx.ui.notify(error instanceof Error?error.message:String(error),'error');}
   return;
  }
  if(op==='combos'){
   if(!ctx.hasUI){ctx.ui.notify('Use crews-omp combo show|set|reset in headless mode','error');return;}
   try{
    const edited=await editCombos(ctx.ui,bridge({op:'policy'}),(value:unknown,expected_binding:string)=>bridge({op:'save_policy',value,expected_binding}),(model:string)=>ctx.models.resolve(model));
    if(edited.saved){classifier.reload();ctx.ui.notify('Combo policy saved. Create fresh plans; main model unchanged.','info');}
   }catch(error:unknown){ctx.ui.notify(error instanceof Error?error.message:String(error),'error');}
   return;
  }
  if(!['status','test','history','report','reload'].includes(op)){pi.sendUserMessage('Use crew-omp skill and crews-omp MCP to plan and execute this request: '+args);return;}
  try{const role=op==='test'?JSON.parse(rest.join(' ')):undefined;ctx.ui.notify(JSON.stringify(await preview(op,role,ctx)), 'info');}catch(error:any){ctx.ui.notify(error.message,'error');}
 }});
}
