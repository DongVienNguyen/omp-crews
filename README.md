
## Visual policy control

Edit model IDs without hand-editing JSON:

```text
crews-omp policy show --json
crews-omp policy set --provider local-gateway --haiku small-v2 --sonnet medium-v2 --opus large-v2 --json
crews-omp policy reset --json
```

These commands write only active state `policy.json`; they never write credentials or OMP `models.yml`. Effort remains controlled by seat policy and visible before planning:

```text
/crew status
/crew test <canonical-role-json>
```

`policy set` changes provider/model bindings and invalidates old plan bindings. Create fresh plans after changing it. Values are validated as distinct bounded identifiers. Use `crew_preview` for a no-spawn effective seat preview.
