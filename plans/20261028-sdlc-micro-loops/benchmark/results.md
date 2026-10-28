# Completed reconstructed provider evaluation

## Decision

Operator enabled SDLC before qualification. Enabled0.11.1 remains installed; this permission is separate from benchmark acceptance. Completed32paired exercises/64arms. Evaluator verdict **NO_GO**; quality_gate=false, latency_gate=false, evaluation_mode=quality_only, money_status=not_evaluated. No monetary calculation or savings claim.

## Evidence populations

| Population | Baseline | Candidate |
|---|---:|---:|
| Scheduled arms |32|32|
| Terminal artifacts |32|32|
| Workflow complete |23|23|
| Workflow blocked |9|9|
| Strict evaluator accepted |0|0|

Workflow complete is NOT strict acceptance. Initial/task authority, policy/source binding, model receipt, independent executable behavior and final delivery all must pass for strict acceptance. No failed arm replayed or removed.

### Workflow completions by reconstructed family

| Family | Baseline /4 | Candidate /4 |
|---|---:|---:|
| Retrieval/docs extraction |3|4|
| Exact transform/scaffold |4|4|
| Server-rendered UI/state CRUD |3|4|
| API/contract |3|3|
| Test/repair |4|2|
| Architecture/security |1|1|
| Concurrency/precision |4|3|
| Performance diagnosis |1|2|

These are completion counts, not correctness rates, production estimates or proof of noninferiority. UI family does not establish visual/browser fidelity.

## Why strict acceptance is zero

Implementation and host settings changed while the corpus was running: workflow source/routing policy snapshots changed and native task.structured was enabled partway through. Frozen source/policy/arm/attempt binding guards refused altered evidence. Dataset is mixed-condition diagnostic evidence, not a clean comparison of one unchanged revision. Retain original signed freeze and raw report; do not re-sign, rewrite old verdicts or treat corrected later configuration as if present from start.

Evaluator recorded171binding/artifact violations:

-68 frozen_attempt_binding_mismatch
-39 frozen_arm_binding_mismatch
-39 frozen_execution_binding_mismatch
-25 workflow_artifacts_changed

51missing-proof entries (entries may refer to same arm):17immutable_attempt_receipt_missing,17independent_behavior_unknown,16attempt_model_proof_missing,1immutable_workflow_latency_missing. Baseline P95 unavailable; candidate recorded P95 approximately600752ms, but aggregate latency gate remains false and must not be interpreted as a valid paired performance estimate.

## Attempt and failure evidence

119immutable provider attempts: Small68, Medium35, Large16. Latest call behavior:47pass,72unknown,1without outcome. No observed executable behavior fail in this population establishes that cancelled/unknown tasks were correct; those remain undelivered/unverified.

17recorded failed calls:16cancelled,1schema_error. Cancelled writer example ran approximately589258ms before deadline; native structured status unavailable. Schema-error checker had host executable behavior pass but no acceptable strict model envelope, therefore delivery remained failed. One additional blocked workflow was stopped by frozen policy drift rather than a failed call.

Paired completion regressions: api-idempotency, repair-intervals, repair-context-close, architecture-layering, concurrency-async-order, perf-stream-topk. Completion improvements: docs-route-index, ui-todo-create, api-pagination, security-redaction, perf-membership, perf-dag-cache. Improvements do not cancel regressions for acceptance.

## Verification after fixes

- Native normal-entry CSV smoke used crew_workflow prepare with no backend pre-admission, default sdlc_cost_aware, admitted writer, independent executable checker; host-authenticated writer/checker complete and checker behavior pass.
- Scripted native OMP smoke exercised prepare/next and yield({data:...}), with caller-source valid structured metadata for all three scout/writer/checker roles. Separate overlapping Small children smoke proved distinct wire tokens and fingerprints.
- Setup enables task.structured in registration transaction; doctor rejects false. Isolated real setup preserved modelRoles, sibling task settings and unrelated configuration. Main/canary0.11.1 doctor ready.
- Packaging11/11passed through10public-interface checks and1real lifecycle check. Offline wheelhouse avoided package-index stalls; dependency pins unchanged. Independent enabled-path/strict-setup/final-cutover source reviews COMPLETE, static scope only.
- Full corpus oracle validation:32originals fail,32reference solutions pass normal/error/boundary assertions. Repaired top-k oracle rejects full materialization and accepts bounded heap with sorted(heap). Original frozen runs were never relabelled.

## Local provenance

Private raw artifacts retained outside Git under `crews-sdlc-enabled-final-corpus`: frozen.json, schedule.json,64terminal JSON files, native transcripts, state/runs.sqlite and report.json. Report SHA-256: `d3a96b54577ea8c45677c59d8c835dbe8eee348beb3529db50ad037a1fe923ed`. Provider transcripts, state, keys and credentials are excluded from publication.

This evaluation is complete with a NO_GO result. A future qualification run needs a frozen unchanged release and host configuration, the same authority/acceptance, independent paired snapshots and no use of this diagnostic corpus as newly unseen holdout. No automatic repeat is authorized by this report.
