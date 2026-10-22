import {createHash} from 'node:crypto';
import {contextFingerprint,CLASSIFIER_PROMPT} from './classifier.mjs';

export async function classifyAdaptive({role,project,session,declared,config,classifier,learning,revalidate,signal,context,preview=false}) {
 const fingerprint=contextFingerprint(project,role);
 const version=createHash('sha256').update(JSON.stringify([declared.policy_version,CLASSIFIER_PROMPT,config.model])).digest('hex');
 const base={project,role,context_fingerprint:fingerprint,policy_version:version};
 let learningError=false;
 const store=request=>{try{return learning(request);}catch{learningError=true;return {unavailable:true,observation_id:null};}};
 const needsTeacher=!declared.answers;
 const lookup=needsTeacher&&!preview?store({...base,operation:'lookup'}):null;
 const audit=lookup?.match&&lookup.audit_due;
 let semantic=null;
 if(needsTeacher&&lookup?.match&&!audit&&lookup.answers){
  const checked=revalidate({...role,answers:{...role.answers,need:role.answers?.need??lookup.answers.need,difficulty:role.answers?.difficulty??lookup.answers.difficulty}});
  const observation=store({...base,operation:'observe',proposal:{need:checked.answers.need,difficulty:checked.answers.difficulty},metrics:{source:'learned',outcome:'unknown',teacher_avoided:true},rule_id:lookup.rule_id});
  return {...checked,outcome:'learned',learning:{...observation,rule_id:lookup.rule_id},semantic:null};
 }
 if(needsTeacher||config.mode==='shadow'||audit){
  semantic=await classifier.recommend(role,project,session,declared.policy_version,config,signal,context,Boolean(audit));
 }
 if(audit){
  store({...base,operation:'audit',rule_id:lookup.rule_id,proposal:semantic?.recommendation?{need:semantic.recommendation.need,difficulty:semantic.recommendation.difficulty}:null,outcome:semantic?.recommendation?'ok':semantic?.reason?.includes('timeout')?'timeout':semantic?.reason?.includes('canceled')?'cancelled':'provider_error'});
  // A failed or disagreeing audit never silently reuses the cached rule.
 }
 if(!audit&&lookup?.candidate_id&&lookup.answers&&semantic?.recommendation){
  store({...base,operation:'audit',rule_id:lookup.candidate_id,proposal:{need:semantic.recommendation.need,difficulty:semantic.recommendation.difficulty},outcome:'ok'});
 }
 let effective=declared;
 if(needsTeacher&&semantic?.recommendation&&config.mode==='recommend'){
  effective=revalidate({...role,answers:{...role.answers,need:role.answers?.need??semantic.recommendation.need,difficulty:role.answers?.difficulty??semantic.recommendation.difficulty}});
 }
 const classified=semantic?.recommendation??effective.answers;
 const proposal=classified?{need:classified.need,difficulty:classified.difficulty}:null;
 const usage=semantic?.usage;
 const outcome=semantic?.recommendation?'ok':!semantic?'ok':semantic.reason?.includes('timeout')?'timeout':semantic.reason?.includes('canceled')?'cancelled':semantic.outcome==='off'?'unknown':'provider_error';
 const observation=preview?null:store({...base,operation:'observe',proposal,metrics:{source:semantic?'teacher':declared.outcome,outcome,teacher_requested:Boolean(semantic&&semantic.outcome!=='off'),cache_hit:semantic?.cacheHit??false,latency_ms:semantic?.latencyMs??0,input_tokens:usage?.input??usage?.inputTokens??null,output_tokens:usage?.output??usage?.outputTokens??null,reasoning_tokens:usage?.reasoning??usage?.reasoningTokens??null},rule_id:lookup?.rule_id??null});
 return {...effective,semantic,learning:{...observation,unavailable:learningError}};
}
