# crews-omp

Portable OMP Crews plugin. Policy-gated planning, per-role classification, native model/effort receipts, scoped tools, stale-artifact refusal, and isolated Python runtime.

## Install from Git

Requires OMP native plugin discovery, Node.js 20+, Python 3.12+, and OMP provider credentials configured separately. Windows x64 is verified; other OS support is unverified.

```text
omp plugin install https://github.com/DongVienNguyen/omp-crews.git --scope user
```

If the installed OMP version does not accept Git installation, clone and link the checkout:

```text
git clone https://github.com/DongVienNguyen/omp-crews.git
omp plugin link <checkout> --scope user
node <checkout>/bin/crews-omp.mjs setup --python <python.exe> --json
node <checkout>/bin/crews-omp.mjs doctor --json
```

Restart OMP after install, migration, upgrade or package changes. Do not also add `extension.ts` manually to `config.yml`; duplicate owners can intercept task spawns twice.

Current OMP rejects direct `.tgz` paths as plugin directories. Extract a tarball into a permanent directory, then run `omp plugin link <extracted>/package --scope user`.

## Lifecycle

```text
crews-omp setup --python <python.exe> --json
crews-omp doctor --json
crews-omp migrate --dry-run --json
crews-omp migrate --json
crews-omp rollback --backup <state>/backups/<snapshot> --dry-run --json
crews-omp uninstall --dry-run --json
crews-omp uninstall --json
```

Setup provisions an isolated locked Python runtime. It never copies credentials, installs into system Python, or downloads Python implicitly. Migration requires the package linked to the active OMP scope and removes only owner-verified legacy registrations. Modified or unknown files refuse migration. Rollback validates owner/profile/hashes and refuses changed files. Uninstall retains state, history, policy and credentials; it removes only owner-marked registration. `--offline` requires an existing valid runtime or `CREWS_OMP_WHEELHOUSE`.

## Model and effort policy

Edit active state `policy.json`; no credentials belong in this file:

```json
{
  "provider": "9router",
  "models": {
    "haiku": "code-seek",
    "sonnet": "code-sol",
    "opus": "code-astra"
  }
}
```

Validated effort bands remain policy-controlled:

```text
Sonnet/Low    -> Seek/High
Sonnet/Medium -> Sol/Low
Sonnet/High   -> Sol/Medium
Sonnet/XHigh  -> Sol/High
Sonnet/Max    -> Sol/XHigh
Haiku         -> Seek/High
Astra         -> difficulty Low/Medium/High
```

Provider/model IDs must be distinct bounded identifiers. Changing policy invalidates old plan bindings; create fresh plans. Main chat model remains unchanged.

## Preview and classification

Use `/crew status`, `/crew test <canonical-role-JSON>`, `/crew history`, `/crew reload`, or `crew_preview`. Preview never creates a plan, ticket, child or write authority. Semantic classifier mode is `off` by default; `shadow` and `recommend` are explicit opt-ins with bounded timeout/output/cache. Deterministic facts run first. Missing facts remain unknown; classifier output cannot invent scope, commands, criteria, model or credentials.

Canonical intake requires role name, kind, mission, deliverable, scope, commands, acceptance/criteria, divisible/specificity and explicit classification for unresolved need/difficulty. Intake creates a validated plan; dispatch returned crew references only. Bad plans block ordinary fallback.

## Development and verification

```text
npm.cmd pack --dry-run --json
node --test tests/packaging.test.mjs
```

Package assets exclude runtime state, credentials, SQLite files, backups, model config and personal paths. `VERIFICATION.md` records actual checks and limits. `NOTICE` retains upstream licensing attribution.

No public MCP registry claim, Linux/macOS acceptance, full product acceptance or real-task quality/cost benchmark is implied.


## Model policy commands

```text
crews-omp policy show --json
crews-omp policy set --provider local-gateway --haiku small-v2 --sonnet medium-v2 --opus large-v2 --json
crews-omp policy reset --json
```

Policy updates write only state policy.json. Credentials remain in OMP. Create fresh plans after changes; old tickets refuse mismatched policy. Use `/crew status`, `/crew test <role JSON>`, or `crew_preview` for no-spawn preview.
