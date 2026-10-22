# Verification — crews-omp 0.4.0

## Verified adaptive classification acceptance

- Current classifier uses the Large Combo for unresolved classification:true roles, recommend default, capped512 output tokens/30000ms. Deterministic/explicit classifications bypass teacher. Large configured effort honored; main chat unchanged.
- check_learning.py covers 3train+2disjoint holdout, duplicate/cross-policy units, conflict/suspension, safe facts, policy/context/project invalidation, privacy bytes/SQLite integrity, cap/purge/mode reset, independent feedback only. Exact literal input fingerprints prevent command/string whitespace conflation; no raw task/evidence/source persisted in learning DB.
- check_adaptive_classifier.mjs exercises actual Python bridge: five independent labeled observations, explicit activation,18local classifications, tenth-hit fresh teacher audit, disagreement suspension/rollback, learned-output label refusal, storage-failure fallback, shadow noninterference. Scripted teacher proves mechanics, not real-world savings.
- Actual OMP local HTTP teacher lifecycle passes: Large/high teacher (no agent spawn) fills missing answers, Small/medium native child reads fixture, strict JSON/wire/native complete; observation1, labels0. Existing native/local routing checks remain passing.
- Actual configured-provider smoke run cc97c7e565264898b6c349fb28663fc6: Large teacher request resolved classification in8506ms with input3111/output61 tokens, then Small/low child COMPLETE with exit0 and matching receipt. Learner report1observation/0labels/0calls avoided. Backend identity behind aliases not inferred.
- Interactive OMP18.12.5 /crew learning actually displays Status, Label observation, Activate rule, Rollback rule and Mode; canceled without changes. Editor confirmation/cancel/payload tests pass. Model-facing crew_learning tool is read-only; CLI mutations need explicit --yes and project.
- Packaging suite8passed0failed, final observed223seconds: new learner lifecycle, project scope/confirmation/privacy and retained learning DB across relocation/upgrade/uninstall-reinstall, plus existing Combo/lifecycle/rollback tests. Python runtime dependencies unchanged; no extra service, model weights or SDK patch added.
- Learned rules default project-shadow, activation manual after thresholds and separate mode on. Every10active hits forces fresh audit; invalid/error/disagree suspends, never reuse old answer to hide teacher failure. Learning DB failures are advisory: valid classification can proceed with unavailable metadata, no unsafe rule fallback. Cached teacher responses do not double count usage.
- No auto-correct label from task COMPLETE or provider error, no fine-tuning, no fuzzy generalization or measured real-task cost/quality guarantee. Global setup upgrades runtime0.4.0; old state/credentials preserved, new processes required.

## Historical Combo 0.3.0 evidence
## Combo release acceptance

- Current policy is Combo Small/Medium/Large, each with user model ID and Low/Medium/High/Auto. Missing effort defaults Auto; native wire effort is lowercase. Former fixed-Seek-high/remap observations below are historical 0.2.0 evidence, not current routing.
- Five Python suites pass: classification/bilingual corpus/safety/history, canonical MCP schema, all Combo needs and boundaries, explicit effort/repair/escalation/config binding, multi-role role-local routing, stale artifact/replay/UTF-8 bridge.
- Node checks pass: classifier/cache/cancellation, failed-plan recovery, write scope, runtime ownership, dialog cancel/save/stale/unsupported validation, and local scripted HTTP provider native main->task->read->receipt lifecycle.
- Interactive OMP 18.12.5 `/crew combos` actually displayed Small/Medium/Large, provider/model fields, Auto/Low/Medium/High. Smoke canceled without writing. Policy saves serialize optimistic binding check and atomic replace; concurrent snapshot test proves exactly one writer wins.
- Native global Auto runs completed with matching wire model/effort and exit0: Small low `f08f68dcaf8349df9b9bf73374367889`, Small medium `f02ac00840f1432594c9ac5ff00d2ca2`, Small high `a08d0b2298a746daad0b332a0ebd7df5`, Medium medium `e198c55d3c9b48c1a4e3ccd23c36c71d`; Large high also COMPLETE in the same recorded native smoke. No self-reported model identity used.
- Packaging suite: 6 passed, 0 failed/skipped; real isolated Python runtime, shared/reused model IDs, missing-effort Auto, CLI invalid-input preservation, pure validation, serialized saves, profile paths, doctor/MCP, migration/rollback/upgrade/reinstall.
- Global setup upgraded private runtime to 0.3.0; doctor ready, main chat/credentials/history preserved. Old plans and tickets without the new policy binding are refused; create new plans, never auto-replay.

