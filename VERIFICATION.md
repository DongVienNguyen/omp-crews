# crews-omp 0.6.0 — compact storage

- New dispatch stores admission/token binding and provider receipt in SQLite, no ticket/wire JSON. Final role result is stored once; earlier record files materialize only when a later wave needs upstream file context. Completion revokes admission and removes transient receipt rows.
- Admission+token creation is one transaction. Trigger-failure regression proves insertion failure leaves role planned, not stranded admitted. Late receipt insertion rechecks current token/status under write lock. Legacy JSON tickets/receipts remain valid read-only until expiry, not issued for new work.
- Storage status/dry-run are read-only; cleanup recomputes under lock, protects fresh/live/learning-backed state, archives full payloads after7days and caps summaries90days/1000runs. Learning protection holds a real readonly transaction through archive commit. Durable pending-file queue retries failed unlink even after run row archival. Symlink/unknown files preserved.
- Compact refuses active work, uses exclusive SQLite locking/checkpoints and reports actual bytes. Automatic cleanup attempts run at most daily after new plan creation, auto_cleanup opt-out supported; no automatic compact/learning purge/backup or runtime deletion.
- Storage regression covers dry-run bytes unchanged, active/live/protected observations, age/summary limits, SQL rollback, failed unlink retry, learning writer commit blocking, no-follow paths, checkpoint busy/refusal, actual reclaim. Archived history/report remain visible but cannot execute. SQLite-only lifecycle and native read/producer-write/Large-teacher flows pass.
- Global preview/snapshot then cleanup archived52 expired runs and deleted339 legacy JSON files, pruned138 expired token bindings. Records113->41, tickets141->3, wire130->1; one unknown wire JSON retained/reported. Learning DB and key byte-identical. Compact1150976->430080bytes (720896reclaimed); initial pre-migration DB1089536bytes. Retained19protected runs. Numbers are a point-in-time cleanup result, not a storage-size guarantee.
- Snapshot was SQLite backup API plus compressed legacy JSON under active state/backups, retained for recovery. Final packaging suite11passed0failed (124.7seconds), including actual provision/upgrade/relocation/uninstall/reinstall and storage admin gates. No public credentials or state included.

## Historical 0.5.0 evidence

# crews-omp 0.5.0 — bounded Small rollout

- Eight Python contract scripts pass, including bounded implementation, verified feedback/current fingerprints, role-local routing, report usage coverage, UTF-8, replay and escalation. Shadow sampling tests prove teacher disagreement never changes declared answers and preview/off/dedup/caps hold.
- Packaging suite9passed0failed; final observed169seconds includes actual isolated Python provision, profiles, report/feedback CLI, upgrade/rollback/relocation/uninstall/reinstall.
- Actual OMP local-provider lifecycle covers both read-only child and bounded producer write; parent independently parses written artifact and matches wire/native receipt. This catches the previously missing admittedWrite import, now restored.
- Cloud bounded slug smoke run f73a61b909294bf7a77ccac30684c8bb remains FAILED/BLOCKED, not PASS. Two pre-request cancellations traced to missing reasoning:true in global models metadata (restored); final same-seat repair reached model but encountered missing admittedWrite import. Guard import fixed and local-provider write reverified. Repair counters were not reset and cloud run not replayed beyond cap. No cloud coding-quality/cost improvement claimed.
- Baseline requested_combo Medium, effective_combo Small, bounded_small metadata preserves original need everyday_implementation; explicit escalation follows actual Combo. Rules require <=1.5 difficulty, explicit safe facts,1–3files and a preexisting checker outside every writer scope. This is declared capability plus independent acceptance, not automatic proof a checker is meaningful.
- /crew report separates persisted crew metrics from current-session main/native event counts. Unknown usage remains unknown. /crew learning Verified Small result requires real receipt plus explicit human confirmation; no automatic labels or fuzzy generalization added.
- Storage investigation only: no retention cleanup, SQLite purge, JSON deletion or VACUUM was performed. Storage commands previously discussed are proposals, not shipped features.

## OMP 18.12.6 post-update verification — 2026-10-22

- Host: OMP `18.12.6`; plugin inventory contains one enabled `crews-omp 0.4.0` extension and no duplicate Crews plugin. `doctor --json` reports `ready`; all Small/Medium/Large aliases present with Auto-required low/medium/high capabilities.
- All Python contracts pass after update: learning privacy/holdout/audit, classification, MCP plan schema, Combo effort/remap, role-local routing, bridge stale/replay. All Node checks pass: classifier bounds, adaptive promotion/audit/rollback, editor confirmation, write scope, runtime ownership, lifecycle.
- Packaging suite: 8 passed, 0 failed/skipped, including learning DB retention across setup/upgrade/relocation/uninstall/reinstall.
- Fresh post-update native teacher/local lifecycle pass: Large/high teacher resolves unresolved role, Small/medium child reads fixture and returns strict COMPLETE with matching native/wire receipt; learning observation stored, labels remain zero. Local provider test passes after update.
- Current global learning status: shadow, zero observations/labels/teacher calls; Combo policy all three Auto. Catalog classifier identity is Large/high. No automatic learning rule is active.
- No update-induced behavior change observed. Existing state, credentials, Combo policy and main chat model remain unchanged. Restart OMP/MCP sessions after update remains required.
