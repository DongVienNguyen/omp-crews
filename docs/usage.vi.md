# Hướng dẫn sử dụng crews-omp

Hướng dẫn dành cho người dùng và người cài từ Git. [README](../README.md) mô tả contract kỹ thuật; lệnh `help` của [CLI](../bin/crews-omp.mjs) là nơi tra cứu cú pháp hiện hành.

## 1. Crews làm gì?

Crews chia công việc đã được cấp quyền thành các role, chọn Combo phù hợp cho từng role và kiểm tra model/effort thực sự đã chạy. Nó không đổi main chat model và không chuyển mọi cuộc trò chuyện thành công việc nhiều agent.

Có ba lớp riêng biệt:

- **Routing:** chọn Small, Medium hoặc Large cho từng role.
- **Governance:** Large review tổng hợp, chọn chính sách vận hành và gia hạn phiên hoạt động.
- **Recipe:** kinh nghiệm có checker/evidence cho một nhóm task; chỉ được tái sử dụng khi điều kiện hiện tại phù hợp.

Đây là tái sử dụng kinh nghiệm có kiểm chứng, **không huấn luyện lại trọng số model**. Model nói `COMPLETE` không tự trở thành bằng chứng code đúng.

## 2. Chuẩn bị trước khi cài

Cần có:

