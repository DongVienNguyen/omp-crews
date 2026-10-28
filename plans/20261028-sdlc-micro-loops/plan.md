---
title: "Cost-aware SDLC micro-loops với kiểm chứng độc lập"
description: "Small thu facts và sửa được chốt; Medium thi công; Large giải quyết bất định/rủi ro, không định tuyến theo token hay số file."
status: completed-enabled-by-operator
priority: P2
tags: [routing, sdlc, cost, reliability]
created: 2026-10-28
---

# SDLC micro-loops — enabled by operator

## Quyết định

Áp dụng ý tưởng bảy giai đoạn của người dùng dưới dạng **workflow theo phụ thuộc, chỉ chạy stage cần thiết**, không waterfall bắt buộc, không quota Small/Medium/Large. Tái sử dụng classifier tám need, native admission/receipt, checker, runner, governance và portable rule hiện có. Không thay main model hoặc gán model marketing vào Combo; policy hiện dùng code-seek/code-sol/code-astra, nhưng không xác minh được backend thực hay tốc độ/giá model do provider ánh xạ.

**Outcome:** giảm toàn bộ chi phí để giao một task đúng, bằng tool-first retrieval, Small context packet, Architect–Builder split, sửa lỗi có lịch sử và review theo rủi ro. Chất lượng là gate trước chi phí; không hứa “cao nhất” tuyệt đối hoặc giảm60–75% khi chưa đo.

**Không làm:** đổi credentials/model/effort của người dùng; tự đọc .env thật; tự publish/deploy/seed DB thật; tăng retry cap; thay workflow AgentKit; thay ordinary chat/native task bằng Crews; training từ self-COMPLETE; nhập pilot cũ thành holdout mới. Không thêm model/dependency/framework orchestration thứ hai.

## Kết quả kiểm tra hiện tại

1. `crews/classification.py::{RUBRIC,classify_role,safety_errors}` đã phân loại theo deliverable, ưu tiên khai báo hợp lệ và facts; unknown không phải false. `omp_adapter.py::effective_combo` đã map tám need đúng ba Combo và có bounded/routine Small.
2. `small_eligibility`: routine<=1.0, bounded<=1.5,1–3file explicit, facts an toàn và checker độc lập. Đây là gate route cụ thể, **không phải quy tắc >=4files thì Large**.
3. `governance.py::validate` chỉ thay mapping theo need, mode, evidence/promotion, audit, lease/quota trong schema; JSON routing **không tạo decomposition/stage/handoff/circuit breaker**. Current specialist text chủ yếu dựa vào failed strong attempt; cần làm rõ intrinsic specialist khi update rubric, không giả tạo lịch sử thất bại.
4. `planner.py::build` dùng thứ tự kind research/produce/integrate/check; mọi role cùng kind ở cùng wave. Chưa có dependency graph cho discovery→architecture (cùng research), scaffold→implementation (cùng produce), check→repair→recheck.
5. `shaping.py::propose` chỉ xác thực proposal đã có authority, không tự tạo role. `runner.py::dispatch/inspect` giữ một run-slot, không phải workflow engine hoặc native executor.
6. `planner.py::_prompt/build` truyền record paths của wave trước cho non-check; checker tránh producer conclusions. `omp_adapter.admit` materialize record khi handoff và kiểm tra hash; chưa có compact context packet có nguồn/citation/freshness và selective dependencies.
7. `extension.ts::dispatchCrew` dùng mutable `active`, một `ctx.invokeTool` và spawnUsed; plan/database nêu concurrency2 nhưng wrapper serialize một dispatch. Không được quảng cáo đã chạy hai writer song song qua extension này.
8. `omp_adapter.escalate` đếm tối đa2repair/4escalation tổng run, sửa latest result khi retry; chưa đếm hai lần sửa **cùng lỗi** xuyên stage/run, chưa có immutable per-attempt cost/outcome ledger. Nguyên nhân unknown, schema/provider/tool lỗi và behavior fail phải tách.
9. `outcomes.py` có độc lập machine behavior/model proof; `routing_report` hiện là latest role population, main-orchestration/pricing unknown. `accounting.py` có signed full-run attestation; `evaluation.py` freeze holdout và chất lượng/cost/P95 gate. Chưa có đo cost per accepted full workflow, gồm repeated context, governance/main/classifier/retries.
10. Pilot trước (`../20261027-0626-small-routing/pilot-final-report.md`) là reconstructed faults có tương quan; NO-GO rộng hơn, thiếu full cost/latency. Không dùng19/20 làm bảo đảm quality production hoặc miễn gate mới.

