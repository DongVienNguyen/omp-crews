export const POLICY_MODELS = ['haiku','sonnet','opus'];
export const POLICY_EFFORTS = {
  haiku: ['high'],
  sonnet: ['low','medium','high','xhigh','max'],
  opus: ['low','medium','high'],
};

export function validatePolicyInput(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('policy must be an object');
  const keys=Object.keys(value);
  if (keys.some(k => k !== 'provider' && k !== 'models')) throw Error('policy accepts only provider and models');
  if (typeof value.provider !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(value.provider)) throw Error('provider must be a bounded identifier');
  if (!value.models || typeof value.models !== 'object' || Array.isArray(value.models) || Object.keys(value.models).sort().join(',')!=='haiku,opus,sonnet') throw Error('models must contain haiku, sonnet and opus');
  const seen=new Set();
  for (const name of POLICY_MODELS) { const id=value.models[name]; if (typeof id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(id)) throw Error(`models.${name} must be a bounded identifier`); if (seen.has(id)) throw Error('model identifiers must be distinct'); seen.add(id); }
  return structuredClone(value);
}

export function effortOptions(model) { return [...(POLICY_EFFORTS[model] ?? [])]; }

export function policyForm(policy) {
  const value=validatePolicyInput(policy);
  return POLICY_MODELS.map(name => ({id:name,label:name,model:value.models[name],efforts:effortOptions(name)}));
}
