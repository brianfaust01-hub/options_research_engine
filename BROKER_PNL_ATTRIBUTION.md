# Broker P/L attribution

Outcome Review / Learning owns `src/broker_performance_attribution.py`.
Brian requested an actual-dollar bridge between research recommendations and
broker outcomes on November 6. The primary review artifact is
`reports/broker_attribution_20261106/SUMMARY.md`.

The report reconstructs exact-contract economic long/short inventory FIFO
from overlapping exports (preserving maximum observed identical-fill
multiplicity), reconciles ending holdings, itemized fees, account fee
remainders and NAV changes. Actual oversells become short positions even
when the broker labels the sell TO CLOSE. Starting positions are measured
from baseline marks for period contribution, separately from full-trade P/L.
Account snapshots provide an independent realized/unrealized/fee identity.

Projected journal fields link pre-entry recommendations by exact contract
and time, without reading gigantic comparison payloads into memory. Matches
are inferred because broker exports lack recommendation IDs. Multiple
same-day matches, duplicate-ID conflicts and unavailable plans are explicit.
The journal is checksum-checked for changes during projection. No later
recommendation is assigned to an earlier fill.

Per-unit evidence retains the original entry limit, stop, target, actual
entry/exit prices and order types, concurrent quantity variance, scores and
policy lineage. Comparisons to original plan prices do not establish actual
amended broker orders, stop slippage or guaranteed alternative execution.
All errors and gains/losses remain in primary account P/L. Reviewed error
overlays are not used to exclude unfavorable trades.

An optional hindsight source joins mature seven-session stock outcomes to
fully closed new-long entry groups by matched recommendation ID. This shows
where stock direction and option dollars disagree, not a causal decomposition
or a replacement for the actual P/L identity.

Example from repository PowerShell:

```powershell
.\.venv\Scripts\python.exe src\broker_performance_attribution.py `
  --statements 'C:\Users\brian\Trading_systems\Stonks Account Summary' `
  --beginning '2026-09-25-AccountStatement_EOD.csv' `
  --ending '2026-11-05-AccountStatement.csv' `
  --hindsight 'data\processed\research_hindsight_20261106_113312.csv' `
  --output 'reports\broker_attribution_NEW_RUN'
```

The output directory's files must be new; existing reports are not silently
overwritten. A nonzero unexplained NAV residual is displayed as UNRECONCILED,
not repaired. Raw statements, journal, portfolio, capital/adjustment ledgers
and trading/shadow policies are never modified.
The current YTD/fee identity supports same-calendar-year windows; cross-year
requests fail explicitly pending year-boundary accounting.

Next evidence priorities: continue regular statement reconciliation; capture
exact recommendation/order/fill/cancel IDs prospectively; collect amended
exit-order history; compare calibrated actual option payoff/risk and costs
by policy/entry-date cohort; wire the dollar bridge into readiness reporting
after that review. A paid-price reference counterfactual is not an engine-
only return and a positive paper-account gain alone is not promotion authority.
