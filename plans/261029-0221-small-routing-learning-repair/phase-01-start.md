---
title: "Phase 1: Routing precedence và evidence funnel"
status: completed
---

# Phase1 — Routing precedence và diagnostic

Priority P1; depends user approval. [Evidence F1/F5/F7](evidence.md). All paths relative to root named in plan.

## Decision

One decision owner in omp_adapter, reused by preview/build/admission and report: need baseline, static capability, approved capability policy, explicit policy floor, critical-risk floor, final Combo/model/effort. Never use `small_route` as execution proof. Stage descriptive; configured explicit effort unchanged.

## Files and steps

1. Modify `crews/omp_adapter.py::{effective_combo,remap_seat,preview,build_plan}`, `crews/governance.py`, `crews/portable_rules.py`, `crews/classification.py`. Use LSP refs if available before exported contract edits.
2. Define baseline map versus explicit minimum Combo policy. Existing nonempty map migrates as **force-preserve** until fresh Large typed policy review; no silent cheapening. New policy may state inherited baseline mapping, then static eligible route applies; explicit force floor and risk always win. Reject contradictory/unknown fields.
3. Preserve recipe lookup result as capability evidence input to same decision, never a second unchecked remap. Result reasons include baseline_combo, candidate_route, blocked_by, policy_source/epoch, final_combo. No `routine` success reason alone when floor actually executes Medium.
4. Reporting in existing `routing_report`, `routing-evidence.mjs`, CLI/MCP: attempts/latest separated, business/governance, direct/intake/workflow/native entry separated. Funnel missing facts/check context/mode/evidence/policy/declared answers/counts, no raw secrets/briefs. Ordinary native tasks remain non-routed and visible as such.
5. Catalog/teacher rubric sync: intrinsic specialist metadata versus old failed-attempt-only teacher text. Declared need stays authoritative; add capability proposal/diagnostic without overwriting acceptance or manufacturing safe facts.

## Todo

- [x] Implement unified precedence with conservative legacy migration and full reasons.
- [x] Update typed governance/catalog/portable/public callers together.
- [x] Add behavior tests: eligible Small+baseline Medium; explicit floor Medium/Large; critical risk; no facts; explicit effort; stale epoch; approved recipe flag versus actual final seat.
[Native provider matching wire proof, installed smoke và conservative cutover hoàn tất; modes/floors không đổi.](native-results.md)

## Gate

Existing `check_bounded_implementation.py`, `check_routine_implementation.py`, `check_effort_policy.py`, `check_keyless.py`, `check_portable_rules.py` plus new regression cases pass. Native wire final seat matches decision, not only preview. No increase difficulty/file ceiling in this phase. Floors preserve currently intentional expensive mapping; ambiguous policy abstains.
