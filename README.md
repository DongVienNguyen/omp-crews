# crews-omp

Policy-gated Crews planning, classification and native OMP agents. AgentKit owns workflows; this plugin routes admitted crew roles, not main chat or unrelated native tasks. Plans bind model/effort, scoped tools, exact shell commands and completion receipts.

**[Hướng dẫn sử dụng đầy đủ bằng tiếng Việt](docs/usage.vi.md)** — cài từ Git, cấu hình Combo, vận hành không key, gia hạn tự động, copy/dán rule cho AI ngoài, cập nhật và xử lý lỗi.

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

Setup enables local-account Large policy governance by default. No private signing key, signed grant file or key migration is needed on a new machine/user installation. Provider login remains required. Automatic review can consume Large provider tokens. Local policy trusts the OS account running OMP, not cryptographic human identity; arbitrary same-user code that can modify state/code is outside this boundary.

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

`requested_combo` means baseline capability mapping before this optimization; `effective_combo` is the latest selected Combo, not execution proof. A bounded Medium->Small role retains need everyday_implementation and reports bounded_small=true, including after explicit escalation. Native/wire evidence is required to claim execution.

### Routine implementation on Small

For fixed local behavior, a produce role with need `everyday_implementation`, difficulty <=1.0 and 1–3 explicit files may use `routine_check:"check-role-name"` instead of a pre-existing deterministic checker. Explicit facts targets_fixed/behavior_fixed/scope_bounded must be true; behavior_undecided/unknown_cause/consequential_judgment/cross_system/concurrency_sensitive must be false. Missing facts retain Medium. The linked read-only check must carry every original acceptance criterion verbatim, declare every produced artifact in inputs, and actually dispatch in a later wave; invalid checker authority rejects the plan. Declare task needs_verifier so the existing budget includes this checker.

The checker independently validates behavior and any producer-written tests; it receives no producer conclusions. Executable checker scripts must exist in its inputs outside all writer scopes. Inline evaluation, shell substitution and module execution are not admitted by this optimization. This is an authority guard, not a sandbox or a proof that arbitrary commands are safe. Each checker still needs narrowly reviewed commands. A read-only inspection checker may have no shell authority.

`small_route` is bounded, routine or null; `small_blockers` explains each failed eligibility gate. `bounded_small` retains its historical bounded-route meaning. Baseline requested_combo and initial small_route survive escalation; effective_combo records the latest admitted selection, not proof of execution. Routing policy changes require fresh plans, even when model bindings are unchanged. Single-role preview without sibling context cannot establish routine eligibility.

Intake warnings flag declared implementation/review needs when explicit facts instead describe a bounded lookup or deterministic check; declarations are not silently rewritten. Classify each deliverable, not the hardest part of its parent project. No Small quota, automatic safety facts or learned downgrade.

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
- Reports separate baseline/effective Combo, latest statuses, Small eligibility blockers and native-model evidence coverage. Counts include planned and archived roles and are not provider attempt counts; unknown archived Combo remains unknown.

`crew_preview` exposes same operations headlessly. Python MCP `crew_test` is deterministic only. Facts are tri-state true/false/unknown; absence never means false. Declared need/difficulty takes precedence unless safety facts contradict it. Unknown cause or consequential judgment cannot be mislabeled as cheap lookup. File counts do not establish difficulty. [Routing corpus](examples/routing-corpus.json) covers bilingual deterministic cases; [classification source](crews/classification.py) owns rubric.

Canonical `task` intake contains `intake:{spec,answers,session}`. `spec` uses task plus roles with name/kind/mission/deliverable, scope/commands/acceptance and flat role answers. Only `classification:true` may omit need/difficulty; `divisible` and `specific` remain required. [MCP minimal example](omp_server.py) supplies explicit canonical plan shape. Intake returns references, not execution; dispatch each returned `crew:{run,role,session}` through task. It never invents scope, commands, acceptance or model selectors. Invalid/unresolved plans block ordinary delegation rather than falling back silently.

