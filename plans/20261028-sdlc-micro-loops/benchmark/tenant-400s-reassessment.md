# Tenant reassessment — operator absolute400-second ceiling

User explicitly replaced the relative1.2x latency limit with an absolute400-second candidate ceiling. This is a **post-hoc operator criterion change**, not a new signed freeze, provider rerun, or rewrite of historical evaluation.

## Rechecked result

Original signed tenant evidence was revalidated using its original snapshot evaluator and state. Both arms remain strict accepted1/1; quality_gate=true, authenticated=true, missing=[], violations=[]. Original relative verdict remains NO_GO with latency_gate=false.

| Criterion | Observed | New ceiling | Result |
|---|---:|---:|---|
| Candidate end-to-end P95 |391330.567837ms|400000ms|PASS|
| Quality/native/host proof |Both arms accepted1/1|Original criteria unchanged|PASS|

Baseline end-to-end P95224301.158667ms. Candidate headroom8669.432163ms (8.669seconds). **Verdict under requested absolute ceiling: GO for this known tenant pair.** No claim of production reliability, unseen-holdout qualification, monetary savings or future400second guarantee.

## Implementation and verification

New quality_only freezes may use positive finite `max_latency_ms` instead of `max_latency_ratio`; fields are mutually exclusive. Monetary/default relative behavior remains unchanged. Benchmark CLI `--max-latency-seconds 400` freezes `max_latency_ms:400000`; task execution deadline remains separate and unchanged. Absolute gate still requires complete latency and original quality/proof gates; no missing evidence can pass.

`check_absolute_latency.py` passed: inclusive400000ms boundary, rejection just above boundary, invalid/missing latency, unchanged relative comparison, signed absolute freeze/report, invalid signed limit types/nonfinite/nonpositive values, mutually exclusive criteria, original model/proof/quality/stale guards. Existing `check_quality_evaluation.py` passed. Independent static review `dfb53301d7464ca4a81b0fc2f4678ebe` COMPLETE within absolute-gate safety scope.

## Provenance

Original evaluation ID: `57042c874d53df25432ffd446cb2570053c9f99671debd210c5b3a337fb0a267`.

Original report SHA-256: `c1749e2c69ba3be173a77f80c0c64a90502bf63b500ad163c59e61e175da2465`.

Original signed freeze and NO_GO report in private `crews-tenant-terminal-proof-20261029` remain unchanged. This document records current operator acceptance of already verified evidence under the new ceiling, not independent benchmark evidence or a signed historical override.
