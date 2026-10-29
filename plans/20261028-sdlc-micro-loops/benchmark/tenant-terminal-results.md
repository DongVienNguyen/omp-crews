# Tenant terminal native-completion regression

## Result

The requested missing baseline native completion is resolved in a new frozen regression run. Baseline and candidate each have **1/1 strict accepted**, independent behavior pass, authenticated native/wire proof, valid caller-schema output, no missing proof and no binding/artifact violations. Quality gate is true.

The paired evaluator still returns **NO_GO solely because latency_gate=false**: baseline end-to-end224301ms, candidate391331ms; candidate exceeds baseline1.2x gate. These are single known regression observations, not a production latency estimate. Money not evaluated. No gate changed, model remapped, deadline extended or old attempt rewritten.

## Earlier cancellation trace

Old baseline tenant writer completed its admitted read/edit/oracle tool work by approximately50.3seconds. After oracle response, no further tool or token growth was recorded until the approximately575.9second cancellation. No rejected yield or schema-retry loop was observed. Final native output absent, structured status unavailable. That evidence proves missing final delivery, not provider-side root cause. A provider response stall remains possible; successful artifact checks do not supply missing native proof.

A concrete repository contract mismatch was identified: role brief requested returning plain JSON, while native task.structured requires terminal `yield({data: full result})`. Adapter now explicitly requests yield submission after required work/checks, all schema fields nested in data, actual non-COMPLETE status when evidence missing, no repeated successful checks or unrelated work. Scope, acceptance, independent checker, receipt/model gates, retry caps and deadline remain unchanged. This correction does not prove why provider stalled in the historical attempt or guarantee future availability.

## New native evidence

Same configured main/Combo models and efforts; writer Large/high, checker Small/medium; original tenant criteria;600-second arm deadline; private immutable executable snapshot and pinned host/native configuration. No implicit retry or resumed/replaced old attempt.

| Role | Native duration ms | Requests | Exit | Aborted | Caller structured status |
|---|---:|---:|---:|---|---|
| Baseline writer |168413|7|0|false|valid|
| Baseline checker |24512|3|0|false|valid|
| Candidate writer |333138|7|0|false|valid|
| Candidate checker |25527|3|0|false|valid|

Baseline child progress includes a successful native yield. Baseline writer returned concrete cause/edit/oracle evidence and ordered passing criteria; checker independently executed immutable oracle. Host evaluator accepted both arms with zero gaps/violations. The new accepted rows are not merged into older64-arm or8-arm reports.

## Verification and limits

- `check_plan_contract.py`, `check_workflow_native.mjs`, `check_result_policy.mjs`, `check_workflow.py`, `check_workflow_repair.py`, `check_quality_evaluation.py`, `check_frozen_benchmark.py`, `check_effort_policy.py` passed after protocol correction.
- Native scripted smoke asserts caller-source valid structured output for scout/writer/checker and actual host artifact behavior. Real tenant regression separately proves native completion/model receipts.
- Independent source review `8eb50c8207c4448f83878f4381f1537c` COMPLETE within terminal-protocol/safety scope; static review only, no causal/provider guarantee.
- Runtime SDLC remains enabled, doctor ready. Model/effort, source authority, acceptance, proof gates,600-second deadline and retry caps unchanged. Existing failed/cancelled attempts remain immutable.

## Private provenance

Local evidence remains outside Git under `crews-tenant-terminal-proof-20261029`: frozen runtime snapshot/proof, signed freeze, baseline/candidate transcripts and terminal artifacts, state database and report. Report SHA-256: `c1749e2c69ba3be173a77f80c0c64a90502bf63b500ad163c59e61e175da2465`. Runtime source digest: `4b26e479c8406e79c3ea5af6da74c27a457212d287c9c0e72013aece261819e0`. No provider transcript, credentials, keys or state payload published.