## Verified outcomes and adaptive recipes

Execution and behavior are separate. A provider/tool/schema/cancel failure does not become a behavioral negative. Unknown usage/pricing stays unknown. Reports include independent behavior, delivery outcomes, producer claim contradictions and verified Small counts. Legacy results remain unchanged; new outcome metadata is versioned.

For executable verification, a check role declares `checker_profile:{input,command,version}` and `verify_targets:[producer-name]`. It must read every producer artifact and carry every acceptance criterion. Profile script is existing, project-contained and outside every writer scope; command is exact admitted Python/Node/Bun script invocation. The host runs that immutable profile and records actual exit, script/artifact hashes and machine JSON output. Script stdout must be one JSON object containing `criterion_results:[{criterion:exact_original_text,status:"pass"|"fail"}]` in original order. Model text or caller exit-code claims are not execution proof. Scripts must test actual behavior and boundary/error semantics; a signed profile approval does not prove a weak checker meaningful.

`crew_shape` validates a caller-supplied role proposal inside explicit read/write/command authority and requires a cross-cutting invariant checker. It returns a proposal, not admission; it never invents scope or changes declared difficulty. Resolve open decisions with an appropriately classified role before bounded Small edits. `crew_recipes`, `/crew recipes` and `crews-omp recipes` expose the recipe lifecycle. `crew_recipe_preview` is read-only and does not reserve hits or create labels.

Recipes use structured `recipe_features` (domain/language/operation/invariant/dependency_shape), immutable version, cue/lesson/evidence/negative examples, applicability/exclusions, independent profile and pinned model binding. Matching ignores wording/target names but revalidates current safety facts, scope, checker, invariant, model revision and profile hashes. `recipe_confirmed:true` reserves a hit only after an operator-approved active recipe and mode on; otherwise default shadow/abstain. Recipe guidance is untrusted context, never new authority. Explicit `model_revision` is required for effective use; hosted-provider revision changes hidden behind an unchanged identifier cannot be detected automatically.

### Advanced direct signed administration

Direct recipe administration outside the automatic Large workflow uses operator-signed exact requests; `--yes` alone is insufficient for that advanced interface. Normal installation and automatic governance do not require these keys. Never ask an agent to read/generate/carry a real private key or replace operator-public.pem. Existing signed artifacts remain project/request-bound.

Default governance uses local-account trust and native role tool authority. Crews is not an OS sandbox: arbitrary same-user processes able to replace state/code are outside protection. Use OS-separated accounts/ACLs or a container for hostile arbitrary code. Receipt checks prevent model text from becoming machine proof; they do not claim same-user root resistance.

Automatic evidence uses host-authenticated non-learned verified snapshots and deterministic source-hash train/holdout split. Initial supported defaults are >=59independent passing units, >=5holdout and95% failure bound<=5%; Large can adjust supported typed policy, including disabling promotion or using shadow mode when evidence is weak. Learned outputs audit only, never self-train. Failures/unknown suspend and preserve history; correlated variants are not independent production evidence.

### Keyless automatic Large policy governance

Normal installation uses local policy rather than manual grant signing. Setup creates installation identity; first project use queues independent Large aggregate review. Only typed policy returned by host-authenticated native Large completion can renew the execution lease or change supported Crews settings. Main model remains unchanged. Large may adjust role-to-Combo routing, recipe mode/auto-evidence, supported promotion thresholds, difficulty ceiling, audit cadence and review budget/lease. It cannot modify verifier code, file/command authority, credentials, historical receipts or task acceptance.

Lease expiry or exhausted per-lease review budget schedules governance review, not permanent manual lockout. Successful review renews within the supported policy schema; denied/malformed review pauses instead of silently continuing. No user reminder/calendar or old-machine private key is needed. New installations create local identity; copied recipe evidence is not automatically execution authority. Explicit disable remains sticky across setup/restart; Large cannot undo it.

