# Evidence — read-only audit 2026-10-29

## Population and limits

Audited active installed checkout and its local state, with installation paths withheld from publication. Reads used SQLite mode=ro; probes used disposable projects/state. No product/policy/label/evidence mutation, model change, real task replay or provider benchmark. Two Small source scouts returned PARTIAL; neither treated as complete audit/review. Findings below checked directly in source and executable probes.

Latest-role history is NOT immutable attempt population, not production-only, not equivalent to native tasks/main chat, and includes development/review/fixtures.4legacy cells lacked typed routing metadata and were excluded. Counts are bounded audit snapshot, not live dashboard.

| Typed latest roles | Small | Medium | Large |
|---|---:|---:|---:|
| completed |28|43|303|
| failed |41|77|257|
| planned |10|11|62|
| admitted |0|3|4|
| produce/integrate completed subset |5|34|35|

Only30immutable attempts in main state at collection: Small5,Medium2,Large23; ledger introduced after much history. Isolated benchmarks use other state and are excluded.463check/difficult_review roles routed Large in history; they include semantic reviews, not automatically all governance.18roles marked governance, all Large. Cannot infer overall model utilization from main UI color or role counts.

## Actual learning funnel

-137observations, all source=declared:27completed,44failed,5cancelled,2provider_error,59ok/without task completion update.0labels,0exact rules,0recipes,0recipe evidence,0captures.
-18automation jobs:17applied,1blocked; every job operation=govern, none register/activate/audit recipe.
-All205produce/integrate cells lack model_revision/recipe_id/recipe evidence and matching automation_context recipe_features/routine_check/recipe_profile.3have workflow_id.26/28completed Small cells lack exact-classification observation linkage; all5completed Small producers lack it.
-Exact config table empty: learning._mode defaults shadow. Audited application project recipe configs were shadow, auto_promotion null, auto_evidence true. Release and isolated projects were on, but no recipe/evidence existed there either. Modes project-scoped; enabling SDLC does not turn learning on.
-Current Temp grant mapping contains everyday_implementation:Medium; audit_every1. Other project defaults differ. Governance max_difficulty<=1. No policy was changed during audit.

## Findings with executable owner

### F1 — capability route overwritten by need baseline

`omp_adapter.py:139-151`: choose Small for eligible bounded/routine first, then routing_policy[need] can reset combo Medium/Large. `remap_seat:167-171` still reports routine/bounded reason even when effective Medium. Probe: same safe routine producer + original independent checker, no mapping=Small; mapping everyday_implementation:Medium=Medium while reason remains routine implementation with independent check. This is deterministic precedence behavior; likely wrong fit for intended baseline mapping, not evidence Small incapable. Intentional force-Medium policy must remain distinguishable from ordinary baseline mapping.

### F2 — split workflow loses routine checker context

`workflow.py:130-134,505`: validation/planning uses node.roles only. `omp_adapter.py:249-253,325-328`: routine_check must resolve same spec and later wave. Probe: direct producer+checker plan=Small; same roles split writer/check node rejects `routine_check: implement-fixed-value: invalid_routine_check`. Same-node direct wave is supported; split-node contract missing. Bounded_check does not have this sibling requirement, but requires producer command authority and existing immutable input.

### F3 — workflow evidence cannot feed existing learning API

`workflow.py:_attach` builds workflow_targets with separate run refs. `omp_adapter.record:440-450` capture/observe requires verify_targets, not workflow_targets. `outcomes.verified_pair:105-116` accepts a single run and later checker wave. Probe against existing strict-accepted tenant workflow: producer-run writer + checker call fails `verified pair roles missing`. Host behavioral proof exists, but recipe API cannot consume it. Do not bypass this by asserting host_authenticated or copying results across runs.

### F4 — discovery requires caller metadata absent in real callers

`omp_adapter.build_plan:257-266,333`: recipe lookup/context only when recipe_features supplied. `automation.observe:305-325`: requires recipe_features,model_revision,routine_check,recipe_profile and verified pair; expected producer binding is configured Small. Successful ordinary Medium role is not discovered. Source binding check safely refuses using Medium success as evidence of Small competence. No bootstrap path from verified Medium opportunity to actual Small trial exists.

