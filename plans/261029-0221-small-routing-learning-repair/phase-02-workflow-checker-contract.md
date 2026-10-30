---
title: "Phase 2: Workflow checker context và cross-run proof"
status: completed
---

# Phase2 — Same contract across direct and staged execution

P1; depends phase1. [Evidence F2/F3](evidence.md). Reuse workflow manifest, ledger and outcomes; no second scheduler.

## Files and steps

1. Modify `crews/workflow.py::{_validate,_advance,_attach,guard}`, `crews/omp_adapter.py::{prepare_plan,build_plan,record}`, `crews/outcomes.py::verified_pair`, `crews/attempt_ledger.py`. Separate **full immutable validation context** from roles actually dispatched in current stage. Passing complete workflow role context must not dispatch sibling checker early or widen authority.
2. Resolve routine_check to unique role identity `(workflow,node,role)`. Require later dependency/ancestor relationship, read-only checker, every original criterion, complete producer artifacts and oracle outside **all** writer scopes. Same name in different nodes must not be silently ambiguous. Stage-local planner should validate frozen linkage rather than require missing same-spec sibling.
3. Canonical verified outcome reference includes producer run/role/attempt and checker run/role/attempt plus workflow identity. Existing same-run consumers migrated through same validation owner, no copied result/synthetic admission. Enforce project, dependency order, authenticated native/wire/model proof, exact checker criteria/profile, artifact-version ownership, checker read-only and oracle immutable.
4. Failed/repaired producer invalidates prior checker pair. Capture only final current independent check for that attempt/version. Partial successor ownership cannot attribute unrelated failing criteria. Historical results/ledgers unchanged; legacy refs remain readable only under existing verified contract, not retroactively certified.
5. Record cross-node outcomes to recipes/automation from host after successful checker completion via canonical target refs. Do not let model supply host-owned refs/workflow metadata. Transactional dedup by immutable attempt pair, no cap or consent bypass.

## Todo

- [x] Direct plan versus split workflow equivalent producer/checker route behavior.
- [x] Canonical same-run/cross-node proof validator and consumer cutover in isolated working copy.
- [x] Completion-to-capture hooks handle workflow_targets without duplicate train units.
[Native provider cross-node Small trial và independent checker accepted; repair/stale regressions pass.](native-results.md)

## Gate

Regression: wrong project, same role, checker before writer, stale source/oracle/output, modified acceptance, missing native receipt, invalidated pre-repair check, ambiguous node names, nested scope, partial successor, same-unit duplicate all reject. One actual native split-node routine producer Small then independent executable check must pass and reach verified outcome **without** shim/replanning. Existing repair/recovery/stale tests remain pass. Source code reviewed by independent Large; technical review grants no production file/command permission.
