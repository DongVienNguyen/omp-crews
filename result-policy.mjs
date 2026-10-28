export function verifiedCompletion(row,payload,proof,call){
 const evidence=Array.isArray(payload?.verification)&&payload.verification.length>0&&payload.verification.every(v=>typeof v==='string'&&v.trim().length>0);
 const wire=proof?.model===call.model&&proof?.effort===call.reasoning_effort&&(!proof?.provider||proof.provider===(call.provider??'9router'));
 const identity=(!row?.resolvedModelIdentity||row.resolvedModelIdentity===`${call.provider??'9router'}/${call.model}`)&&(!row?.resolvedThinkingLevel||row.resolvedThinkingLevel===(call.reasoning_effort??'off'));
 return row?.exitCode===0&&!row.error&&!row.aborted&&wire&&identity&&(!row.structuredOutput||row.structuredOutput.status==='valid')&&payload?.status==='COMPLETE'&&evidence;
}