### Smoke đã chạy trong state tạm

- Exact prescribed transform → repeatable_task/Small/medium.
- Implementation4file, known method → everyday_implementation/Medium/medium; không tự Large.
- specialist difficulty2 → Large/high.
- unknown_cause=true gắn cheap need bị từ chối.
- check có write scope bị shaping từ chối.
- research architecture + research lookup cùng một wave dù cần thứ tự; sau khi khai báo task budget divisible hợp lệ, plan cho concurrency2/depth1. Không spawn worker cho smoke này.

Read-only source scouts chỉ cung cấp facts tham khảo; một role trả PARTIAL/failed, role kia không có strict completion đáng tin. Không tính chúng là review PASS; các kết luận trọng yếu được đọc source và smoke trực tiếp. Không thay source/state/config thật.

## Chỉnh lại đề xuất người dùng

| Đề xuất ban đầu | Thiết kế chọn |
|---|---|
| Input lớn bắt buộc Small | Tool/AST/LSP trước. Small làm retrieval rõ mục tiêu; root-cause/semantic/security vẫn cần model đúng capability dù input lớn. |
| Mọi task đi qua Small scout | Chỉ khi thiếu context. Đã có file/spec đủ thì direct route, tránh thêm lượt model/handoff. |
| >=4files gọi Large | Chỉ undecided interfaces, uncertainty, risk, prior failure mới cần Large; file count chỉ là blast-radius signal. |
| Mechanical check tự sửa | Check luôn read-only. Check trả diagnostics; writer mới nhận patch hẹp → repeatable hoặc bounded/routine implementation; check lại độc lập. |
| JSON mẫu→Zod/schema luôn mechanical | Chỉ mechanical nếu required/null/optional/validation semantics đã chốt. Mẫu JSON không xác định đầy đủ contract. |
| Specialist = mọi SQL/queue/regex | Framework keyword không đủ. Known N+1 fix Medium; diagnosis khó/concurrency correctness/precision cần Large; specialist intrinsic phải có capability reason rõ. |
| Large không bao giờ viết code | Large chủ yếu thiết kế/diagnose/review; được viết isolated hard core thật sự cần nó, không viết boilerplate. |
| Hai lỗi là tăng model | Hai **behavioral repair attempts** cùng fault/acceptance ở Medium thì dừng Medium. Provider/schema/cancel không là hai code bugs; vẫn tốn budget và có stop riêng, không retry vô hạn. |
| CRUD/UI bỏ Large và kết thúc sau lint | Large chỉ risk gate cần; ordinary task vẫn independent acceptance/runtime proof, không chỉ lint. |
| Docs/commit message luôn repeatable | Chỉ khi nội dung/scope/facts đã cố định. Docs cần quyết định nội dung là implementation; commit/push vẫn cần user authorization. |
| Đạt80% thì giao model rẻ | Chọn model thấp nhất đáp ứng **toàn bộ acceptance**; không chấp nhận80% chất lượng. |
| Bắt buộc70% code Medium/giảm60–75% | Không quota, không số tiết kiệm đoán. Tính accepted-task cost với verified pricing, coverage và quality gate. |

## Thiết kế chọn

