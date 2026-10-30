# Native acceptance and canary decision — 2026-10-29

## Decision

Routing/proof implementation accepted for conservative cutover. Learned frontier rollout **NO_GO** for measured one-unit canary: both arms passed original independent behavior, but Small trial workflow latency exceeded the existing1.20ratio gate. No recipe activation, no automatic trial mode, no live policy remap, no monetary savings claim.

## Retained evidence

Real provider output, canonical SQLite state and frozen runtime snapshot were retained locally outside the published package; machine-specific paths withheld. Hash comparison found no drift in adapter, workflow outcomes, trial, recipes, automation, evaluator, extension or MCP server against final implementation before cutover; later edits only CLI help/docs/tests unless recorded otherwise.

- Baseline workflow `28a7c76d3d04430da60c47b76def2c54`: Medium writer `9router/code-sol:medium`, independent Small checker `9router/code-seek:medium`.
- Trial workflow `ac71276c901b4835be45499d9e3b65a5`: signed isolated Small writer and independent Small checker, both `9router/code-seek:medium`.
- All four actual native attempts exit0, COMPLETE, matching wire/native model+effort and host_authenticated=true. Both checker host executable profiles pass original integer mapping.
- Trial producer run `3f65e41775b44be9802a0afa4df76311`, attempt3; checker run `e1943e7103a44defb23c66d28b37af28`, attempt4. Canonical reference version2; verified=true, behavior=pass, learned=false. Trial settlement pass; activated=false, label_created=false.
- `fixture-revision` is explicitly test-only operator deployment identity, not provider backend revision; ephemeral test signer/trust lives only in disposable state. Real account/private signing keys were not accessed.

| Observed metric | Baseline | Small trial |
|---|---:|---:|
| Native child attempts |2|2|
| Input+output tokens, excluding separately reported cache reads |46775|25400|
| Cache read tokens |34560|48512|
| Host workflow creation to final immutable attempt |124191.198ms|162387.955ms|
| Sum child native durations |64377.898ms|105854.610ms|
| Independent accepted behavior |pass|pass|

Latency ratio1.307564 exceeds1.20. Token reduction45.70% is observed input+output metric only, not price or normalized model workload. One unit is not statistical quality proof. No objective was retroactively frozen and this descriptive canary is **not** an authenticated signed capability-comparison GO. Signed comparison acceptance/rejection is exercised separately with isolated fixtures. More Small calls alone are not success.

## Failure history retained

Two earlier baseline native writers timed out at344631ms and321861ms before terminal completion. Their logs/state remain unchanged at `crews-small-learning-native-1793248799344222800` and `crews-small-learning-native-1793251678256209000`. The successful run changed harness context only (`--no-context-files --no-skills --no-rules`); model, effort and360sdeadline unchanged. This proves isolated capability, not general production reliability. No failed attempt was replayed or rewritten.

## Independent review and local checks

Changed-contract review `e5d62887581e40c7b0224d48d575e4a3`, role `review-live-ticket-fixes`: static COMPLETE/C1pass, authenticated `9router/code-astra:high` native and `code-astra/high` wire. Scope: active trial tickets, owner liveness, unverifiable audit suspension, content holdout and cross-database serialization. Static verdict is not host behavioral proof. Public evidence/capture/automatic finish/comparison freeze share process+file lock through commit; cross-process exclusion regression passed. Cancellation blocks subsequent tools, not already-running OS code; scopes are not OS sandbox.

Focused Python routing/workflow/learning/recipe/automation/trial/comparison/storage/evaluation suites passed. Node classifier/editor/dispatch/write-scope checks passed. Packaging11/11; frozen actual OMP local-scripted workflow PASS85.40s. Fixture receipts remain fixture evidence, never production training/holdout or fabricated59successes.

## Rollback

Keep existing Combo/provider/model/effort, force floors and project modes unchanged. No learned family active without original promotion thresholds. Roll back installed code from newest retained pre-cutover backup if installed smoke fails; do not rewrite attempts, consent, labels or policy history. Restart OMP after cutover on Windows. Broader frontier rollout requires a newly approved supported-family experiment and independent evidence; current default remains baseline.

## Installed cutover

Conservative cutover completed at the active installed checkout with42changed source/test/docs files and no conflict against original admitted source snapshot. Installed signed trial/comparison checks and CLI opportunity report passed; `doctor --json` returned ready/problems:[] and all configured Combo effort aliases supported. Plan validate valid:true; updated skill quick_validate valid. Package dry-run includes linked plan/native evidence. Additional installed package evidence inclusion change only, no provider/runtime/policy mutation.

Pre-cutover backups retained locally outside Git. At this acceptance snapshot no commit/push/publish had occurred. Restart OMP for new extension/schema; live learned frontier remains baseline/NO_GO. Later publication does not change that canary verdict.
