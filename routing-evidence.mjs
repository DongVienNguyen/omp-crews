export function sessionRoutingReport(entries, project) {
 const paths={};const models={};const routes={};const floors={};
 for(const entry of entries){
  if(entry.type!=='custom'||entry.customType!=='crews-routing'||entry.data?.project!==project)continue;
  const row=entry.data;paths[row.path]=(paths[row.path]??0)+1;
  if(row.candidate_route)routes[row.candidate_route]=(routes[row.candidate_route]??0)+1;
  for(const reason of row.blocked_by??[])floors[reason]=(floors[reason]??0)+1;
  const native=row.native??row;
  if(native.model){const key=String(native.model);models[key]=(models[key]??0)+1;}
 }
 return {scope:'current-session-branch',paths,model_events:models,capability_events:routes,blocked_by:floors,main_population:'unknown',note:'Main/native-task events are not Crews Combo executions; counts are events, not inferred task cost.'};
}
