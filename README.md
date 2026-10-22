# Model and effort configuration

Edit state `policy.json` directly or use `crews-omp policy` command (when available):

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

Model IDs are user-editable, distinct, bounded identifiers. Provider and model credentials stay in OMP config, never in this file. Policy changes invalidate existing plan bindings; create fresh plans after changing it.

Effort stays policy-driven:

- Haiku → Seek/High.
- Sonnet Low → Seek/High.
- Sonnet Medium → Sol/Low.
- Sonnet High → Sol/Medium.
- Sonnet XHigh → Sol/High.
- Sonnet Max → Sol/XHigh.
- Astra follows difficulty Low/Medium/High.

Do not edit effort in task payload. Use `crew_preview` with `operation: "test"` to see effective model, requested seat, effort and routing reason before creating a plan. `crew_preview` never creates plan/ticket/child.

If you need visual control, use an OMP command/UI layer that writes only policy.json through validated fields, then calls `/crew reload`. Do not build a second model router or add model names to role prompts.
