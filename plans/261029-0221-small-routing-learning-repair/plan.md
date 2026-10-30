---
title: "Small routing và vòng học có kiểm chứng"
description: "Sửa precedence và workflow proof, nối discovery/trial/promotion thay vì ép quota Small."
status: completed
priority: P1
tags: [routing, learning, reliability]
created: 2026-10-29
---

# Small routing và learning — hoàn tất, frontier rollout NO_GO

## Overview

Kết luận: Small ít làm producer không chỉ do model capability. Có precedence ghi đè eligible Small, split-node routine/checker chưa nối, workflow proof không vào capture, metadata học vắng và learning live chưa có rule nào. [Evidence và8probe](evidence.md) phân biệt bug, policy bảo thủ và giới hạn thống kê. Không sửa product/policy trong audit.

**Outcome:** route thấp nhất đáp ứng toàn bộ acceptance; successful Medium tạo opportunity, không tự trở thành nhãn Small. Small phải thực thi trial thật, checker độc lập, disjoint evidence rồi mới promotion. Không quota, không đổi main/Combo model/effort; không monetary gate theo quyết định user.

## Quyết định và trade-off

- Chọn sửa pipeline hiện hữu, tái dùng classifier/runner/attempt ledger/verified outcomes/recipes/governance. Không engine hay ML service mới.
- Không chỉ tăng difficulty ceiling/tắt shadow: không chữa missing metadata/proof và có thể mở route thiếu evidence.
- Không automatic remap ordinary native task. Report phải tách main/native/Crews, control-plane/business, attempts/latest, fixture/real. Startup/intake/CLI có route diagnostic thay vì đoán từ UI.
- Need baseline không phải force-minimum. Đề xuất baseline mapping trước capability route; explicit force floor riêng cần fresh independent policy review. Existing nonempty mapping migrate thành force-preserve trước review, không tự reinterpret policy cũ để downgrade.
- Static ceiling giữ bounded1.5/routine1.0. Phase4 đề xuất experimental learned frontier difficulty1–1.5/1–3file/full safety facts với immutable later checker có shell authority còn producer không có. Current bounded/routine không bao phủ1<d<=1.5case này; reviewed Small trial có thể cấp future family competence sau promotion. Không mở ceiling/risk waiver; frontier/trial consent nằm trong plan chờ duyệt.
- Exact user-labelled classification và executable recipe evidence giữ riêng. Không tự tạo user labels từ teacher/model COMPLETE, không dùng Medium pass làm Small pass.

## Phạm vi duyệt

Plan gồm toàn bộ5phase, implementation chỉ sau user duyệt. Trial mặc định đề xuất: tối đa1candidate/session,2native attempts/candidate (Small+checker), tổng2candidate/ngày/project, không auto-retry; admin có explicit limit, không tiền. Frozen original authority/acceptance trước thử; snapshot không chạm working tree. Baseline retained khi missing proof/provider error/risk.

Các59unit/3train/5holdout auto-promotion guards giữ đợt đầu; không tự hạ từ quan sát thiếu task. Đo false accept, accepted delivery, end-to-end latency/token/attempt/overhead, không share Small làm mục tiêu chất lượng.400s chỉ thuộc tenant reassessment, không hardcode toàn learning.

## Goals

| # | Goal | Priority |
|---|------|----------|
|1|Static eligible Small không mất vì implicit baseline; policy force cũ giữ nguyên|P1|
|2|Direct và split-node routine tương đương eligibility khi authority/checker tương đương|P1|
|3|Verified same-run/cross-node outcomes vào cùng funnel có provenance|P1|
|4|Medium opportunity được Small thử độc lập, promotion có evidence chứ không suy đoán|P1|
|5|Report lý do abstain và rollout/rollback kiểm chứng được|P1|

## Phases

