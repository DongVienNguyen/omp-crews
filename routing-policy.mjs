export function createPlanRecovery() {
 const pending = new Set();
 let failed = false;
 return {
  begin(id) { if (!pending.size) failed = false; pending.add(id); },
  result(id, isError) {
   if (!pending.delete(id)) return;
   if (isError) failed = true;
  },
  blockReason() {
   if (pending.size) return 'crew_plan pending; wait for its result before delegating.';
   return failed ? 'Repair crew_plan using crew_catalog schema/example before native delegation; do not silently fall back to an ordinary task.' : null;
  },
  reset() { pending.clear(); failed = false; },
 };
}

export function isCrewPlanCall(name, input) {
 return name === 'mcp__crews_omp_crew_plan' || name === 'crew_plan' ||
  (name === 'write' && input?.path === 'xd://mcp__crews_omp_crew_plan');
}
