export default function(pi:any){
 const base=process.env.CREWS_LOCAL_PROVIDER_URL;
 if(!base)throw Error('Local scripted provider URL required');
 pi.registerProvider('9router',{baseUrl:base,apiKey:'local-scripted-no-secret',models:['code-seek','code-sol','code-astra'].map(id=>({id,name:id,api:'openai-completions',reasoning:true,input:['text'],contextWindow:100000,maxTokens:4096,cost:{input:0,output:0,cacheRead:0,cacheWrite:0},thinking:{mode:'effort',efforts:['low','medium','high','xhigh','max'],defaultLevel:'high',requiresEffort:true},compat:{supportsReasoningEffort:true,supportsReasoningParams:true,thinkingFormat:'openai'}}))});
}