```text
crews-omp automation status --project PATH --json
crews-omp automation disable --project PATH --yes --json
crews-omp automation enable --project PATH --yes --json
```

Original task must still supply safe facts, explicit artifacts, model revision and independent immutable checker. Role classification is per-role, not whole-project. Routing overrides cannot authorize unsafe Small execution. Unknown/failing checker suspends; learned runs do not train themselves. Native receipts and actual checker behavior remain evidence, never model self-COMPLETE.

OMP drains stored review jobs after task completion. Startup pending queue directs `task {automation:true}`; host chooses jobs. There is no worker while OMP is closed. Admission/epoch/replay guards retain interrupted/failed history; no silent duplicate execution. Direct signed recipe/accounting/evaluation administration remains a separate advanced interface, not installation prerequisite. If using that signer, `PRIVATE_KEY` must name a new file, not a directory; never supply signing key contents to an agent.

### Copy rules to an external AI and paste optimized proposals

Use `/crew rules`: export policy or a recipe ID, copy JSON from editor, ask external AI to edit only `proposal`, then choose import and paste returned JSON. CLI equivalent for policy:

```powershell
$src = "$env:USERPROFILE\.local\share\crews-omp\source"
$project = "C:\path\to\project"
node "$src\bin\crews-omp.mjs" automation export --project "$project" --json | Set-Clipboard
# Paste clipboard into external AI. Save returned crews-rule JSON as optimized-rule.json.
node "$src\bin\crews-omp.mjs" automation import --project "$project" --request optimized-rule.json --yes --json
```

Packet `format:crews-rule, version:1` includes edit instructions/schema, immutable export ID/base revision and editable proposal. Policy proposal is full supported policy; recipe proposal edits only cue/lesson/steps/negative examples and includes invariant constraints. It exports no keys, receipts, raw source/task or execution authority; review your own guidance text for sensitive content before sharing. External AI must preserve every field except proposal and return one JSON object (single fenced json block accepted).

Import also accepts the exact UI export result envelope `{"changed":false,"packet":{...}}`; edit only `packet.proposal` in that form. The inner packet keeps integer `version:1`. Envelope normalization does not bypass packet revision, schema or Large review checks.

Import queues independent Large review; paste never directly activates. Stale base, foreign project/export, changed immutable context, extra authority, duplicate JSON keys or nonfinite values refuse. Export fresh packet if policy/recipe changed. Repeated identical paste deduplicates. Approved recipe edits create new immutable candidate version with no inherited training/active state and suspend superseded version. Missing original reviewed recipe authority refuses export rather than inventing context. Legacy exact classification rules and raw agent prompts are not editable through this packet. On another machine export a fresh local packet, transfer optimized proposal only, then review there.



`probe` consumes fresh paired run references, keeps baseline on ambiguity/regression/missing accounting and never grants routing authority. `crew_account` or CLI `account --request SIGNED_JSON --project PATH --yes` records independently attested complete-run accounting (producer/checker/classifier/main/repairs and pricing provenance). Zero provider metadata is not verified pricing. Probe selection requires that complete accounting; no cost-saving claim without it.

`crew_recover` or CLI `recover --request JSON --project PATH --yes` reconciles an admitted dispatch only after the recorded host PID is proven dead. Unknown/live ownership refuses. It atomically marks interrupted/unknown behavior and revokes ephemeral tickets; it never replays or fabricates COMPLETE. Retry/escalation counters remain intact. Older admissions without owner metadata need explicit investigation, not guessed cleanup.

```text
crews-omp recipes status --project PATH --json
crews-omp recipes register --project PATH --request SIGNED_REQUEST.json --yes --json
crews-omp recipes evidence --project PATH --request SIGNED_RUN_REFERENCE.json --yes --json
crews-omp recipes activate --project PATH --request SIGNED_REQUEST.json --yes --json
crews-omp recipes configure --project PATH --request SIGNED_REQUEST.json --yes --json
```

