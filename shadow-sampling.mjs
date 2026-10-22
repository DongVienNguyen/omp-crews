import {createHash} from 'node:crypto';

export function createShadowSampler(){
 const sampled=new Map();
 return {
  select(role,declared,project,session,config,fingerprint){
   if(!declared.answers||declared.tier!=='medium'||role.kind!=='produce'||declared.answers.need!=='everyday_implementation'||declared.answers.difficulty>1.5||config.mode==='off')return false;
   const key=JSON.stringify([project,session,role,declared.policy_version,fingerprint]);
   if(sampled.has(key))return false;
   const sessionKey=JSON.stringify([project,session]);
   let count=0;for(const entry of sampled.values())if(entry===sessionKey)count++;
   if(count>=config.mediumShadowMax)return false;
   const bucket=createHash('sha256').update(key).digest().readUInt32BE(0)%100;
   if(bucket>=config.mediumShadowPercent)return false;
   if(sampled.size>=256)return false;
   sampled.set(key,sessionKey);
   return true;
  },
  reset(){sampled.clear();},
 };
}
