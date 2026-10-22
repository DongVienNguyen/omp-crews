# crews-omp

Policy-gated Crews planning, classification and native OMP agents. AgentKit owns workflows; this plugin routes admitted crew roles, not main chat or unrelated native tasks. Plans bind model/effort, scoped tools, exact shell commands and completion receipts.

## Requirements

- OMP with native `ctx.invokeTool`, `before_subagent_spawn` and provider payload hooks. Unsupported hosts refuse crew dispatch. See [verification evidence](VERIFICATION.md) for host limitations.
- Node.js 20+ for CLI/stdio launcher; OMP supplies its Bun extension runtime.
- Python 3.12+ installed explicitly. Setup creates an isolated venv using [locked dependencies](requirements-omp.lock), never system pip or an automatic Python download.
- Provider credentials configured separately in OMP. Default provider is `9router`, model IDs `code-seek`, `code-sol`, `code-astra`. Each configured model must support its selected effort; `Auto` can request low, medium or high. Doctor checks configured aliases/capabilities. Policy contains IDs only, never credentials.

Windows lifecycle has recorded verification. Linux/macOS need equivalent lifecycle validation before claiming support.

## Install and setup

Keep checkout or extracted package at a permanent path:
Install directly from Git with `omp plugin install https://github.com/DongVienNguyen/omp-crews.git --scope user`, then run the installed package's `crews-omp setup` and `doctor` commands. If the package bin is not on PATH, clone the repository to a permanent directory and use the explicit node commands below. A model provider/login must be configured in OMP; the plugin does not create credentials.

```text
omp plugin link <absolute-package-root> --scope user
node <absolute-package-root>/bin/crews-omp.mjs setup --python <Python-executable> --json
node <absolute-package-root>/bin/crews-omp.mjs doctor --json
```

For a local `.tgz`, extract it and link extracted `package/` directory. Direct tarball installation is not supported on the recorded OMP host. Do not also add extension manually to config.yml: duplicate roots can install competing task wrappers. Restart OMP after package changes, especially on Windows.

Setup is explicit and idempotent: it provisions private runtime and owner-marked MCP registration. No install/update runs on startup. `--register-plugin` asks CLI to link package through OMP. `--offline` requires valid existing runtime or dependency wheels via `CREWS_OMP_WHEELHOUSE`; missing dependencies fail visibly.

Shared target options are `--python PATH`, `--agent-dir PATH`, `--state-dir PATH`, `--profile NAME` and `--json`. Use CLI `--help` for current flags. `CREWS_OMP_HOME` and `CREWS_OMP_AGENT_DIR` support isolated state and agent roots; choose same profile/paths for setup, doctor and later lifecycle operations. Do not accidentally share profile credentials/state. Relative OMP `PI_CONFIG_DIR` resolves against home, not current directory.

## Existing installs, upgrades and removal

Legacy extension installs require migration after linking exact package root:

```text
node <package-root>/bin/crews-omp.mjs migrate --dry-run --python <Python-executable> --json
node <package-root>/bin/crews-omp.mjs migrate --python <Python-executable> --json
node <package-root>/bin/crews-omp.mjs doctor --json
```

Migration removes only owner-verified old extension/MCP/agents/skill registrations. Unknown modified files are refused rather than overwritten. `--expected-hashes FILE` accepts explicitly reviewed owned hashes (`{"files":{"absolute-path":"sha256"}}`), not blanket force. State, history and retry counters remain; incomplete runs never auto-replay.

For upgrades, update package assets at linked root, rerun `setup` and `doctor`, then restart OMP. Existing policy and records remain. There is no `upgrade` subcommand.

`uninstall --dry-run --json` previews removal; `uninstall --json` removes owned MCP/native registration transactionally while retaining state/config/history and provider credentials. Failed removal restores registration.

To restore a migration snapshot, inspect `rollback --backup <state>/backups/<snapshot> --dry-run --json`, then repeat without `--dry-run`. Snapshot ownership/profile/hashes and current files are checked; modified content is preserved/refused. Crash-prepared snapshots require explicit recovery. Older snapshots without current manifest schema require reviewed manual restoration. No automatic downgrade, data reset or venv pruning.

`--dry-run` is supported only by `migrate`, `uninstall`, `rollback`; `rollback` requires `--backup DIRECTORY`. Lifecycle implementation and complete option parser live in [CLI](bin/crews-omp.mjs).

## Combo model and effort policy

Three user-facing Combos each select a model ID and `Low`, `Medium`, `High` or `Auto` (default). Model names remain provider IDs; changing them does not rename Combo slots. Different Combos may use same model. See [canonical policy example](examples/policy.json).
In OMP interactive mode, run `/crew combos`: select Small/Medium/Large, enter provider/model, choose Auto/Low/Medium/High, review and confirm. Escape cancels without writing. Empty provider/model entry keeps the current value. The editor checks OMP model/effort resolution before saving. Headless users use the CLI below.