No recipe is auto-registered/activated by installation; no old pilot label is imported. Exact user-labelled learning remains separate and unchanged. New versioned recipe tables share learning.sqlite; receipt/evidence-backed runs remain retention-protected. Main model and ordinary native tasks are unchanged. Use fresh OMP/MCP processes after package cutover; existing tickets never silently change recipe/model/policy.

`crew_evaluate` freezes an operator-signed unit manifest before runs: source groups cannot cross train/holdout, before/acceptance hashes bind each unit, and results must match fresh authoritative paired evidence. It reports per-family behavior and delivery, abstention from persisted policy decisions (not caller claims), complete-run cost, P95 and missing coverage. Any ambiguity/regression/missing accounting retains baseline; GO is never forced. Reusing old pilot outcomes as a newly frozen holdout is refused by timestamps.

`crew_runner` prepare/status persists a unique run-slot reservation before planning. Existing slot/spec/session mismatch refuses; restart exposes only a still-planned role, never replays admitted/failed/completed work or resets artifacts. A crash between reservation and run-link returns an explicit recovery blocker rather than creating another plan. `crew_storage` provides status, dry-run cleanup, confirmed destructive cleanup/compact, using the same retention engine as CLI.

Recipes expire after30days by default (operator may choose1..90days) and retain predecessor rollback provenance; newest invalid/rolled-back version never silently falls back to an older recipe. Existing exact learning privacy remains HMAC-based; recipe lessons are intentionally project-local operator-approved text and must not contain secrets. Audit events and recipe evidence persist for traceability, not model instructions.

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

Exact classification learning persists keyed HMAC project/task/context fingerprints, safety facts, numeric labels and bounded metrics, not raw task/source/credentials. Recipe and automation tables in the same learning.sqlite also retain reviewed guidance, scoped role context and evidence references; portable-rule export stores the original packet/context for safe re-import. Treat the database and normal Crews records/transcripts as private project data. Teacher/governance requests send bounded task or aggregate context through the configured provider.

Capacity is 10000 observations / bounded SQLite pages; full capacity drops new observations visibly rather than training or silently deleting evidence. Reports separate verified-label agreement, errors, observed teacher calls, local calls avoided, tokens and latency with unknown coverage. These counters are not a real-task quality/cost benchmark. `crews-omp learning purge --project <project> --yes --json` explicitly removes that project's learned data. Uninstall/upgrade/reinstall preserve learning state by default; never package state DB/key. Back up sensitive local state separately.

The conservative thresholds and periodic audit are guardrails, not a statistical guarantee. To broaden generalization, collect a representative independent labeled corpus first; no rules are synthesized from one teacher answer.

## Compact storage (0.6.0)

SQLite is the source of truth for new admissions, wire receipts and role results. New runs do not create ticket/wire JSON files. Completed results are not duplicated as records unless a later wave needs the upstream record-path handoff. Legacy JSON tickets remain readable only while valid/current, then retention removes owned expired copies.

```text
crews-omp storage status --json
crews-omp storage cleanup --dry-run --json
crews-omp storage cleanup --yes --json
crews-omp storage compact --yes --json
```

Cleanup without --yes is a preview; --yes and --dry-run conflict. Status/preview do not create state or mutate SQLite/WAL. They report busy rather than read an uncheckpointed WAL unsafely. Retry after workers/readers finish. Compact requires no live admission/legacy ticket or recently admitted work, uses exclusive SQLite locking, checks WAL checkpoint results and reports actual reclaimed bytes. It never runs automatically while a task is executing.

Optional active-state `storage.json`:

```json
{"payload_days":7,"summary_days":90,"max_runs":1000,"auto_cleanup":true}
```

