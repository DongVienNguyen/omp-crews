export async function editCombos(ui, snapshot, save, resolveModel) {
 const policy=structuredClone(snapshot.model_policy);
 const combo=await ui.select('Configure Combo',['Small','Medium','Large']);
 if(!combo)return {saved:false};
 const provider=await ui.input('Provider',policy.provider);
 if(provider===undefined)return {saved:false};
 const model=await ui.input('Combo '+combo+' model',policy.combos[combo].model);
 if(model===undefined)return {saved:false};
 const effort=await ui.select('Effort (Auto uses classified task difficulty)',['Auto','Low','Medium','High']);
 if(!effort)return {saved:false};
 policy.provider=provider.trim()||policy.provider;policy.combos[combo]={model:model.trim()||policy.combos[combo].model,effort};
 for(const [name,item] of Object.entries(policy.combos)){
  const levels=item.effort==='Auto'?['low','medium','high']:[item.effort.toLowerCase()];
  for(const level of levels)if(!resolveModel(policy.provider+'/'+item.model+':'+level))throw Error('Unsupported OMP model/effort for Combo '+name+': '+policy.provider+'/'+item.model+':'+level);
 }
 if(!await ui.confirm('Save Combo policy?',JSON.stringify(policy,null,2)+'\nExisting plans will be refused. Credentials and main chat stay unchanged.'))return {saved:false};
 return {saved:true,result:save(policy,snapshot.policy_binding)};
}
