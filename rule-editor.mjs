export async function manageRules(ui,request){
 const operation=await ui.select('External AI rule editing',['export policy','export recipe','import optimized packet']);
 if(!operation)return {changed:false};
 if(operation.startsWith('export')){
  const recipe_id=operation==='export recipe'?await ui.input('Recipe ID',''):undefined;
  if(operation==='export recipe'&&!recipe_id)return {changed:false};
  const packet=request({operation:'export',kind:recipe_id?'recipe':'policy',...(recipe_id?{recipe_id}:{})});
  const text=JSON.stringify(packet,null,2);
  await ui.editor('Copy this JSON to external AI; edit only proposal',text);
  return {changed:false,packet};
 }
 const packet=await ui.editor('Paste optimized crews-rule JSON','');
 if(!packet?.trim())return {changed:false};
 if(!await ui.confirm('Queue external rule for Large review?','No direct activation. Host validates original context and current revision.'))return {changed:false};
 return {changed:true,result:request({operation:'import',packet,confirmed:true})};
}