- **Small:** mechanical verification, repeatable tasks, bounded retrieval.
- **Medium:** everyday implementation, long-running agentic work.
- **Large:** difficult review, integration architecture, specialist work.

Each role uses its own need and difficulty, not task-level or sibling classification. `Auto` selects low for difficulty below 1, medium below 2, high otherwise. Explicit effort overrides difficulty for that Combo. Native wire efforts are lowercase. Repair stays in same Combo; escalation moves to next Combo using that Combo's configured effort, or Auto with original role difficulty. Large has no stronger Combo. Escalation requires recorded failure.

### Bounded implementation on Small (0.5.0)

`everyday_implementation` stays its real need but may execute Small when kind is produce, role difficulty <=1.5, scope contains 1–3 explicit files, and `facts` explicitly set targets_fixed/behavior_fixed/scope_bounded/deterministic_check true and behavior_undecided/unknown_cause/consequential_judgment/cross_system/concurrency_sensitive false. Missing facts retain Medium. Supply `bounded_check:{"input":"check.mjs","command":"node check.mjs"}`: checker must exist in inputs outside every writer scope and command must exactly match an admitted command. This checks declared authority/ownership, not semantic correctness of arbitrary checker code. The independent reviewer still owns acceptance. No implicit retry: Small failure requires recorded repair/escalation; target Combo configuration is respected.

`requested_combo` means baseline capability mapping before this optimization; `effective_combo` is the executed Combo. A bounded Medium->Small role retains need everyday_implementation and reports bounded_small=true, including after explicit escalation.

```text
crews-omp combo show --json
crews-omp combo set --provider local-gateway --small-model small-v2 --small-effort Auto --medium-model medium-v2 --medium-effort Low --large-model large-v2 --large-effort High --json
crews-omp combo reset --json
```

Use `node <package-root>/bin/crews-omp.mjs` instead of `crews-omp` when executable is not on PATH. Effort options are case-insensitive. Setting a model without its effort resets that Combo to Auto; untouched Combos retain their settings. Missing policy effort defaults to Auto. Legacy `{provider,models:{haiku,sonnet,opus}}` files remain readable; `combo set` explicitly converts/persists canonical `combos` configuration. `combo reset` writes defaults. Obsolete `policy` command and old model-slot flags are not supported.

Policy changes invalidate old plan bindings, including effort-only changes. Create fresh plans after changes. The semantic teacher follows configured Large model and effort (Auto uses classifier difficulty3, hence high). Provider authentication remains in OMP.

## Classification and preview

- `/crew status`: classifier config/runtime without inference or child.
- `/crew test <canonical-role-JSON>`: classification/effective Combo without plan, ticket or child.
- `/crew history`: project-scoped routing/status without prompts.
- `/crew reload`: validate config and invalidate cached recommendations, not running tickets.
- `/crew report`: persisted project crew counts/usage/coverage/escalations plus current-session main/native-task/crew event counts. `crews-omp report --project <project> --json` returns persisted crew-only data. Session event counts are not task counts; unknown usage is not zero cost.

`crew_preview` exposes same operations headlessly. Python MCP `crew_test` is deterministic only. Facts are tri-state true/false/unknown; absence never means false. Declared need/difficulty takes precedence unless safety facts contradict it. Unknown cause or consequential judgment cannot be mislabeled as cheap lookup. File counts do not establish difficulty. [Routing corpus](examples/routing-corpus.json) covers bilingual deterministic cases; [classification source](crews/classification.py) owns rubric.

Canonical `task` intake contains `intake:{spec,answers,session}`. `spec` uses task plus roles with name/kind/mission/deliverable, scope/commands/acceptance and flat role answers. Only `classification:true` may omit need/difficulty; `divisible` and `specific` remain required. [MCP minimal example](omp_server.py) supplies explicit canonical plan shape. Intake returns references, not execution; dispatch each returned `crew:{run,role,session}` through task. It never invents scope, commands, acceptance or model selectors. Invalid/unresolved plans block ordinary delegation rather than falling back silently.

## Large teacher and verified local learning

Classification order is: explicit valid answers, deterministic facts, active verified local rule, then Large teacher for unresolved answers. The teacher proposes need/difficulty only; execution may still use Small. It does not split arbitrary requests into authorized roles: the orchestrator must supply canonical role scope, commands and acceptance.

`<state>/classifier.json` absent uses `recommend`, Large Combo, timeout30000ms and maxTokens512. This is enabled for unresolved `classification:true` roles; it may incur provider requests. `off` disables teacher calls; `shadow` compares without changing effective answers. Explicit/deterministic answers avoid calls except requested shadow comparison. Existing classifier.json is not overwritten: an old Small model override must be removed or updated to current Large identity before enabling. Large Auto uses high; explicit Combo effort is respected. Strict JSON, safety checks and caller answers remain authoritative.

