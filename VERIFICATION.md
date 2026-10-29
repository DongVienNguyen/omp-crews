# Verification and operating limits

This file records observed release checks, not a guarantee of production task quality or model equivalence. User instructions: [Vietnamese usage guide](docs/usage.vi.md). Executable owners: [governance](crews/governance.py), [automation](crews/automation.py), [portable rules](crews/portable_rules.py), [host adapter](crews/omp_adapter.py).

## Immutable benchmark repair

- Fixed mutable-checkout execution: benchmark re-execs a private executable snapshot before task freeze. Generated host extension and native bridge are pinned; bridge checks before/finally after dispatch. Host config/model digest, strict overlay and model policy are checked; policy deletion refuses instead of falling back. Both CLI option forms work.
- check_frozen_benchmark.py executes a real worker and bridge. Working checkout edits remain isolated; snapshot/config/overlay/policy edits and deletion refuse; mutation during bridge triggers finally refusal. No credential contents copied to proof. Full32-unit oracle/64manifest validation and selected4-unit/8manifest validation passed inside snapshot runtime.
- Independent closure reviewd70c302351cd4d489922b3561a2bb078 COMPLETE, static scope. Clean8arm real-provider regression finished: candidate4/4strict accepted, baseline3/4, zero binding violations. Baseline tenant writer cancelled at575935ms despite oracle-pass artifact; native delivery proof still missing, evaluator NO_GO retained. [Immutable results](plans/20261028-sdlc-micro-loops/benchmark/immutable-results.md). No old failures relabelled or unseen-holdout claim.

## 0.11.1 enabled SDLC verification

- Explicit operator decision enables fresh sdlc_cost_aware workflows before benchmark qualification. Native crew_workflow prepare/next/status/recheck/recover uses original grants, confirmed mutations and exact returned crew refs. Existing baseline manifests stay pinned; main model/effort/state unchanged.
- Actual native scripted smoke calls crew_workflow prepare and dispatches scout/writer/checker; native metadata source=caller,status=valid for all roles after task.structured enabled. Real provider normal-entry CSV workflow completed writer/checker, host behavior pass. Enabled-path review1326ca8ad7094690998c51588dcfe370, strict-setup review37069e30da674510932a97dbdab2d2ee and final cutover review52f267eb07734cf2aadfcd6e5dc8a934 COMPLETE, static scope only.
- Root cause: native OMP task.structured defaults false and discards caller outputSchema/schemaMode. Setup now enables true inside registration transaction, doctor refuses false, model roles/sibling task keys preserved. Checker brief has one status/verification/criterion_results envelope; no lenient JSON repair. Restart OMP/MCP required.
- Workflow/default/pinned-history, plan schema,27-row routing, quality-only, immutable attempt/repair/recovery/partial ownership, authority, keyless/governance/recipes/learning regression checks passed. Strict native yield smoke asserts source=caller,status=valid for all3roles; invalid/unavailable metadata cannot become COMPLETE. Windows directory-symlink case unavailable.
- Packaging11/11passed in separate bounded selections:10public-interface checks (128.937s) and real lifecycle setup/repeat/relocate/doctor/migration rollback/uninstall/reinstall with disabled-structured repair (595.369s), pinned offline wheelhouse. Previous600s online-index timeouts retained, not PASS. Isolated setup probe confirmed modelRoles, sibling task settings and unrelated config unchanged. Dependency pins unchanged.
- Full reconstructed corpus completed64/64arms:23workflow-complete/9blocked each arm; strict accepted0/32each because frozen source/policy binding changed during implementation plus missing/cancelled evidence. Evaluator quality/latency NO_GO, not_evaluated money.119immutable attempts (Small68/Medium35/Large16),16cancelled and1schema-error failed calls. Host task.structured changed mid-run; mixed-condition diagnostic evidence, not clean noninferiority proof. [Detailed results](plans/20261028-sdlc-micro-loops/benchmark/results.md). Enablement authorization does not rewrite verdicts.

## 0.11.0 SDLC verification

- Permanent checkout contract suites passed: typed routing27rows/27boundaries, workflow ordering, source scope, two-child correlation, immutable attempts, criterion strikes, successor/partial ownership, two repairs with independent rechecks, dead reservation/orphan recovery, signed quality-only and monetary evidence boundaries.
- Final package lifecycle11/11passed,0failed/skipped (98.429s). Actual native staged workflow and overlapping Small children passed with scripted provider; focused real-provider scout→writer→host executable checker completed after strict output-envelope correction. Fixture signatures/prices are not provider quality evidence.
- User explicitly removed monetary/cost acceptance. Signed quality_only keeps quality, per-unit nonregression, host latency, frozen model/policy/environment and original behavior proof; money remains not_evaluated. No savings claim.
- Main runtime and separate sdlc-canary profile provisioned/linked at0.11.0; doctor ready with all Combo aliases/efforts. Main model/Combo policy unchanged; state preserved. Canary real native startup returned CANARY_READY, exit0. Startup with --no-tools correctly lacked delegation API; a broader earlier startup timed out. Restart OMP/MCP to load new extension.
- Reconstructed32-unit corpus/64canonical manifests oracle-validated. V4 real-provider evaluation stopped at an arm boundary after confirmed regression and independent oracle findings:12terminal arms, baseline6accepted/candidate5accepted, quality/latency NO_GO; unstarted pairs remain missing. Candidate transform-csv checker lacked strict output (schema_error); never counted pass despite host artifact behavior. No broad default promotion; installed code keeps baseline default and SDLC opt-in.
- Earlier provider failures retained, not replayed/relabelled. Oracle audit found incidental top-k AST restriction and unobservable lock requirement: final corpus uses tracemalloc retention boundary and concurrent integer snapshots. Counterexample smoke rejects full materialization and accepts bounded heap with sorted(heap); final32unit validation passes. Revised corpus is not retroactively applied to frozen V4 results. No production-equivalence or monetary claim.
- Directory symlink OS case skipped where Windows privilege unavailable. Existing pydantic-settings lifespan warning remains. No credentials, state databases, provider logs or ephemeral signing keys belong in Git.

