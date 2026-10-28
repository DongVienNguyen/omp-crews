export async function manageRecipes(ui, request){
 const operation=await ui.select('Adaptive recipes',['status','register','evidence','activate','audit','suspend','rollback','configure','probe']);
 if(!operation)return {changed:false};
 if(operation==='status')return {changed:false,result:request({operation})};
 const text=await ui.input('Request JSON (authority and evidence remain independently validated)','{}');
 if(text===undefined)return {changed:false};
 const args=JSON.parse(text);
 if(!args||typeof args!=='object'||Array.isArray(args))throw Error('Request JSON object required');
 if(!await ui.confirm('Confirm recipe '+operation+'?',JSON.stringify(args,null,2)+'\nNo new tool authority or main model changes.'))return {changed:false};
 return {changed:true,result:request({...args,operation,confirmed:true})};
}
