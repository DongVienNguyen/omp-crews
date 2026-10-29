# Immutable-runtime regression evidence

## Scope and verdict

Eight real-provider arms completed for four **previously seen regression units**: transform-csv, repair-intervals, security-tenant, perf-stream-topk. Same original acceptance/model policy and600-second arm deadline. No implicit retry, replay, model change or new unseen-holdout claim. Old64-arm results remain unchanged.

| Unit | Baseline strict accepted | Candidate strict accepted |
|---|---|---|
| transform-csv |yes|yes|
| repair-intervals |yes|yes|
| security-tenant |no — cancelled writer|yes|
| perf-stream-topk |yes|yes|

Candidate **4/4strict accepted**, baseline **3/4**. All accepted rows have independent executable behavior pass, authenticated native/model receipts and original-acceptance binding. **Zero binding/artifact violations**, unlike old mixed-condition evaluation. Final signed evaluator remains **NO_GO**, quality_gate=false and latency_gate=false, because baseline tenant has missing delivery/model/behavior proof. Missing evidence must not be treated as pass.

Three gap entries all refer to baseline security-tenant: attempt_model_proof_missing, immutable_attempt_receipt_missing, independent_behavior_unknown. Baseline recorded P95 approximately602630ms; candidate239570ms. These four known regression units do not establish production performance, model equivalence or broad noninferiority; no monetary evaluation performed.

## Remaining delivery blocker

Baseline tenant producer Large/high was aborted at575935ms after8requests. Native output metadata: source=caller, mode=strict, status=unavailable, exitCode1, aborted=true, empty output, no native error field. Last recorded tool was the admitted oracle command, without tool error. A separate post-cancellation diagnostic of unchanged product.py ran oracle.py and passed all3criteria: own-tenant copied read, anonymous/cross-tenant denial, nondisclosing missing-record error.

Artifact pass is not a completed native task. Cancellation/absent final model receipt remains unverified delivery. No historical result or attempt was rewritten; diagnostic oracle run was not entered as a replacement receipt. Provider latency/availability cannot be repaired through benchmark code; deadline, model and evidence guards were not weakened to manufacture GO.

## Repair and checks

- Runner reserves fresh output, snapshots whitelist executable source and generated host extension, then re-execs runner/bridge/extension/evaluator inside private runtime before task freeze.
- Source digests, host config/model digests, strict native overlay, normalized policy and Python identity pinned. Native bridge checks before/finally after request; workflow-next bridge and arms validate before/after. Missing policy refuses instead of default-model fallback.
- Mutable working checkout changed during regression, while snapshot source stayed stable. All8arms reached terminal artifacts; evaluator found no binding violations. Runtime proof source digest: `23d038de0fde46f5286a19d1bdcf4009efde804230382ba0e72d6c320ac39faf`.
- check_frozen_benchmark.py exercises real worker reexecution with equals-form CLI arguments, actual bridge pre-execution refusal and finally refusal on mutation during request. Checkout edits remain isolated; host/source/overlay/policy mutation and deletion rejected. Credentials digested only, not copied.
- Full32-unit oracle/64manifest validation and selected4-unit validation pass in snapshot. Packed npm artifact extracted and frozen regression check passed; no private state/model config/key/transcript in package.
- Independent closure review `d70c302351cd4d489922b3561a2bb078` COMPLETE within static snapshot/bridge/policy/CLI scope. Initial review findings preserved and corrected, not relabelled.
- Main SDLC runtime remains enabled and doctor ready. Changes affect evaluation harness, not production routing ceilings, acceptance, model/effort, retry caps or task authority.

## Private provenance

Local evidence retained outside Git under `crews-immutable-regression-20261029`: runtime-proof.json, private runtime source snapshot, signed frozen.json,8terminal artifacts, native logs, state database and report.json. Report SHA-256: `687b6e32714ec471dc1ceb529b35fd9846f73ddca5cadde68657be0f71294619`. Raw provider logs, credentials and state are not published.
