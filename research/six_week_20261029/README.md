# Sunday option configuration comparison

Implementation and rollout: SHADOW_OPTION_COMPARISON.md at repository root.
Primary comparison: baseline vs moderate_delta_iv, each with independent $15,000 cash/positions, exact option quote fills, shared review/allocator and the same accounting model. The earlier probability model remains a separate disabled diagnostic.

Activation is OFF. On Sunday November 1 or later, after reviewed code is in place, run from a normal PowerShell session:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File research/six_week_20261029/Set-ShadowRelease.ps1
```

The helper checks code hashes, flags, date and scheduled jobs targeting this checkout. It does not start a scan or place orders. To disable without erasing evidence, append -Disable.

Live reports after start: data/processed/configuration_comparison/latest.md and health_latest.json. Detailed event/fill/NAV/coverage exports: `.venv\Scripts\python.exe src/shadow_comparison_runtime.py report`.

Full source and cost assumptions freeze at the comparison's first recorded daily decision. Change them only as a reviewed new experiment version. Actual broker fills/fees remain authoritative in their separate account ledger. Missing data never implies a fill or zero return.
