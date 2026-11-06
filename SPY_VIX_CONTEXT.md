# VIX context for the SPY experiment

Brian approved observational VIX context on November 5, 2026. This records
conditions so we can later ask whether SPY signal outcomes differ by
volatility environment. It does not treat VIX as direction, a probability
score, or a new trading override. SPY's frozen selection, quantity, entry,
stop and target rules remain unchanged.

## Forward observations

The daily runner captures a timestamped VIX/SPY quote pair immediately before
the existing SPY capture. After that immutable SPY selection is committed,
an independent context binding records its path, checksum, selection time
and recommendation IDs. A VIX sample must have been genuinely observed
before selection and at most 120 seconds earlier. An already-created SPY
decision cannot be labeled with later VIX information.

During regular NYSE hours, the existing minute runner gives the auxiliary
research process a bounded opportunity after the priority collectors. VIX
requests occur at most once per five-minute slot; daily decision snapshots
are additional. The structure and VIX collectors share a ten-second parent
deadline. Each VIX batch has a three-second timeout, cached authorization
only and no refresh, retry, broker order or raw error-body logging. Work
is skipped while the daily scan is running. Missing invocations are gaps,
not interpolated observations.

Schwab cash-index symbol `$VIX` and SPY are requested together. Index data
uses timestamped last price, not fabricated index bid/ask. Records include:

- VIX level (index points), previous close, opening level and timestamps.
- Change in index points and percent from previous close; percent from open.
- Approximate 5-, 15- and 60-minute changes, actual reference receipt time
  through its immutable sample ID, actual elapsed seconds and points/minute.
- SPY level and changes from previous close/open at the same receipt.
- Per-series data status, sample phase, source, failures and availability.

For each horizon, the nearest prior observed sample within half the
five-minute cadence is used. The report shows actual elapsed minutes;
a three-minute observation is not silently claimed to be exactly five.
No reference crosses the trading-date boundary or uses a future observation.
Missing references remain unavailable. A realtime flag, positive level and
non-future timestamp no older than 120 seconds are required. Unknown,
delayed or stale data does not become a valid context label or a zero change.

VIX measures approximately 30-day expected S&P 500 volatility. Its percent
change is a change in expected volatility, not a SPY price return or the
IV of a selected option contract. No fixed high/low threshold or successful
regime is inferred from the first few days.

## Evidence and reports

`src/spy_vix_context.py` owns an independent ignored SQLite database under
`data/processed/spy_vix_context/`. Observations and decision bindings are
append-only; sample slots and selection dates are idempotent. Immutable SPY
selection files and its ledger are never modified. Source selection checksum
changes fail rather than silently relink. Snapshot/report code reads SPY's
ledger through a read-only connection.

`latest.md` / `latest.json` and the SPY sections of hindsight/weekly reports
show decision-time VIX context next to fully closed SPY lot counts and net
P/L, joined by exact recommendation ID. This is decision-context attribution,
not VIX captured at the eventual fill time. Unclosed/no-trade decisions have
unavailable closed-trade P/L rather than an invented zero-result trade.
No historical SPY decisions are retrospectively assigned VIX conditions.

Read current context and publish its derived report without API requests:

```powershell
.\.venv\Scripts\python.exe src\spy_vix_context.py
```

The first future regular-session capture starts this series. Before assigning
conditional success probabilities, require mature outcomes, enough independent
entry dates, payoff/cost analysis, uncertainty and out-of-sample checks. A high
win rate alone does not establish positive expectancy. This is research
evidence, not authority to retune the frozen experiment.

Validation: 241 repository tests passed; Python compilation, PowerShell
parsing and both frozen policy fingerprint checks passed. A separate
after-session provider check confirmed Schwab returns `$VIX` as an INDEX
with `lastPrice`, `closePrice`, `openPrice` and `tradeTime`; a bid/ask or
`quoteTime` is not required for that index. Both after-session quotes were
correctly classified stale. This schema check created no decision binding
or forward sample and establishes no intraday coverage yet.
