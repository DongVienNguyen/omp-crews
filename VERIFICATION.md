# Verification and operating limits

This file records observed release checks, not a guarantee of production task quality or model equivalence. User instructions: [Vietnamese usage guide](docs/usage.vi.md). Executable owners: [governance](crews/governance.py), [automation](crews/automation.py), [portable rules](crews/portable_rules.py), [host adapter](crews/omp_adapter.py).

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