## Historical 0.2.0 evidence
## Exercised implementation evidence

- Python classification: 16 Vietnamese/English corpus cases, explicit precedence, tri-state safety contradictions, d1/1.001 and d2.49/2.5 boundaries, pure preview, automatic intake, project-scoped history, bridge UTF-8.
- Existing remap, repair/escalation, stale producer refusal, native replay guard, MCP schema/errors and legacy unsupported model checks pass.
- JS classifier checks exercise off/no calls, strict schema, cache/policy/context invalidation, timeout, cancellation and late reload refusal. Write-scope check verifies all hashline targets and disallows move/escape.
- Fresh native OMP source package: cold status and deterministic preview returned Seek/high without creating child; canonical intake created run 8be76323e22f4a90a24ae0b255690a78, then native Seek/high child read source and returned COMPLETE.
- Synthetic live semantic recommendation: Seek/high through OMP completeSimple, 8000ms deadline, maxTokens256; bounded lookup recommendation returned valid JSON at 7571ms with input3079/output39/reasoning9 tokens. This is capability/limit smoke, not a representative classifier-quality or cost benchmark. Global semantic mode remains off.
- Windows MCP SDK requires pywin32 due to eager client imports. Lock includes it only with sys_platform == win32; no SDK patch/fake API.

## Limits

- Windows x64 is the exercised host. Linux/macOS paths are implemented with platform APIs and dependency markers, but no non-Windows host acceptance has run; no universal OS support claim.
- Classifier success does not prove minimum-capability choice is always correct. Deterministic rules run first, unknown facts remain unknown, explicit classifications/authority stay validated. No real-task quality/cost savings claim.
- OMP extension checks are not an OS sandbox. Exact admitted commands and file scope do not prevent all shell/script-side effects.
- Native model/effort receipts prove OMP request routing and structured completion, not backend identity behind gateway aliases.
- Public Git/npm release is not performed. Local package install/reinstall is the delivery route.

## Packaging and installed-plugin evidence

- Packaging suite: 5 passed, 0 failed (final observed 89.9 seconds): side-effect-free help, profile/custom-agent config root consistency, transaction rollback, actual isolated Python venv, offline repeat, relocation, custom provider/model policy, reordered MCP semantics, owner migration refusal/cleanup, crash-prepared snapshot rollback with changed-file refusal, real 0.2.0->0.2.1 runtime upgrade preserving old venv/state/policy, uninstall failure recovery, uninstall/reinstall and actual SDK stdio/schema/catalog doctor handshake.
- Actual packed artifact extracted into a clean home with Vietnamese characters and spaces, linked through OMP and provisioned with a new private venv. Packed check_classification.py and check_lifecycle.mjs passed from that relocated package, not the source tree.
- Local scripted HTTP provider acceptance uses actual OMP main loop/native TaskTool/child read/strict JSON and verified receipt. It sends no cloud inference or user credentials. Separate offline host callback probe covers failure recovery, canonical intake, one-spawn ticket, model drift, tool scope and replay refusal.
- Global installation migrated to native plugin with an owner-file snapshot under the active state backups directory. Old extension/MCP/managed copies removed only after native link confirmation; state history retained. Doctor reports ready.
- Actual global plugin model receipts: Seek/high run d04b6ae2ab844744875ecd1f9042ef13; Sol/low run 0ac96ffddecb41649cec83bdc70aee03; Astra/low run 713d00b64fdb46c6a23575435801c054. All completed with matching wire provider/model/effort and native exit0.
- Current OMP does not accept direct .tgz plugin install: extract then link the permanent package directory. No unsupported install command is claimed. Windows tar.exe failed Unicode paths; Python tarfile stdlib extraction succeeded.
- Full generic-spawn auto-routing is intentionally not implemented: canonical intake owns exact tool-call identity and authority; ordinary/named/speculative/eval paths remain unchanged/no-remap and cannot escape a failed plan. No FIFO correlation guessed.
- Native OMP currently requests strict output but does not expose structuredOutput metadata in every returned row. Completion validates parsed JSON status/evidence plus native/wire receipts; this is not a claim of provider-enforced JSON-schema validation.
- Semantic global mode remains off. The corpus/lifecycle proves deterministic behavior and safety, not a paired real-task quality/cost benchmark. Semantic shadow/recommend requires explicit opt-in; it was exercised only in isolated synthetic smoke.
- Final lifecycle review issues corrected: transactional uninstall/relink recovery, explicit validated snapshot rollback, platform-correct config root/path comparison, semantic MCP equality, sanitized pip errors, runtime owner/profile validation. No unrelated automatic data cleanup added.