### F5 — approved recipe lookup not authoritative route input

`build_plan:264-266`: records recipe_id from effective_small; `remap_seat/effective_combo` never consumes that lookup decision. Probe with explicitly mocked **lookup seam only** (not real approval): lookup effective_small=true and recipe_id recorded, governance baseline Medium, actual combo Medium. Shows plumbing mismatch; does not prove real recipe activation or authorize any state change.

### F6 — recipe eligible set contained in existing routine set

`recipes._safe:237-271` invokes small_eligibility(...routine=True). Thus difficulty<=1.0 and same1–3file/facts/checker constraints already route Small without recipe. Probe recipe max_difficulty1.5 + producer1.2 yields difficulty_above_limit. Schema permits1.5, local governance max1, actual safe gate1; not one uniform supported ceiling. Recipe can supply guidance/audit, but currently cannot learn a genuinely new Medium-to-Small region. Do not remove safety checks to force incremental coverage.

### F7 — exact learning learns labels, not automatic task capability

`adaptive-classifier.mjs:12-20,32-40`: lookup only when declared.answers absent; complete declared need/difficulty retained. `learning.py:431-468`: labels source=user; outcome updates explicitly label_created=false. Identity includes exact normalized brief/context and policy hash. `classification.policy_version:81-89` hashes19source files plus catalog/model policy; edits invalidate matching. `shadow-sampling`10%/max1session compares teacher classification, never executes Small alternative. Medium success does not imply Small competence. Safe behavior, but different product from expected adaptive execution.

### F8 — feedback rejects modern native identity form

`learning._receipt:223-251`: Small-only, requires original observation, accepts model or provider/model but not provider/model:effort; direct file hashing does not share recursive fingerprints. Live completed Small receipts use9router/code-seek:low/medium/high. This is an additional reachability defect for user feedback; no live label attempted. Must reconcile with outcomes.model_proof/fingerprints without weakening them.

### F9 — promotion safety vs unreachable/expensive pipeline

`recipes._auto_ready:374-381`: >=3train,>=5holdout,>=59known, zero fail/unknown,95%zero-failure bound<=5%, consent and policy. Delegated activation queued only from automation.observe. Default local max_difficulty1, modes often shadow/nullpromotion, audit cadence can be1. Small self-learned runs audit only, not training. These guards should not be removed blindly; problem first is zero source/trials and unobservable blockers.59correlated variants must not count independent; no claim this threshold proves production safety.


### F10 — audit cadence1 starvation and incompatible effectiveness probe

Independent plan review exposed additional source facts: recipes._lookup:331-344increments hit then returns effective_small=false when audit due. At cadence1 every reservation is due; clearing audit still makes next reservation due. Current observe needs matching Small proof, so Medium fallback cannot bootstrap Small audit. Recipe _probe:450-507requires priced accounting, equal model bindings and a behavior failure-to-pass improvement; it cannot assess Medium pass/Small pass execution efficiency. Plan phase4 adds explicit audit-delivery reservation and separate signed capability comparison in workflow_evaluation, preserving per-arm native proof and ordinary evaluator contracts.
## Probe observations

1. governance_precedence: eligible=routine; base Small; mapping Medium; reason still routine.
2. routine_direct: Small.
3. routine_split_workflow: invalid_routine_check.
4. recipe_safe_implies_existing_small: blockers=[], routine_small=true.
5. accepted_workflow_learning_pair: workflow_complete=true; verified pair roles missing.
6. approved_recipe_route_seam: mocked lookup true, recipe-id recorded, effective Medium.
7. recipe_ceiling_vs_routine: recipe max1.5, role1.2, difficulty_above_limit.
8. modern_small_feedback: isolated native provider/model:effort receipt shape with model validation seam fixed returns feedback model/effort receipt mismatch before observation lookup. Not a live feedback/label attempt.

No permanent test added for investigation. Temporary probe scripts removed after evidence captured. Run actual behavioral regressions during approved implementation; source-text assertions are not acceptance tests.