- **Hai trục:** `stage` mô tả SDLC; `need` giữ tám routing keys; `kind` mô tả read/write authority; difficulty/risk/facts độc lập. Stage không ép model.
- **Tool-first context:** công cụ lọc/count/compile trước, Small diễn giải facts có citation. Small packet không thay code nguồn, không xóa unresolved evidence và không thành authority.
- **Staged workflow:** dependency manifest và stage-local canonical plans dùng runner hiện hữu. Admission cũ vẫn chính chủ model/effort/token; check sạch, recheck sau sửa. Không dựng DAG scheduler riêng trong planner upstream.
- **Parallel:** tối đa2role độc lập, write scopes không giao nhau, shared contract đã khóa. Cần refactor active dispatch registry theo toolCallId/token trước khi bật hai native child; không dùng ordinary task để né Crews.
- **Fault-aware retries:** immutable attempts + logical fault grouping; cap cũ giữ nguyên. Lỗi rủi ro/unknown chuyển Large ngay, không cần trả phí hai lần. Failed-attempt evidence không được mất khi latest result thay đổi.
- **Governance:** Large policy review vẫn có quyền chỉnh thông số hỗ trợ, nhưng stage/fault metadata không cấp write authority hoặc làm lệch explicit Combo effort. Control-plane review được thống kê riêng, không giả thành business-task Large share. Portable crews-rule phải hỗ trợ snapshot/epoch fields mới, không nhét system prompt vào policy object.
- **Tiến triển an toàn:** chỉ chứng minh quyết định hợp lệ bằng facts và receipt, không tăng routine ceiling/quota Small ở đợt đầu.

## Phương án đã so sánh

1. Chỉ sửa skill/prompt: ít diff, tốt cho discipline nhưng không enforce retry/dependencies/handback; thất bại đầu tiên khi model bỏ bước hoặc context mất invariant. Không đủ cho mục tiêu này.
2. **Mở rộng runner/adapter đã có**: thêm stage manifest, context packet và attempt ledger; tái dùng admission/evidence/governance. Chọn vì có thể kiểm chứng từng phase và không tạo convention thứ hai.
3. Engine SDLC/DAG mới toàn diện: nhiều surface/scheduler/state mới, trùng runner/planner và tăng chi phí bảo trì; chỉ cân nhắc nếu dependency model phase2 không đáp ứng workload thật.

## Phases và điều kiện duyệt

1. [Phase1 — Contract & routing](phase-01-routing-contract.md).
2. [Phase2 — Context & staged execution](phase-02-context-workflow.md), phụ thuộc1.
3. [Phase3 — Circuit breaker & quality](phase-03-fault-quality.md), phụ thuộc1–2.
4. [Phase4 — Cost evaluation & rollout](phase-04-evaluation-rollout.md), đo baseline trước mọi mutation; promotion rollout sau1–3.

[Ma trận toàn bộ micro-tasks](micro-task-matrix.md). [Source map và verification contract](source-evidence.md).

Independent planning review COMPLETE: run6ecb14f37c6c4c8aab4d55fe4fc9c9b2. Implementation evidence and scoped independent closure: [VERIFICATION.md](../../VERIFICATION.md). Planning review is not runtime proof.

**Gate hoàn tất:** mọi row ma trận có route hoặc abstain có lý do; stage order/checker/authority/policy snapshot đúng; source citations không stale; hai behavioral repair attempts cùng fault ngăn Medium attempt tiếp; no silent replay; native2role không receipt collision; budget không bỏ sót main/governance/context; frozen independent behavior không thoái lui; không false-COMPLETE; missing pricing vẫn unknown. Không cài/push khi chỉ viết plan.

## Handoff

User explicitly enabled before qualification.0.11.1 main/canary ready; fresh default sdlc_cost_aware, native crew_workflow and strict task.structured enabled. Original authority/model/effort/state, pinned history and retry/replay guards preserved. Native real entry/strict yield smoke and independent reviews pass within stated scope. Full64arm evaluation complete:23workflow-complete each arm; strict accepted0due frozen-source/policy drift and missing/cancelled evidence, quality/latency NO_GO. This is diagnostic mixed-condition evidence, not production or noninferiority proof. [Results](benchmark/results.md). Code commit67d634a pushed; restart OMP/MCP required.
