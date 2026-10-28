# Phase3 — Two-strike và quality gate

Status implemented. Append-only attempts, criterion-specific cross-run strikes, explicit repair/recheck and partial successor ownership exercised. See [verification](../../VERIFICATION.md). Provider failures remain separate from behavioral failures; no historical receipt rewriting.

## Immutable attempt ledger

`calls.result` hiện là latest result, bị reset khi repair; giữ nó làm view tương thích, thêm append-only attempt rows cùng DB transaction với record/escalation. Mỗi attempt có workflow/node/logical_issue/fault_key, original acceptance hash, source revision, Combo/effort, disposition/failure_kind, actual behavior proof, native/wire refs và observed usage/latency. Không ghi token/capability secret vào portable rule hoặc UI.

Fault grouping: host-owned logical issue/counter lineage qua dependency stages; normalize diagnostics/criterion IDs + acceptance + target set. Hash diagnostic text đơn thuần không đủ: compiler wording thay không được coi bug mới. Same caller rename role/run/stage không reset; merge/split fault cần explicit evidence và event. Changed requirement được phân biệt với tiếp tục sửa cùng bug, giữ original lineage.

## Two-strike chính xác

- **Strike** là một completed Medium **repair attempt** mà independent behavioral check cùng acceptance/fault vẫn fail. Initial feature implementation failure không tính như đã sửa một lần. Hai repair attempts thất bại → không dispatch Medium repair tiếp cho issue đó.
- Khi đủ2strikes, next route Large specialist diagnosis. Nó có thể trả prescribed fix cho worker phù hợp hoặc làm isolated hard fix; bằng chứng thực hiện và check độc lập không mất. Current total2repairs/4escalations/run vẫn cap; workflow không cộng thêm quota nhờ chia run.
- Nếu cap không đủ chuyển tiếp, stop với preserved artifact/evidence và đề xuất architecture decision, không tạo run mới để né. Large fail không có tier cao hơn; không rename retry.
- Unknown cause/serious risk có thể Large ngay, không “cheap80% trước” hoặc bắt trả hai lần Medium mới được Large.
- Provider timeout/schema/tool/cancel không là behavioral strike; tiêu thụ execution/resource/retry cap như hiện tại, được báo riêng. Không có code fix proof thì không tăng/giảm quality labels. Repeated transport lỗi pause/escalation theo policy host, không endless retry.
- Native record FAILED do checker có actual fail phải phân biệt với producer task_failed và test flake. Failed model strict output không chứng minh code sai nhưng vẫn không được đánh COMPLETE.

## Independent verification

Mechanical stage = check read-only. Có thể chạy compiler/lint/schema compare được cấp quyền. Diagnostics mở producer repair node riêng; code/text scope chốt trước admission. Không cho check sửa imports rồi tự chứng nhận.

Test-writing Medium là producer; checker/profile oracle không được writer sửa. Nếu bug nằm ở checker, suspend verdict, review checker meaning độc lập, tạo profile version mới và không reuse old positive evidence. Không special-case fixture, xóa assertion, skip case hay re-pin wording để xanh.

High-risk facts security/auth/money/precision/concurrency/data_loss/public-contract mới cần check Large tương ứng; risk chưa rõ không silent safe. Ordinary CRUD/UI vẫn có independent behavior/check runtime; Large không mandatory business reviewer chỉ vì bảy-stage template.

Recheck sau repair bind current artifacts, exact criterion, explicit exit proof; no stale record fingerprint overwrite. UI exercise actual surface; API/CLI run thing, not only mocked tests. Mock signatures/receipts chỉ test boundaries, không gọi nó model-quality evidence.

## Acceptance

- Repair1fail+repair2fail cùng fault → Medium repair3 refused trước provider request, Large next allowed chỉ trong còn cap.
- Initial failed implementation+repair1pass không strike2; one provider failure+one actual behavior failure không bị ghi hai code strikes.
- Rename role, new stage, new runner slot, diagnostic wording change không reset counter; unrelated criterion mới không bị dính oan.
- Multiple Medium nodes dùng cùng fault vẫn chung lineage; concurrency record không double debit hoặc tạo2next steps.
- Read-only checker cannot write; producer cannot mutate checker oracle; fresh recheck cannot use stale fingerprints.
- Two interrupted admissions không tự thành behavioral failures; recovery requires proven dead host, preserves caps.
- High-risk path Large review and ordinary CRUD non-Large path đều có actual acceptance proof; no false-COMPLETE, no silent downgrade after escalation.
- Legacy calls view/history vẫn đọc được; append-only ledger đủ attempt usage, latest report nêu population rõ.
