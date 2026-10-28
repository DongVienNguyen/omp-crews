# Phase2 — Source-backed context và staged workflow

Status implemented. Native staged scout/writer/executable-checker and two-child isolation smoke PASS with scripted provider. Explicit reservation recovery, source grants and same-kind dependencies exercised. See [verification](../../VERIFICATION.md); no external model-quality claim.

## Source-backed context packet

Research Small trả thêm typed `context_packet` bên cạnh result status/verification, giới hạn schema/size ở host:

- Facts phân biệt observations/inferences/unresolved; không self-certify đã hiểu toàn bộ repo.
- Source refs project-relative + file hash + line/symbol anchors; command/log artifact refs nếu đã có quyền và tool receipt.
- Chỉ signatures/đoạn liên quan, behavior/invariants/API contract/negative cases; đủ authority để tiếp tục hoặc flag needs_more_context.
- Raw code và log vẫn được giữ ở artifact nguồn; summary không thay file, receipt, acceptance hoặc authority.
- Packet compact chỉ nhận facts có nguồn. Invalid/truncated/stale packet không forward như truth; producer đọc targeted sources hoặc scout lại đúng phạm vi.
- Secrets không được đọc/gửi do “context compression”; scan redaction boundary theo existing authority trước model. Không nói tự động redact mọi secret là đã an toàn.

Tool-first: read declarations/AST/LSP, existing indexed CodeGraph nếu có, compiler output files và targeted snippets. Đừng dùng Small đọc nguyên log mà tool có thể count/filter và chỉ cần error lines. Không enforce file>500line hoặc summary vài trăm token cố định nếu làm mất invariant. Packet size cap dự kiến8KiB/32source refs mỗi node, configurable giảm/tăng theo contract; raw bytes không copy sang mọi downstream prompt. Nếu không đủ, explicit bounded expansion thay silent truncation.

## Dependency execution bằng runner đã có

Manifest version mới: workflow identity + original task authority + invariant set + node IDs/stage/dependencies + node state + run refs/attempt lineage + frozen policy binding. Node không tự chọn model từ tên stage; phase1 classify mỗi role.

- Tạo canonical plan stage-local khi dependencies đã hoàn tất và current artifacts/policy còn hợp lệ. Spec động chỉ trong original read/write/commands; Large spec không tự cấp shell/file permission.
- Discovery→architecture cùng research nhưng khác stage/node phải sequential; scaffold→implementation cùng produce khác node cũng vậy. Không dựa vào cat.wave_order để suy ra dependencies.
- Trivial task direct fast path, không scout/architect boilerplate dư thừa. Không buộc bảy stage mỗi task.
- Producer nhận đúng context packet/spec/artifacts theo dependencies, không toàn bộ record của mọi wave trước. Checker nhận original acceptance/source/artifact, **không nhận producer conclusions**. Research facts có nguồn được checker dùng khi không phải verdict của producer.
- Existing runner slot chống overwrite/replay tiếp tục canonical. Crash reservation, admitted owner unknown, failed node đều có blocked reason; explicit host recovery như cũ, không auto-plan unchanged task để reset cap.
- Cross-node fingerprints chỉ bind sources/acceptance contract thật cần. Không kiểm tra intermediate output hash đã bị legitimate later writer sửa như prior immutable artifact; version/ownership handoff explicit. Bất kỳ change ngoài authorized transition phải refuse.
- Budget từng run hiện có phải đủ roles. Workflow total planned/spent/remaining bound; không dùng nhiều run để né max_cells hoặc repair caps. Stage plan phụ thuộc evidence có runtime refs thay narrative guessed.

## Hai role đồng thời thật sự

Hiện `active` single global là blocker. Refactor native dispatch registry keyed by toolCallId/token và child-local admission context; model receipts/tool receipts/host secrets/abort/finally không dùng shared active pointer.

- Max2children, depth1, no overlap write scope, không đọc file sibling đang viết. Shared contract/input pinned trước; independent branches mới fan out.
- Hook before_subagent_spawn/provider/tool_call phải resolve đúng token/call, không chọn “active đầu tiên”. Chỉ host điều phối; child không spawn grandchildren.
- Nếu host API không cung cấp correlation/lifecycle đầy đủ, **không bật parallel**: report host limitation + sequential execution; stage có thể parallelizable nhưng không claim executed parallel. Đây là prerequisite gate phải xác minh đầu phase trước code worker fan-out; thiếu API cần user chốt thay đổi host hoặc chấp nhận sequential, không lách bằng generic task.
- Không thay global task wrapper bằng orchestration bên ngoài; governance/control jobs dùng cùng registry và ưu tiên idle path, không collision business task.

## Acceptance/smoke

1. Native Small scout→Large spec→Medium implementation→Small mechanical check đúng refs, raw source accessible, no facts laundering.
2. UI/CRUD có đủ context bỏ scout/Large, output acceptance/runtime check giữ đủ.
3. Same-kind dependency không chạy sớm; cycle/unknown node/writer overlap rejects; independent2roles native/wire hashes/secrets không giao nhau.
4. Summary stale/truncated/unsupported statements causes bounded re-read/abstain, not false COMPLETE; permission unchanged.
5. Restart đúng pending state, admitted role không replay, workflow cannot reset caps/new slot while unchanged fault open.
6. Exact source-based checker remains blind even context compression on; missing producer evidence không thành pass.
7. Storage retention protects manifest/attempt/context source needed for active/evidence workflows; không lưu raw secrets vào report.
8. Smoke trên CLI/OMP surface thật và scoped component behavior; existing runner/intake/lifecycle/storage suites không regress.
