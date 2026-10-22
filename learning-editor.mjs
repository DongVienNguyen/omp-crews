export async function manageLearning(ui, request) {
 const action=await ui.select('Verified classification learning',['Status','Label observation','Activate rule','Rollback rule','Mode']);
 if(!action)return {changed:false};
 if(action==='Status'){ui.notify(JSON.stringify(request({operation:'report'})),'info');return {changed:false};}
 let args;
 if(action==='Mode'){
  const mode=await ui.select('Learning mode',['shadow','on','off']);
  if(!mode)return {changed:false};args={operation:'configure',mode};
 }else if(action==='Label observation'){
  const id=await ui.input('Observation ID (see learning observations)');if(!id)return {changed:false};
  const need=await ui.select('Verified need',['bounded_retrieval','repeatable_task','mechanical_verification','everyday_implementation','long_running_agentic','difficult_review','integration_architecture','specialist']);if(!need)return {changed:false};
  const difficulty=await ui.select('Verified difficulty',['0','1','1.5','2','2.5','3']);if(difficulty===undefined)return {changed:false};
  const split=await ui.select('Independent evaluation split',['train','holdout']);if(!split)return {changed:false};
  const unit=await ui.input('Independent task/check identifier (must not repeat across splits)');if(!unit)return {changed:false};
  const evidence=await ui.input('Why this classification was verified (not self-reported COMPLETE)');if(!evidence)return {changed:false};
  args={operation:'label',observation_id:id,need,difficulty:Number(difficulty),split,unit_id:unit,evidence};
 }else{
  const rule_id=await ui.input('Rule ID');if(!rule_id)return {changed:false};args={operation:action==='Activate rule'?'activate':'rollback',rule_id};
 }
 if(!await ui.confirm('Apply learning change?',JSON.stringify({...args,evidence:args.evidence?'[evidence hashed, not persisted raw]':undefined},null,2)+'\nOnly verified labels count. Candidate activation requires disjoint holdout validation.'))return {changed:false};
 const result=request(args);ui.notify(JSON.stringify(result),'info');return {changed:true,result};
}