Declared Medium produce roles at difficulty <=1.5 may be sampled for teacher shadow comparison: classifier.json `mediumShadowPercent` defaults10 and `mediumShadowMax` defaults1 per project/session (range0..100 and0..5). Comparison never replaces declared answers. Preview/off mode does not sample. Sampling consumes bounded teacher resources; set either value0 to disable. The in-memory sampler stops adding samples at256 entries rather than evicting budgets and resampling old calls.

The learner is bundled and requires no extra service/dependency beyond plugin setup. Its default is **shadow per project**: observations and validated candidates can accumulate, but rules cannot replace the teacher until you explicitly enable mode on and activate an eligible rule. Same task family/context/policy must match exactly; this is verified experience reuse, not neural fine-tuning or semantic similarity routing.

### Human feedback and activation

`/crew learning` provides confirmed interactive labeling, mode selection, activation and rollback. The `crew_learning` model tool is read-only. CLI equivalents:

```text
crews-omp learning status --project <project> --json
crews-omp learning observations --project <project> --json
crews-omp learning label --project <project> --id <observation-id> --need bounded_retrieval --difficulty 1 --evidence "Independent check of required capability" --split train --unit-id <unique-task-id> --yes --json
crews-omp learning rules --project <project> --json
crews-omp learning activate --project <project> --id <rule-id> --yes --json
crews-omp learning configure --project <project> --mode on --yes --json
crews-omp learning report --project <project> --json
crews-omp learning rollback --project <project> --id <rule-id> --yes --json
```

For receipt-backed feedback use `/crew learning` -> `Verified Small result`, or list `crews-omp learning feedback_options --project <project> --json` then `crews-omp learning feedback --project <project> --run <run> --role <role> --session <session> --need everyday_implementation --difficulty 1 --evidence "independent acceptance verified" --split train --unit-id <independent-id> --yes --json`. Backend checks completed Small receipt, exact model/effort/provider, current policy and fingerprints, and original nonlearned observation; user must still verify capability/correctness. Listing never creates a label. Existing train/holdout thresholds remain unchanged.

At least **3 independent train units plus 2 disjoint holdout units** must agree before activation. `--split holdout` uses distinct unit IDs; do not label five copies of one check as independent evidence. Only human-reviewed classification labels count. Teacher guesses, `COMPLETE`, provider errors, cancellation and timeout never create correctness labels. Label capability/difficulty, not merely whether a model returned an answer. Cheap labels require explicit negative risk facts; unknown cause/security/consequential judgment cannot be learned into a cheap route.

Candidates are shadowed, not automatically activated. Every tenth active match bypasses classifier cache and asks Large to audit; disagreement, invalid output or failure suspends the rule. Existing explicit answers always win; scope/model/effort admission guards cannot be learned away. Rolled-back/suspended rules do not silently reactivate. Policy/model/prompt/context changes invalidate reuse.

### Privacy, metrics and retention

Learning persists keyed HMAC project/task/context fingerprints, boolean safety facts, numeric labels and bounded metrics in `learning.sqlite`, with local `learning.key`. It does not store raw task, source content, file paths, commands, evidence text or credentials in the learning DB. Ordinary Crews records/transcripts retain their existing brief/evidence behavior; this is not a claim that all plugin storage is secret-free. Teacher request still sends bounded role text through the configured provider.

Capacity is 10000 observations / bounded SQLite pages; full capacity drops new observations visibly rather than training or silently deleting evidence. Reports separate verified-label agreement, errors, observed teacher calls, local calls avoided, tokens and latency with unknown coverage. These counters are not a real-task quality/cost benchmark. `crews-omp learning purge --project <project> --yes --json` explicitly removes that project's learned data. Uninstall/upgrade/reinstall preserve learning state by default; never package state DB/key. Back up sensitive local state separately.

The conservative thresholds and periodic audit are guardrails, not a statistical guarantee. To broaden generalization, collect a representative independent labeled corpus first; no rules are synthesized from one teacher answer.

## Safety and verification

Extension tool checks are not an OS sandbox; read scope is not a secrets boundary. Exact commands may execute mutable project scripts. Check roles should use trusted narrow commands, not producer-controlled code. Receipts prove requested model/effort and native output, not router backend identity. Stale prior-role fingerprints intentionally refuse admission: reconcile current files and create fresh scoped check, never rewrite historical evidence to PASS.

Run owned offline Python suites with provisioned runtime: `check_classification.py`, `check_plan_contract.py`, `check_effort_policy.py`, `check_seek_routing.py`, `check_bridge_launch.py`. [Package scripts](package.json) own Node packaging checks; `npm run test:packaging` uses isolated lifecycle fixtures. See [verification evidence](VERIFICATION.md) for observed results rather than treating documentation as proof of successful execution.

License MIT. Upstream license retained; [NOTICE](NOTICE) records attribution.
