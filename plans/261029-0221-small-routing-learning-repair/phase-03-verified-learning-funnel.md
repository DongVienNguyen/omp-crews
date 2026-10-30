---
title: "Phase 3: Outcome collection và candidate discovery"
status: completed
---

# Phase3 — Make learning reachable, not automatic self-labels

P1; depends phase2. [Evidence F3/F4/F7/F8](evidence.md).

## Boundaries

Exact classifier memory remains user-labelled and exact; recipe competence evidence remains independent executable proof. User labels are not silently minted by model/teacher, and successful Medium means only a **candidate opportunity**. No need relabeling to mechanical/repeatable to force Small.

## Files and steps

1. Modify `crews/learning.py::_receipt`, `crews/outcomes.py::{model_proof,fingerprints}` consumers, `adaptive-classifier.mjs`, `learning-editor.mjs`. Shared proof validation accepts valid provider/model:effort form and directory fingerprints; rejects wrong effort/model, stale artifacts, no original observation, self-learned feedback. Read-only feedback options list blockers; actual labels still user confirmation.
2. Preserve exact signature/privacy/version semantics. Report why declared complete answers never consult exact lookup, why shadow/off prevents hits, why policy drift invalidates rule. Do not loosen exact matching or safety on message similarity. Ensure direct plan/workflow route is explicitly marked as skipping adaptive intake; no claim every task automatically trains exact model.
3. Extend host completion discovery (`crews/automation.py::observe`, `crews/recipes.py::capture`, adapter record) using phase2 outcome refs. Successful Medium/Small non-learned producer with genuine independent checker may create non-authoritative opportunity even when caller lacks recipe_features. Derive objective family proposal from bounded metadata/artifact contract; missing semantic family/oracle meaning queues Large review or abstains, never guesses risk=false.
4. Opportunity stores provenance/acceptance/profile hash/model binding/source grouping and exclusion reasons; not raw secret task data. Reuse existing learning.sqlite, recipe/job state conventions, schema migration and report. Distinguish medium_baseline_evidence from small_competence_evidence; latter only from actual verified Small execution. Minimal separate record needed so no Medium row can accidentally count as Small success.
5. model_revision must be real provider/OMP supplied or explicit reviewed operator metadata; unknown revision visible and blocks persistent cross-revision competence promotion. Do not fabricate marketing identity/hash as actual backend revision. Current-in-session binding may support nonpersistent trial under exact policy; durable rule requires approved version strategy.
6. Persist blocked-stage counts: no authority/no checker/no metadata/unknown revision/mode/lease/no Small evidence/holdout short/audit pending. Existing success paths should not disappear under broad except/pass; surface safe reason, never swallow proof error into success.

## Todo

- [x] Fix reachable modern Small feedback and maintain explicit label authority.
- [x] Host-opportunity discovery for verified same-run/cross-node Medium and Small.
- [x] Expose candidate-vs-evidence funnel with provenance and dedup.
[Native Medium opportunity tới reviewed signed Small trial thực thi pass; không labels/activation tự tạo, live modes unchanged.](native-results.md)

## Gate

Observed real historical receipts used only as diagnostic, never retroactive labels. Isolated tests prove Medium pass creates opportunity but **zero Small train/holdout labels**; false-COMPLETE/cancel/provider/schema/unknown never success. Metadata-free task reaches proposal review or exact abstain, no authority change. No .env/key/credential capture. Existing exact learning/recipe/automation privacy tests pass. Only user-approved project modes changed after plan approval; current audit shadow modes are preserved until explicit rollout decision.