Full expired run payloads older than7days become minimal per-role status/Combo/model/effort/usage/attempt summaries; summaries retain90days and at most1000runs. Live admissions, runs younger24h and runs backing labeled observations/candidate or active learned rules remain full. Protected data may exceed the limit; it is not silently evicted. Archived summaries remain visible in history/report but cannot dispatch, repair or become verified feedback without original evidence. Unknown fields/retention outside safe ranges refuse cleanup.

Legacy tickets/wire expire after their own deadline plus1h grace. Owned materialized records need run age48h and file age24h, no live protection. Symlinks, unexpected filenames and paths outside the owned subtree are preserved/reported, not followed. Cleanup rechecks under a write transaction and unlinks only after SQL commit. File failures are visible; no learning DB/key, credentials, policy, runtime, rollback backup or venv is removed.

New plan creation triggers at most one cleanup attempt per24h when auto_cleanup true; no background watcher or model call. Disable it in storage.json for manual-only maintenance. Run explicit compact after meaningful pruning, not per tool call. SQLite may keep free pages until compact: file size alone is not active data size. Runtime venvs and migration snapshots are separate retained installation assets, not disposable JSON logs; old runtime deletion is not automatic while sessions may still use them.

Before first real cleanup keep a snapshot. Commands target active profile/state, use --state-dir for an isolated preview. Learning retention and purge remain separate and explicit. Current-state integrity and active guards are verified before reclaim; no old run becomes executable because a ticket row was removed.

## Enabled SDLC workflows

`crew_runner` accepts `workflow_prepare`, `workflow_status`, `workflow_next`, `workflow_recheck`, and `workflow_recover`. CLI: `crews-omp workflow prepare|status|next|recheck|recover|attempts|evaluation --project PATH --request FILE [--yes]`. Prepare/next/recheck/recover require `--yes`; evaluation freeze/attest still require operator signatures. No new scheduler or automatic provider benchmark runs.

Native OMP `crew_workflow` accepts `{request:{operation:"prepare"|"status"|"next"|"recheck"|"recover",slot,session,...}}`; mutating operations require `confirmed:true`. It reuses the same runner and returns exact `task {crew:...}` references. Startup guidance selects this path for multi-stage Crews coding; one-step work retains direct canonical intake. Ordinary native tasks and main model are not silently remapped.

For a wholly unexecuted workflow frozen by policy renewal, `workflow_recover` accepts explicit `snapshot:{old_policy,new_policy,old_sources,new_sources}` digests with `confirmed:true`. Compare-and-swap rejects stale values, changed model bindings, different installation, any admission/execution/retry history, and nodes outside pending/planned. Routing-code version may refresh only when every existing role recomputes to its original Combo/model/effort. It refreshes metadata on the same run IDs, retains original authority/criteria and all counters, and records old/new snapshot digests. It does not replay completed work or repair failed roles. Dead-reservation recovery remains unchanged. Run `check_workflow_snapshot_recovery.py` for snapshot, source acknowledgment, identity/counter preservation and history-refusal checks.

Setup enables OMP `task.structured:true` transactionally; doctor refuses a disabled setting. Native task otherwise ignores caller `outputSchema/schemaMode` and returns free text. Crews keeps independent host checker receipts even with valid structured output. Setup preserves sibling task settings, model roles and provider configuration; restart OMP after setup. This host setting also makes ordinary native task structured fields available, but does not remap their models.

Prepare request contains `slot`, `session`, optional `profile` (`sdlc_cost_aware` default; explicit `baseline` opts out for a fresh workflow), and `workflow: {task, authority:{read,write,commands}, invariants, max_calls, nodes}`. Existing slots keep their pinned profile when omitted. Each node has `{id,stage,depends_on,roles,answers}` with existing canonical roles/task answers. Stage does not select Combo. Dependencies allow same-kind stages; unordered overlapping readers/writers are refused. Returned `next` contains at most two admitted `task {crew:...}` references; caller dispatches them explicitly.