## 0.10.0 release evidence

Recorded on Windows with Python 3.12, Node.js 24 and OMP native task support:

- Package lifecycle suite: **11 passed, 0 failed, 0 skipped**. Covers isolated setup/repeat/relocate/doctor, native plugin registration, migration transaction rollback, uninstall/reinstall, policy/config preservation and storage interfaces.
- Keyless lifecycle checks: setup without signing keys; authenticated typed policy application; lease/quota renewal; stable project identity; sticky disable; copied account/state identity refusal; stale tickets and fresh inactive plans refused; caller-supplied governance markers refused; expired unfinished governance receives a new generation.
- Denied or malformed governance results remain paused even when the recorded plan expires before application. Routing snapshot race checks reject policy changes between role selection and plan persistence.
- Portable rule checks: policy and recipe guidance round-trip through the review queue; immutable host-side export snapshot, project/revision and strict integer version checks; duplicate JSON keys, nonfinite input, extra authority, foreign and stale packets refused. Recipe edits create a new candidate with no copied training/holdout evidence and suspend the superseded version.
- Existing recipes, outcomes, classification, effort, plan contracts and storage checks passed during implementation. Direct signed advanced administration continues to reject unsigned/tampered/replayed requests.
- Actual CLI export produced a raw `crews-rule` packet; importing an edited proposal queued review without changing policy first. Duplicate pasted JSON keys were rejected.
- Actual native Large/high reviews returned typed policy decisions with matching native/wire evidence and host-authenticated completion. Host applied initial governance and an externally optimized policy proposal. These runs exercised real model judgment, unlike synthetic fixture receipts.
- Independent read-only Large review found no remaining concrete blocker in the inspected keyless governance and portable-rule paths after corrections. Earlier failed reviews were not counted as successful evidence.
- Publication checkout recheck passed: keyless, portable rules, public plan contracts, actual OMP local-provider bounded-write lifecycle, and packaging **11/11** (275.715 seconds). All local documentation links resolved; eleven PowerShell example blocks parsed successfully without executing install/destructive commands. Package dry-run included the usage guide and contained no local state/key/log payload.

The checked-in `check_keyless.py`, `check_portable_rules.py`, `check_automation.py` and related checks use isolated fixture model receipts to test host contracts. They do **not** prove that a real model judged every fixture correctly. Real native smoke evidence is a separate observation.

## Reproducing focused checks

Use the provisioned runtime printed by `setup`; do not install test dependencies into system Python:

```text
<runtime-python> -B check_keyless.py
<runtime-python> -B check_portable_rules.py
<runtime-python> -B check_automation.py
<runtime-python> -B check_recipes.py
<runtime-python> -B check_outcomes.py
<runtime-python> -B check_plan_contract.py
<runtime-python> -B check_classification.py
<runtime-python> -B check_effort_policy.py
<runtime-python> -B check_storage.py
node check_lifecycle.mjs --bounded-write
npm run test:packaging
```

`check_lifecycle.mjs` launches the real OMP/native task path with an isolated local scripted provider. It checks admission, model/effort receipts, read/write behavior and strict completion; it does not measure production provider quality. Packaging fixtures create temporary runtimes and can take longer than focused checks.

## Limits

- Local-account trust is deliberate. Crews extension checks are not an OS sandbox and do not protect against arbitrary code that can alter the same user's state or package files. No signing private key is needed for default setup.
- Main chat model and unrelated native task paths are not remapped by Crews. Role routing is not proof of execution until matching receipts exist.
- The current host requires a restart after package/schema changes. Incomplete/failed work is not silently replayed; policy or artifact drift requires a fresh authorized plan.
- The interactive `/crew rules` editor is integrated but has not received direct visual TUI verification in the recorded release run. Backend and actual CLI round-trip were exercised.
- Linux/macOS lifecycle parity has not been demonstrated by the recorded Windows checks.
- No claim of production noninferiority, absolute correctness, monetary savings, or backend model identity beyond configured provider/native receipts. Missing pricing/accounting stays unknown; zero provider metadata is not verified free usage.
- Lease renewal does not itself renew expired recipe validity or revive suspended/rolled-back recipes. Fresh evidence and the relevant review gates still apply.
- No background worker runs while OMP is closed. Review resumes through the host when OMP is used again.

## Prior compatibility

The release retains project-scoped exact classification learning separately from recipe learning; human capability labels are not created from model self-COMPLETE. Admission/results remain SQLite-backed; historical counters and records are preserved. Existing signed accounting/evaluation and direct advanced recipe administration remain separate from normal keyless setup. See the usage guide before migrating, cleaning storage or copying data to another machine.