1. [Routing precedence và diagnostics](phase-01-start.md) — sửa bug trước, chưa mở ceiling.
2. [Workflow checker và cross-run proof](phase-02-workflow-checker-contract.md) — giữ authority, nối host evidence.
3. [Verified outcome và opportunity funnel](phase-03-verified-learning-funnel.md) — Medium pass không là Small label.
4. [Small trial và promotion](phase-04-small-trial-and-promotion.md) — miền thử nghiệm hẹp, consent và independent evidence.
5. [Real adoption và rollout](phase-05-rollout-and-validation.md) — canary/report/rollback.

## Success Criteria

- [x] F1–F10 có regression hoặc intentional-policy disposition rõ; không dùng source/wording tests làm acceptance.
- [x] Direct/split/CLI/intake/native dùng routing decision/provenance; force floor/risk/explicit effort giữ đúng.
- [x] Native provider Medium baseline và isolated cross-node Small trial có matching native/wire/host proof; xem native-results.md.
- [x] Funnel opportunity/review/trial/evidence/promotion/hit/audit có provenance hoặc blocker; một canary không đủ promotion, không activate.
- [x] Unknown/cancelled/provider/schema không tạo competence; source-group/content holdout và oracle độc lập giữ nguyên.
- [x] Canary isolated; latency1.308x vượt1.20gate nên giữ baseline/modes/floors, không rộng rollout hoặc commit/push.

## Dependencies và authority

Phase1 rồi2 rồi3 rồi4 rồi5. Exact code owners trong phase files; dùng active installed checkout, không phụ thuộc đường dẫn máy tác giả. Read current source/LSP references trước edit; audit lines có thể đổi. User approvals needed for implementation, automatic Small trial authorization and any eventual frontier expansion; defaults above là đề xuất để duyệt, chưa applied tại thời điểm lập plan.

## Verification boundaries

Current audit uses137observations/0labels/0rules/0recipes main state; all205producer/integrate cells thiếu recipe metadata. Historical latest counts không production sample. Partial scout reports không review PASS; independent final plan review recorded after gate. No benchmark old evidence imported as new holdout.

Independent review: run `7e05ea60448442e0bada920f0cfa0ca9`, role `small-learning-plan-review`, repaired review COMPLETE/C1 pass. Authoritative crew_results confirms native `9router/code-astra:high`, wire `code-astra/high`, host_authenticated=true. First review found audit starvation/evaluator/version-strategy gaps; current phase4/5 resolve them. Static plan validity only: host behavioral outcome remains unknown (no executable profile), historical counts/probes not independently reproduced, no runtime competence or efficiency claim. Implementation and trials remain approval-gated.

## Implementation evidence 2026-10-29

Implementation đã cutover42file từ bản làm việc sang active installed checkout, không conflict với original admitted snapshot. Backup trước cutover giữ local ngoài Git; còn tối đa2backup tại snapshot kiểm chứng. Policy/mode/config/keys/history không đổi.

Observed: focused behavioral suites, packaging11/11, immutable actual OMP/local-scripted workflow PASS85.40s, CLI/MCP/catalog và installed doctor ready. Native provider baseline Medium và signed isolated Small trial đều có host independent behavior pass trên frozen final core. Hai timeout trước giữ nguyên. [Native evidence, metrics và giới hạn](native-results.md).

Changed-contract independent review `e5d62887581e40c7b0224d48d575e4a3` static COMPLETE/C1pass, native/wire Large/high và host_authenticated=true. Runtime host behavior của review vẫn unknown (static only); cross-process lock và automation regressions thực thi PASS. Canary token46775vs25400, host latency124191.198msvs162387.955ms(1.307564x): **NO_GO learned-frontier rollout**. Giữ baseline, không activate recipe, không tiết kiệm tiền/production-quality claim. Plan hoàn tất bằng conservative cutover và quyết định không rollout theo gate đã duyệt; restart OMP trên Windows để nạp extension/schema mới.

<!-- slug: small-routing-learning-repair -->