Research `context_request:true` returns an 8KiB/32-reference source-hashed packet. Observations, inferences and unresolved items stay distinct. `needs_more_context:true` forwards a bounded reread request, never a completeness claim; downstream reads only its original grants. Checkers do not receive producer conclusions. Workflow read/grep/glob paths are checked against declared inputs/read_scope/write_scope, including resolved targets. This is not an OS sandbox; explicitly admitted commands remain trusted code.

After independent failure, explicitly repair/escalate producer through existing API. Descendant verdicts are invalidated. Use `workflow_recheck` with `node` after repaired dependencies complete: it consumes workflow call budget, not producer repair quota. Two repairs/four escalations remain shared workflow caps; two independently failed Medium repairs of the same unresolved criterion stop Medium. Name, answer-key or list-order changes do not reset evidence. Attempts are append-only; provider/schema/cancelled failures are not behavioral strikes.

Dead reservation recovery requires explicit `workflow_recover` with node and, if canonical plan already exists, its `run`. Live owners and already executed orphan runs refuse recovery. No automatic replay. Initial snapshots, immutable sources, artifact ownership and policy/environment bindings remain frozen. Directory fingerprints include membership/content; legitimate successor writes supersede earlier output hashes.

`workflow evaluation` request wraps `{request:{operation:"freeze"|"evidence"|"attest"|"report",...}}`. SDLC freeze signs `units`, `arms` and gates. Arms bind baseline/candidate profiles, model policy, routing policy and environment; unit hashes bind initial writable contents as well as sources. `evidence` returns workflow evidence hash; `attest` signs full components (`main`, `governance`, `classifier`, `scout`, `architecture`, `producer`, `checker`, `repairs`, `context`), latency, price provenance and coverage. Report uses workflow refs, not caller scores. Failed task spend stays in cost-per-accepted numerator. Missing corpus/pricing/receipts means `NO_GO`; paired pass-to-fail cannot cancel against another task's improvement. Portable rule exports pin this contract and accept edits only under `proposal`.

Operator explicitly enabled SDLC before benchmark qualification. This is user authorization, not a benchmark PASS or safety exemption. Signed `evaluation_mode:"quality_only"` gates independent quality and host-ledger latency without prices/accounting attestations; `money_status:"not_evaluated"`, `cost_gate:null`. Omitted mode retains monetary gates. Profile selection never changes main model or Combo effort. Provider benchmark exercises reconstructed tasks, not production-equivalence or savings.

Benchmark execution uses [runner.py](plans/20261028-sdlc-micro-loops/benchmark/runner.py) and [frozen_runtime.py](plans/20261028-sdlc-micro-loops/benchmark/frozen_runtime.py): reserve a fresh output directory, copy executable inputs to private runtime, and re-exec all extension/bridge/evaluator code there before freezing tasks. Source, generated host extension, strict native overlay, host config/model digests and normalized policy are pinned; drift or missing policy refuses before/after bridges and arms. Credentials are not copied or printed. `--units ID...` selects previously seen regression exercises, never a new unseen holdout. No implicit retry/replay or deadline increase. Full old evaluation stays unchanged.

## Safety and verification

Extension tool checks are not an OS sandbox; read scope is not a secrets boundary. Exact commands may execute mutable project scripts. Check roles should use trusted narrow commands, not producer-controlled code. Receipts prove requested model/effort and native output, not router backend identity. Stale prior-role fingerprints intentionally refuse admission: reconcile current files and create fresh scoped check, never rewrite historical evidence to PASS.

Run owned offline Python suites with provisioned runtime: `check_classification.py`, `check_plan_contract.py`, `check_effort_policy.py`, `check_seek_routing.py`, `check_bridge_launch.py`. [Package scripts](package.json) own Node packaging checks; `npm run test:packaging` uses isolated lifecycle fixtures. See [verification evidence](VERIFICATION.md) for observed results rather than treating documentation as proof of successful execution.

License MIT. Upstream license retained; [NOTICE](NOTICE) records attribution.
