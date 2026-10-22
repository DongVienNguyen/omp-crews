export async function manageLearning(ui, request) {
 const action=await ui.select('Verified classification learning',['Status','Verified Small result','Label observation','Activate rule','Rollback rule','Mode']);
 if(!action)return {changed:false};
 if(action==='Status'){ui.notify(JSON.stringify(request({operation:'report'})),'info');return {changed:false};}
 let args;
 if(action==='Mode'){
  const mode=await ui.select('Learning mode',['shadow','on','off']);
  if(!mode)return {changed:false};args={operation:'configure',mode};
 }else if(action==='Label observation'||action==='Verified Small result'){
  if(action==='Verified Small result'){
   const result=await request({operation:'feedback_options'});
   const candidates=(result.feedback_options??[]).filter(item=>['run','role','session'].every(key=>typeof item[key]==='string'&&item[key].length>0));
   if(!candidates.length){ui.notify('No eligible Small results available for verified feedback.','info');return {changed:false};}
   const title=item=>JSON.stringify({run:item.run,role:item.role,session:item.session});
   const selected=await ui.select('Select independently verified Small result (run / role / session)',candidates.map(title));
   const candidate=candidates.find(item=>title(item)===selected);
   if(!candidate)return {changed:false};
   args={operation:'feedback',run:candidate.run,role:candidate.role,session:candidate.session,verified_small:true};
  }else{
   const id=await ui.input('Observation ID (see learning observations)');if(!id)return {changed:false};
   args={operation:'label',observation_id:id};
  }
  const need=await ui.select('Verified need',['bounded_retrieval','repeatable_task','mechanical_verification','everyday_implementation','long_running_agentic','difficult_review','integration_architecture','specialist']);if(!need)return {changed:false};
  const difficulty=await ui.select('Verified difficulty',['0','1','1.5','2','2.5','3']);if(difficulty==null)return {changed:false};
  const split=await ui.select('Independent evaluation split',['train','holdout']);if(!split)return {changed:false};
  const unit=await ui.input('Independent task/check identifier (must not repeat across splits)');if(!unit)return {changed:false};
  const evidence=await ui.input('Why this classification was verified (not self-reported COMPLETE)');if(!evidence)return {changed:false};
  args={...args,need,difficulty:Number(difficulty),split,unit_id:unit,evidence};
 }else{
  const rule_id=await ui.input('Rule ID');if(!rule_id)return {changed:false};args={operation:action==='Activate rule'?'activate':'rollback',rule_id};
 }
 if(!await ui.confirm('Apply learning change?',JSON.stringify({...args,evidence:args.evidence?'[evidence hashed, not persisted raw]':undefined},null,2)+'\nOnly independently verified labels count; COMPLETE alone is not verification. Candidate activation requires disjoint holdout validation.'))return {changed:false};
 const result=await request(args);ui.notify(action==='Verified Small result'?'Verified Small feedback recorded.':JSON.stringify(result),'info');return {changed:true,result};
}
