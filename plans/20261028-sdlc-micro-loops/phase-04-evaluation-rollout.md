# Phase4 — Đo toàn workflow và rollout

Status enabled by explicit operator override before benchmark qualification.0.11.1 applied; default sdlc_cost_aware and native crew_workflow. User removed money criteria. Full32-unit/64-arm reconstructed evaluation continues without replay; independent behavior/latency verdict stays separate from permission to enable. Host structured-output prerequisite repaired; old failures not reclassified. See [verification](../../VERIFICATION.md).

## Frozen task corpus

Đề xuất32task độc lập có behavior/oracle rõ,8family,4task/family: retrieval/docs extraction, fixed transforms/scaffold, UI CRUD, API/contract, test+repair, architecture/security, concurrency/precision, performance diagnosis. Có ít nhất một normal/error/boundary hoặc risky near-miss trong mỗi family phù hợp. Đây là số task pilot, không đủ bảo đảm tuyệt đối; confidence phải report, không suy tỷ lệ nhỏ thành production guarantee.

- User approved reconstructed benchmark, clearly labelled; [corpus.py](benchmark/corpus.py) owns32independent exercises and executable acceptance. No production-equivalence claim or old pilot import.
- Freeze task/spec/acceptance/initial files/source grouping, environment, policy/model binding và evaluator trước chạy. Context-compression baseline/candidate cùng authority và original acceptance.
- Baseline hiện tại và candidate workflow mới chạy trên isolated identical snapshots; randomize hoặc counterbalance arm order, giữ resource/concurrency điều kiện giống nhau; cached input/provider variance ghi rõ.
- Training/recipe suggestion không sử dụng holdout evaluation verdict. Development/corpus calibration tách frozen holdout; governance source statistics không học từ candidate benchmark arm rồi reuse baseline arm.
- Dùng32pairs=64arms chỉ khi cả hai arm được operator-authorized. Failed/cancelled/provider/schema và unknown tính delivery/accounting riêng, không cherry-pick chỉ pairs đã pass. Không reset cap/retry để đủ bảng.

## Chi phí thật trên accepted task

Lưu theo workflow+attempt ledger phase3:

1. Main orchestration, scout, architecture, every builder/checker, classifier, governance/control review, repair/escalation/recheck và context serialization/read overhead.
2. Input/output/cache-read/cache-write/reasoning nếu provider cung cấp; latency critical path/P50/P95 và provider attempt count, không role latest count.
3. Actual context bytes/tokens sent từng node + overlap/source read counts; source bytes không tự tương đương provider tokens. Không bắt buộc tokenizer mới nếu host/provider đã báo.
4. Giá có provenance/current provider/model revision; giá0metadata và missing main usage là unknown. Reuse signed accounting/full-run attestation cho independent evidence; keyless governance không tự ký tiền hoặc bịa pricing.
5. Accepted task = original acceptance passed by independent checker + valid delivery/model/authority proof. Cộng chi phí **mọi attempt của cả corpus**, kể cả task fail, chia số task accepted; nếu không có accepted thì không finite “saving”. Report thêm total spend/delivery count để tránh denominator che task khó.
6. Control-plane cost tách riêng và amortize minh bạch: per-session/workflow coverage, số task chia, cold/warm installation; không bỏ governance vì “không thuộc code”. Không chạy governance riêng cho từng micro-task.

## Gate đề xuất để user duyệt

- Quality: candidate không thêm confirmed regression so với baseline trên bất kỳ family; không false accepted behavior, unsafe scope/secret access, tự sửa oracle hoặc replay. Unknown không bằng0failure hoặc pass.
- Delivery: số accepted candidate không thấp hơn baseline; blocker/abstention phải có lý do đúng, không tăng Small bằng từ chối toàn task khó. False-COMPLETE producer caught by checker ghi trust metric, không che trong aggregate pass.
- Cost gate removed by explicit user decision. Use signed `evaluation_mode:"quality_only"`; money_status remains not_evaluated and cost_gate=null. Default monetary mode remains available but is not this rollout's acceptance criterion.
- Latency: P95 end-to-end <=baseline*1.20; candidate parallel arm so với baseline cùng resource config hoặc report separate sequential/parallel. Under-powered pilot report uncertainty và widen evidence trước default nếu cần.
- Context: không mất original invariant/negative case; source stale/truncated prompt injection được xử lý đúng, no false conclusion từ Small summary. Đếm context reduction, không áp mục tiêu60–75%.
- Concurrency: nếu host không hỗ trợ2native tasks correlation, gate parallel BLOCKED, không skip acceptance rồi claim all done. Có thể xin user duyệt sequential rollout riêng; plan không mặc định đã cho phép giảm scope.
- Retry:2same-fault Medium failed repairs chặn Medium attempt tiếp;0counter resets qua rename/run; provider issues không bịa behavioral labels; immutable ledger đầy đủ.
- Public surface: CLI/MCP/OMP actual smoke, portable export/import profile revision và reject stale proposals, startup/runtime packaging idempotent, legacy historical rows đọc được. Governance không thể bỏ source/checker/authority invariants.

## Rollout

1. Operator now explicitly enables sdlc_cost_aware for fresh workflows; baseline remains explicit opt-out. Existing manifests retain pinned profile. Startup selects native crew_workflow for multi-stage Crews work; one-step direct intake and ordinary native model path unchanged.
2. Reconstructed provider corpus explicitly authorized. [runner.py](benchmark/runner.py) emits arm progress, retains terminal failures and supports STOP at arm boundaries; no replay or automatic retry. No price cap requested by user.
3. Canary trên project đã chọn; mỗi completed workflow report route/stage/guard, strikes, accepted behavior, usage coverage và policy epoch. Không self-promote profile từ model summary.
4. Benchmark verdict remains honest even after operator enablement. No receipt/checker/scope/cap exemption or model self-promotion. Existing recipes/control-plane remain separate.
5. Rollback chỉ chọn baseline cho **future workflows**; active pinned workflow tiếp tục binding hoặc pause rõ nếu policy invalid. Không rewrite old attempts/outcomes; không xóa ledger để undo.
6. Docs/skill/CLI help khớp schema; hướng dẫn export profile policy để AI ngoài tối ưu bằng proposal, không dán system prompt vào JSON. Model names remain IDs do user cấu hình, explicit effort giữ nguyên. Commit/push sau implementation chỉ khi user yêu cầu.

## Deliverable

Quality/latency/context table per family, per-stage routes, native receipts and GO/NO_GO. No guarantee cao nhất, no70%quota, no price/speed guesses. Operator explicitly overrode promotion gate to enable before qualification; benchmark result remains separate and honest. Apply and commit/push remain authorized.