1. OMP hỗ trợ native task và các hook mà plugin yêu cầu; xem [Requirements](../README.md#requirements).
2. Git, Node.js 20+ và Python 3.12+.
3. Provider/model đã được cấu hình và đăng nhập trong OMP. Plugin không tạo tài khoản, API key hoặc tự tải Python.

Mặc định Combo dùng provider `9router` với `code-seek`, `code-sol`, `code-astra`. Nếu bạn không có các ID này, đổi Combo sang các model hợp lệ của provider bạn dùng trước khi thực hiện task. Model cần hỗ trợ effort đã chọn. `doctor` sẽ chỉ ra alias/effort thiếu.

Windows đã có smoke và lifecycle verification. Linux/macOS cần kiểm chứng môi trường tương đương; không coi ví dụ shell là chứng nhận hỗ trợ mọi máy.

## 3. Cài mới từ Git

### Windows PowerShell

Chọn một thư mục giữ source lâu dài, không phải thư mục tạm:

```powershell
$src = Join-Path $env:USERPROFILE "Projects\omp-crews"
git clone https://github.com/DongVienNguyen/omp-crews.git "$src"

omp plugin link "$src" --scope user
node "$src\bin\crews-omp.mjs" setup --python python --json
node "$src\bin\crews-omp.mjs" doctor --json
```

Nếu `python` không phải Python 3.12+, thay bằng đường dẫn đầy đủ tới Python phù hợp. Setup tạo venv riêng; không chạy system pip thủ công.

Có thể dùng `omp plugin install https://github.com/DongVienNguyen/omp-crews.git --scope user`, rồi chạy `setup`/`doctor` từ vị trí package đã cài. Clone và link giúp biết rõ đường dẫn source dùng cho cập nhật và CLI.

**Đóng/mở lại OMP sau cài hoặc cập nhật.** MCP/extension đang mở có thể giữ schema hoặc policy hash cũ.

### Kết quả mong đợi

- `setup`: `ok:true`, runtime riêng và local automation enabled.
- `doctor`: `ok:true`, `status:"ready"`, `problems:[]`.
- Không cần tạo `operator-public.pem`, private key hoặc ký grant để sử dụng chế độ mặc định.
- Setup không gọi model để đăng ký hàng loạt recipe. Review Large khởi tạo xảy ra khi bắt đầu dùng project.

Nếu trước đây từng thử signer và báo `EISDIR`, đó là do truyền thư mục thay vì tên file. Với chế độ mặc định hiện tại, **không cần tiếp tục chuỗi lệnh ký đó**. Không xóa/ghi đè key cũ nếu còn dùng giao diện signed nâng cao.

## 4. Bắt đầu dùng một project

```powershell
$project = "D:\Projects\my-app"
omp --cwd "$project"
```

Trong OMP, giao nhiệm vụ như bình thường, ví dụ:

> Dùng Crews kiểm tra luồng đọc cấu hình, sửa lỗi đã xác định và kiểm chứng hành vi trên input hợp lệ, thiếu giá trị và sai kiểu. Không đổi API công khai.

Orchestrator vẫn phải xác định scope, lệnh và acceptance cho từng role. Crews không tự suy ra quyền ghi file/lệnh từ một câu mô tả mơ hồ. Câu hỏi đơn giản có thể trả lời trực tiếp, không cần tạo nhiều agent.

Lần đầu project được đăng ký, host tạo review policy cho Large. Nếu session thông báo queue governance đang chờ, agent thực hiện:

```json
{"automation": true}
```

qua tool `task`. Đây không phải lệnh PowerShell. Host chọn job đã lưu, không cho caller thay request cần duyệt. Không cần bạn xác nhận từng review. Nếu phiên bị ngắt, mở lại OMP trong đúng project để tiếp tục theo trạng thái host, không tự replay run cũ.

Tra cứu bằng CLI ngoài OMP:

```powershell
node "$src\bin\crews-omp.mjs" automation status --project "$project" --json
node "$src\bin\crews-omp.mjs" recipes status --project "$project" --json
node "$src\bin\crews-omp.mjs" report --project "$project" --json
```

`--project` là đường dẫn tuyệt đối tới project đang làm, **không nhất thiết là thư mục source Crews**. Chạy status ở project khác sẽ thấy dữ liệu khác.

## 5. Đọc trạng thái và chế độ hoạt động

| Trạng thái | Cách hiểu |
| --- | --- |
| `enabled:true`, grant `live:false` | Local automation được cho phép nhưng lease chưa được duyệt, đã hết hạn/quota hoặc đang pause. Không có nghĩa task có quyền vượt lease. |
| grant `live:true` | Phiên policy đang hợp lệ. Mode recipe vẫn có thể là `shadow` hoặc `off`. |
| job `queued` | Chờ host dispatch review. |
| job `reviewing` | Đã gắn với một native review; xem run và kết quả, không tự chạy trùng. |
| job `applied` | Host đã áp dụng quyết định được xác minh. |
| job `blocked` | Có lý do từ chối, stale hoặc lỗi. Xem `result` và `events`. |

Recipe mode:

- `off`: không dùng recipe để thay routing.
- `shadow`: theo dõi/thu evidence nếu policy cho phép, nhưng không áp dụng recipe Small.
- `on`: recipe đủ điều kiện có thể được dùng; vẫn phải qua safety, checker, model/profile và evidence gate.

**Large có thể chọn shadow hoặc tắt promotion khi evidence yếu.** Không cần ép cấu hình thành `on` chỉ để thấy Small chạy nhiều hơn. Routing Small cơ bản cho task đơn giản và recipe routing là hai cơ chế khác nhau.

## 6. Large được tự điều chỉnh gì?

Policy review trả cấu hình có kiểu dữ liệu, host kiểm tra bằng [schema và validator](../crews/governance.py). Các trường gồm:

- `routing`: ánh xạ loại công việc sang Combo.
- `mode`, `auto_evidence`, `auto_promotion`: vận hành recipe và evidence.
- `max_difficulty`: phạm vi routine implementation mà cơ chế hiện có hỗ trợ.
- `audit_every`: tần suất yêu cầu audit mới.
- `lease_seconds`, `max_reviews`: thời gian và số review trong một phiên hoạt động.

Large được chọn các giá trị trong schema hỗ trợ, không được tự sửa validator để mở rộng giới hạn. Khó review/architecture vẫn giữ Large; Small không nhận task unsafe chỉ vì mapping bị đổi. Provider/model/credential được người dùng quản lý qua Combo/OMP, không phải policy review.

### Gia hạn tự động

Host lên lịch review khi lease gần/hết hạn, hết quota hoặc policy binding cần review mới. Large đọc số liệu tổng hợp và trả policy; host xác minh native/wire receipt rồi gia hạn. Quota không phải giới hạn dùng cả đời và không phải trần chi phí tiền.

- Duyệt hợp lệ: lease mới, epoch mới, quota phiên được làm mới.
- Từ chối hoặc output sai: pause, giữ lịch sử; không giả vờ đã duyệt.
- Evidence mới có thể làm hệ thống review lại. Nếu cần chủ động yêu cầu đánh giá lại sau khi xử lý nguyên nhân, dùng `automation enable`.
- Không có daemon khi OMP đóng. Sau thời gian không dùng, review sẽ chạy khi mở lại hoặc host tiếp tục công việc.
- Gia hạn policy không đồng nghĩa tự tái kích hoạt recipe đã suspended/rolled back hoặc bỏ thời hạn recipe.

### Tắt và bật lại

```powershell
node "$src\bin\crews-omp.mjs" automation disable --project "$project" --yes --json
node "$src\bin\crews-omp.mjs" automation enable --project "$project" --yes --json
```

Disable là chủ ý người dùng, được giữ qua setup/restart; Large không tự đảo ngược. Enable không nhận policy tùy ý từ caller; thay đổi policy cần review Large. Các plan/ticket dựa trên epoch cũ có thể bị từ chối và cần plan mới.

## 7. Chọn model và effort cho các Combo

Trong OMP:

```text
/crew combos
```

Hoặc CLI:

```powershell
node "$src\bin\crews-omp.mjs" combo show --json
node "$src\bin\crews-omp.mjs" combo set --provider my-provider --small-model fast-model --small-effort Auto --medium-model balanced-model --medium-effort Auto --large-model reasoning-model --large-effort High --json
node "$src\bin\crews-omp.mjs" doctor --json
```

Thay các ID ví dụ bằng model thực sự có trong OMP. Không đưa API key vào lệnh Combo.

- Small: retrieval có giới hạn, tác vụ lặp lại, kiểm chứng cơ học và sửa code đủ điều kiện.
- Medium: implementation có chi tiết cần quyết định, công việc agentic nhiều bước.
- Large: review khó, architecture, specialist và governance.

`Auto`: difficulty <1 dùng low; từ1 đến dưới2 dùng medium; từ2 dùng high. Effort cố định của Combo thắng Auto. Mỗi role được phân loại riêng; không lấy độ khó toàn project áp cho mọi role. Thay Combo/model/effort làm plan cũ stale; tạo plan mới, không sửa lịch sử receipt.

## 8. Evidence, recipe và kiểm tra độc lập

Để tự tạo recipe từ công việc thật, role phải có metadata rõ ràng: family `recipe_features`, `recipe_profile`, `model_revision`, safety facts và checker độc lập. Xem [verified outcomes](../README.md#verified-outcomes-and-adaptive-recipes) và [ví dụ task](../examples/produce-and-check.roles.json) để hiểu role/acceptance; ví dụ task cơ bản không tự bảo đảm có đủ metadata cho recipe.

Chuỗi dữ liệu:

1. Producer làm trong scope được giao.
2. Checker độc lập kiểm tra acceptance. Host chạy immutable profile và lưu exit/criterion/artifact hash.
3. Host đóng băng đề xuất recipe; Large đánh giá checker và phạm vi trước đăng ký.
4. Auto-evidence chỉ lấy verified non-learned outcomes phù hợp; không lấy model tự nói xong.
5. Recipe đủ gate mới được review promotion; audit theo policy hiện hành.

Provider lỗi, schema lỗi và hành vi sai là các loại khác nhau. Checker không xuất proof hợp lệ thì giữ `unknown`; unknown/failure có thể suspend recipe, không được bỏ qua để đủ điểm promotion. Kết quả chạy bằng recipe không tự biến thành training evidence cho chính nó.

Không nhập các bản sao gần giống như nhiều đơn vị độc lập. Không coi số unit, token success hoặc `COMPLETE` là chứng nhận chất lượng production. Chi phí không xác minh được phải hiển thị unknown, không tự coi bằng0.

## 9. Copy rule cho AI ngoài tối ưu rồi dán lại

### Cách tương tác

```text
/crew rules
```

Chọn:

- `export policy`: chính sách vận hành project.
- `export recipe`: nhập recipe ID lấy từ `recipes status`.
- `import optimized packet`: dán toàn bộ JSON AI trả về và xác nhận đưa vào queue.

Editor export hiển thị JSON để copy; không tự gửi tới dịch vụ AI ngoài. CLI là đường phổ quát nếu terminal/editor không tiện copy.

### Copy bằng PowerShell

```powershell
node "$src\bin\crews-omp.mjs" automation export --project "$project" --json | Set-Clipboard
```

Paste vào AI khác, cùng lời yêu cầu:

> Tối ưu rule này theo mục tiêu của tôi. Chỉ sửa phần `proposal`. Giữ nguyên mọi trường còn lại, đặc biệt `format`, `version`, `export_id`, `base`, `schema` và `constraints` nếu có. Không thêm code, lệnh shell, quyền file hoặc evidence giả. Trả lại toàn bộ JSON, không thêm lời dẫn.

Lưu JSON nhận lại vào `optimized-rule.json`, UTF-8. Có thể dùng clipboard:

```powershell
[System.IO.File]::WriteAllText((Join-Path $PWD "optimized-rule.json"), (Get-Clipboard -Raw), (New-Object System.Text.UTF8Encoding($false)))
node "$src\bin\crews-omp.mjs" automation import --project "$project" --request .\optimized-rule.json --yes --json
```

Một JSON object hoặc một fenced block `json` được hỗ trợ. Không dán kèm bài giải thích. Lệnh ghi ở trên dùng UTF-8 không BOM, phù hợp cả Windows PowerShell 5.1. Nếu lưu bằng editor, chọn UTF-8 không BOM.

### Export một recipe bằng CLI

Tạo `export-recipe.json`:

```json
{"kind":"recipe","recipe_id":"RECIPE_ID_FROM_STATUS"}
```

```powershell
node "$src\bin\crews-omp.mjs" automation export --project "$project" --request .\export-recipe.json --json | Set-Clipboard
```

### Quy tắc packet

`crews-rule` version1 là **đề xuất có thể mang đi**, không phải quyền thực thi:

Importer nhận packet trực tiếp hoặc kết quả export đầy đủ dạng `{"changed":false,"packet":{...}}` mà `/crew rules` hiển thị. Nếu copy cả kết quả này, chỉ sửa `packet.proposal`; giữ `changed:false`. `version:1` nằm trong `packet`, không cần thêm version ở lớp ngoài. Envelope không được chứa trường phụ hoặc packet lồng nhiều lớp; mọi kiểm tra revision/context và review Large vẫn áp dụng.

- Policy: `proposal` là toàn bộ policy được schema hỗ trợ.
- Recipe: chỉ sửa `cue`, `lesson`, `recipe_steps`, `negative_examples`. Invariant/checker/model/evidence không được thay.
- Hệ thống giữ snapshot gốc tại project export. Sai version, thay context, packet từ project khác hoặc base đã thay đổi sẽ bị từ chối.
- Nếu stale, export lại và nhờ AI áp ý tưởng tối ưu vào proposal mới; không sửa hash/ID để ép nhập.
- Dán giống nhau khi đang chờ không tạo task trùng.
- Paste chỉ tạo queue. Large có thể chấp nhận, điều chỉnh lại policy hoặc từ chối.
- Recipe guidance được duyệt tạo candidate version mới, không kế thừa trạng thái active/evidence; version cũ bị suspend.
- Rule exact-classification cũ, raw prompt và code không thuộc định dạng này.

**Trước khi gửi AI ngoài:** đọc guidance text để bỏ thông tin nhạy cảm. Export không tự mang key/receipt/raw source, nhưng nội dung người dùng đã ghi trong cue/lesson có thể chứa dữ liệu riêng. Không có cơ chế tự gửi dữ liệu ra ngoài.

## 10. Cập nhật, máy mới và sao lưu

### Cập nhật clone

Khi không có thay đổi riêng cần giữ:

```powershell
git -C "$src" pull --ff-only
node "$src\bin\crews-omp.mjs" setup --python python --json
node "$src\bin\crews-omp.mjs" doctor --json
```

Nếu `pull` từ chối vì có thay đổi local, giữ lại thay đổi và giải quyết trước; không dùng reset/force để mất dữ liệu. Restart OMP sau cập nhật. Setup lặp lại giữ installation identity và disable đã chọn. Policy/code đổi có thể làm run cũ stale.

### Đổi máy hoặc tài khoản

Cài OMP/provider/Python, clone và chạy setup như máy mới. Không cần private key cũ. Không copy `runtime.json`, venv, ticket hoặc toàn state để biến máy mới thành máy cũ. Binding local phụ thuộc account/máy/vị trí state; sao chép identity cũ không tự cấp quyền.

Muốn mang ý tưởng rule: export packet tại máy mới, chuyển **proposal tối ưu** vào packet mới và để Large review lại. Không mang số liệu evidence hoặc trạng thái active giả sang.

### Dữ liệu local

Vị trí mặc định Windows: `%USERPROFILE%\.crews-omp`. Named profile và `--state-dir` dùng vị trí khác; dùng cùng profile/state cho setup và thao tác sau đó. State có history/evidence/policy, không phải file để commit lên Git. Không chia sẻ `learning.key`, provider credentials, private keys, DB hoặc session logs.

Sao lưu state khi OMP/workers đã dừng để tránh copy DB/WAL thiếu nhất quán. Sao lưu không thay thế việc revalidate trên máy khác.

## 11. Tra cứu, dọn dữ liệu và gỡ cài

Trong OMP: `/crew status`, `/crew history`, `/crew report`, `/crew reload`, `/crew recipes`, `/crew learning`. CLI luôn có `node "$src\bin\crews-omp.mjs" help` khi `crews-omp` chưa nằm trên PATH.

Dọn storage:

```powershell
node "$src\bin\crews-omp.mjs" storage status --json
node "$src\bin\crews-omp.mjs" storage cleanup --dry-run --json
node "$src\bin\crews-omp.mjs" storage cleanup --yes --json
node "$src\bin\crews-omp.mjs" storage compact --yes --json
```

Đọc preview trước khi xóa. Compact cần idle; busy thì dừng việc khác rồi thử sau. Không xóa DB/key/ticket bằng tay để tiết kiệm chỗ hoặc chạy lại task.

Gỡ registration, giữ state và provider credentials:

```powershell
node "$src\bin\crews-omp.mjs" uninstall --dry-run --json
node "$src\bin\crews-omp.mjs" uninstall --json
```

Migration/rollback là luồng khác; xem [Existing installs](../README.md#existing-installs-upgrades-and-removal). Không dùng rollback để reset cap/retry hoặc làm receipt cũ hợp lệ lại.

## 12. Xử lý lỗi thường gặp

| Triệu chứng | Việc nên làm |
| --- | --- |
| `doctor` báo thiếu model/effort | Cấu hình provider/login trong OMP và đổi Combo sang ID thực có; không sửa receipt. |
| `Routing policy changed; create a fresh plan` | Restart OMP/MCP sau update, đối chiếu đúng package/state và tạo plan mới theo scope hiện tại. Không retry plan cũ bằng cách sửa hash. |
| Local lease expired/exhausted hoặc governance queued | Mở đúng project, để agent gọi `task {automation:true}`. Governance có thể review dù lease thường hết hạn. |
| Policy pause/denial/malformed | Đọc events và kết quả review. Sửa nguyên nhân; enable chủ động chỉ yêu cầu đánh giá lại, không ép approve. |
| `prior role evidence stale` | Artifact đã đổi sau kiểm chứng; reconcile thay đổi và tạo check mới, không đổi lịch sử evidence. |
| Run đang admitted nhưng host đã dừng | Dùng recovery có xác nhận, chỉ khi host thực sự chết. Không xóa hàng DB hoặc tự replay. |
| Rule stale/foreign/immutable context changed | Export mới từ project đích, chỉ chuyển proposal sang packet mới. |
| Recipe không export được vì thiếu reviewed context | Không có đủ authority gốc để dựng version an toàn; tạo recipe qua luồng task/checker hiện hành trước. |
| State copied from another account/location | Cài local identity mới, không sửa account hash để nhận quyền cũ. |
| `init requires two NEW key paths` / `EISDIR` | Luồng ký nâng cao nhận tên file, không thư mục; chế độ mặc định không cần ký nên bỏ qua bước signer cũ. |
| Storage busy | Đợi task/DB reader kết thúc, không xóa WAL bằng tay. |

## 13. Giới hạn cần hiểu

- Local-account trust không phải sandbox. Chương trình tùy ý cùng tài khoản có thể sửa state/code; muốn chống trường hợp đó cần OS isolation.
- Large được quản lý policy hỗ trợ, không toàn quyền máy tính. Task scope, receipt, checker và dữ liệu lịch sử không do model tự thay.
- Auto review có thể tốn token/tiền. Quota review không phải trần USD; provider metadata giá0 không chứng minh miễn phí.
- Khi OMP đóng, không có dịch vụ nền tự chạy task/gia hạn. Mở lại sẽ tiếp tục theo host state.
- Không bảo đảm model-equivalence hoặc độ đúng production chỉ từ smoke. [Verification](../VERIFICATION.md) phân biệt kiểm chứng fixture, native thực và giới hạn chưa exercise.

## 14. Workflow SDLC opt-in

Mặc định `baseline`; chỉ chọn `profile:"sdlc_cost_aware"` khi tạo workflow mới. Không đổi main model, Combo hay effort. `stage` chỉ mô tả giai đoạn; `need` mới quyết định route.

CLI: `crews-omp workflow prepare|status|next|recheck|recover|attempts|evaluation --project PATH --request FILE [--yes]`. MCP dùng `crew_runner`. Manifest gồm `task`, `authority:{read,write,commands}`, `invariants`, `max_calls`, `nodes:[{id,stage,depends_on,roles,answers}]`; request có `slot`, `session`. Prepare/next/recheck/recover cần xác nhận. Dispatch từng reference `next` qua `task {crew:...}`; tối đa hai child độc lập, không tự chạy benchmark.

Packet scout tối đa8KiB/32source refs, có hash/line range và unresolved. `needs_more_context` yêu cầu đọc lại nguồn trong scope đã cấp; không biến summary thành authority. Checker không nhận kết luận producer. Workflow kiểm tra read/grep/glob grants và symlink; shell đã cấp vẫn là trusted code, không phải OS sandbox.

Check fail: repair/escalate producer rõ lý do; sau sửa gọi `workflow_recheck` với `node` checker. Recheck tốn call budget nhưng không ăn quota hai lần sửa producer. Hai Medium repair cùng criterion thất bại sẽ chặn Medium tiếp; rename/reorder không xóa lịch sử. Crash reservation dùng `workflow_recover` với node; nếu đã có orphan plan phải chỉ đúng `run`. Owner còn sống hoặc run đã chạy bị từ chối, không replay ngầm.

Evaluation nhận wrapper `request` với operation freeze/evidence/attest/report. Freeze cần chữ ký operator; keyless governance không tự ký evidence. Với `evaluation_mode:"quality_only"`, chỉ kiểm quality và latency từ host ledger, không cần giá hoặc accounting tiền; `money_status:not_evaluated`. Bỏ mode thì giữ monetary gate cũ. Snapshot giữ cả file ban đầu sẽ được sửa, profile/model/policy/environment từng arm. Thiếu corpus/receipt/independent behavior luôn `NO_GO`. Portable export pin revision workflow; sửa proposal không cấp scope hay quyền rollout.
