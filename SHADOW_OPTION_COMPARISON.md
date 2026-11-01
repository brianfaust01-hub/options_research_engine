# Option configuration comparison — completed implementation

**Implementation complete; activation remains OFF for the planned Sunday rollout.** This replaces the earlier forecast-only proposal as the primary comparison. The probability diagnostic is disabled in the release settings.

## What will run

Two independent simulated portfolios each start with $15,000 cash and no positions at the first eligible daily decision after activation:

- **Baseline control:** existing candidate qualification, ranking and allocator.
- **Challenger:** the same inputs and allocator, additionally requiring recorded absolute option delta >0.35 to <=0.50 and IV >20% to <=40% for new entries.

The profile does not force an existing position closed solely because its delta or IV later moves outside the entry band. Both books use the shared position-review/profit-protection and capital-arbitration code for ongoing management. The filter can change selections, exposure and intentional cash; it does not replace scores with a probability estimate. Profile thresholds are a research hypothesis, not proven optima.

The actual broker account remains separate and authoritative. No broker orders are submitted, and neither simulated portfolio writes data/paper_portfolio.csv, the production journal, actual fills, capital ledger or performance-adjustment records.

## Price-driven execution

- Every working entry and held contract from either book is added to the exact-contract watch set, even if absent from the current journal. Active comparison contracts are fetched first; remaining research symbols continue rotating.
- Quotes must be real-time, within the regular NYSE session, fresh within 60 seconds, with a positive bid and coherent ask. The observation must occur after the order decision. An unchanged exchange quote timestamp may predate the order if the post-decision observation remains fresh.
- A buy limit can fill when ask <= limit. Simulated price is min(limit, ask plus the configured penny adverse slippage). It cannot pay above the limit. Entry orders expire at session close and are superseded by a new daily decision.
- A stop sell triggers at the first fresh observed bid <= stop. Its simulated execution uses bid minus modeled market slippage, including any observed overshoot. It is not assumed filled at the trigger price.
- A target sell requires bid >= target and receives the target limit, without assumed price improvement. Stop and target close the same remaining lot, so it cannot sell twice or become short.
- Daily profit protection, time exits, earnings logic where present in as-known inputs, portfolio CLOSE/REDUCE and capital competition reuse the existing review/allocator. Reviews use executable bid; reported NAV uses quote mark/midpoint. The normal broker review may use mark inputs, so this is a controlled quote-execution simulation, not a claim of identical actual broker behavior.
- Reductions preserve the remaining lot and bracket. Approved incremental ADDs remain subject to the contract cap. Replacement entries wait for pending exits to fill; prospective sale proceeds and freed position slots are never assumed available. Closing fees are reserved with cash.
- Fees are provisionally $0.70 per contract per side; market-order adverse slippage is $0.01 per share. These are explicit frozen estimates, not imported actual broker fee attribution. The same assumptions apply to both simulated books.

Full-size quote-touch fills assume sufficient size and ignore queue position. Minute samples cannot establish every intervening crossing or actual broker trigger convention. These limits remain visible rather than being represented as confirmed executions.

## Scheduling and missing data

Future daily CSVs now carry the exact recommendation IDs/timestamps and snapshot lineage from the successfully committed journal batch. No historical CSV or journal is rewritten. Missing or ambiguous lineage is rejected.

The daily sidecar records decisions after the existing email/collection flow, so it cannot change baseline trading guidance or send additional email. Decision availability uses the actual recording time, never the morning recommendation timestamp retroactively.

The existing minute launcher normally pauses broad research collection during the daily scan. When this comparison is enabled, it instead runs a small **priority-only, cached-authorization-only** collection for active comparison contracts. That path cannot refresh or rewrite OAuth tokens and avoids reading the large research journal. Priority-only samples are labeled separately and do not masquerade as full-universe collection. Missing/expired cached authorization produces visible failed-quote evidence; the daily workflow owns any normal refresh.

If held-contract marks are stale, the daily candidate snapshot is queued rather than used for new allocations. The minute path retries once all held contracts have fresh prices, recording the later decision time. Snapshots older than 30 minutes or from another session expire without new allocations. Raw quote bundles survive processing failures, which are recorded separately.

No quotes are interpolated. Missing data is never counted as a trade loss, success or zero return. Reported NAV can carry the last mark, but stale/missing flags make that explicit and block new allocation. Zero bids cannot fabricate a zero-price sale. Expired contracts requiring settlement remain flagged rather than silently assigned zero or an invented exercise value. Trading-gap measurement excludes closed hours/weekends/holidays and includes missing full sessions.

## Accounting and evidence

Canonical file: `data/processed/configuration_comparison/ledger.sqlite` (ignored by Git).

- Inputs, orders, fills, reviews and source hashes are recorded in SQLite; cash and state commit atomically across both books.
- Same-source reruns and repeated quote bundles are no-ops. Conflicting immutable inputs are rejected. Crashes cannot apply half a transaction or duplicate fills on restart.
- NAV = cash + option mark/midpoint market value. Realized and unrealized net P/L reconcile to NAV minus starting capital, including paid entry/exit fees. Liquidation NAV is also shown using bid less modeled exit costs.
- Reports include cash, positions, working orders, reserves, fees, net returns, closed-round-trip statistics, sampled drawdown, turnover and data-quality flags.
- A persisted NAV series and per-contract quote-coverage table support later evaluation. Relevant policy/execution sources, package versions and comparison-spec fingerprints prevent silently mixing policy versions after code/config changes.
- The actual broker view displays separately dated statement NAV/cash/option value. Any statement-close NAV change is explicitly not a matched intraday or cash-flow-adjusted investment return; existing capital-ledger reporting remains the source of actual performance.

Current reports: `data/processed/configuration_comparison/latest.md`, `latest.json` and `health_latest.json`. Processing failures append to processing_failures.jsonl. Original raw quotes remain under intraday_option_paths.

Export detailed evidence from repository root after the experiment starts:

```powershell
.venv\Scripts\python.exe src/shadow_comparison_runtime.py report
```

This writes derived snapshots plus events.csv, simulated_fills.csv, nav_history.csv and quote_coverage.csv under configuration_comparison/exports. It performs no market-data request or order submission. Before start it reports NOT_STARTED.

## Sunday activation

1. Review the code/artifact manifest and commit/push explicit reviewed files, preserving unrelated existing account/history changes. No whole-tree staging or Git history rewrite is required by this implementation.
2. Ensure weekly Schwab authorization is ready and the laptop/user session supports the existing scheduled jobs.
3. From a normal Windows PowerShell session in the repository, on Sunday November 1 or later:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File research/six_week_20261029/Set-ShadowRelease.ps1
```

The helper checks Eastern date, trading-comparison flags, the reviewed manifest, normalized source hashes, Python dependency fingerprint, and the enabled daily/minute jobs pointing at this checkout. It preserves the comparison/diagnostic flags and does not start a scan, send email or place an order. This app sandbox cannot query Task Scheduler's CIM service, so live job verification is deliberately part of desktop activation rather than an unsupported claim made here.

First normal session: November 2. The comparison begins at the first successfully recorded daily decision; it has no fabricated prior holdings or earlier shadow trades. Check latest.md and health_latest.json for fresh samples, separate portfolios, decision timestamps and pending/fill records.

Rollback/disable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File research/six_week_20261029/Set-ShadowRelease.ps1 -Disable
```

This preserves evidence and returns the collector to its prior broad-research behavior. It does not reset portfolios, liquidate positions or change the actual broker account. Disabling suspends simulated execution; missing intervals on any later resume remain explicit. A policy-source change requires a reviewed new comparison version rather than silent continuation.

## Week-12 interpretation

Compare control and challenger over their **same forward window**, starting at their actual common inception. Separately reconcile actual broker performance over the appropriate statement period, with different existing positions/capital and real fills explained. Do not compare a new shadow's shorter history directly against all twelve baseline weeks as though the windows match.

Net return, costs, deployment, concentration, drawdown, independent dates and regime coverage matter alongside win rate. Trade records are simulated, and partial fills/overlapping stock exposures are not independent successes. No automatic promotion or parameter tuning occurs; the previous evidence gates and explicit review still apply, and observation count alone does not prove an edge.

## Validation

**179 repository tests passed**, with successful module compilation and PowerShell syntax checks. An offline schema check also verified all 500 saved October 29 candidates against exact same-session journal IDs/contracts/prices and queued ten orders per simulated book in a temporary, explicitly historical fixture. It created no fills or forward evidence. Normal token-file renewal and unrelated authentication-helper edits do not change the frozen trading-policy fingerprint.

Fixture tests cover daily allocation, minute-feed integration, shadow-only symbols, priority during scans, cached-only authorization, deferred decisions, ask-limit touches, bid stops/overshoots, target limits, partial exits, ADD/capital guards, real cash recycling, zero bids, fees/NAV reconciliation, restart idempotence, immutable inputs, stale/future observations, session clocks, coverage, exports, rollback flags and source-version rejection.

All testing uses temporary fixture accounts and quotes. No production scan, API quote request, order, email, token-file update, commit or push was performed for validation. The deployment remains disabled.

## November 1 extension before first forward observations

Brian subsequently enabled the release. Before its first normal session,
reporting was added to hindsight and weekly learning, with matched weekly
and since-inception control/challenger results and separately dated broker
context. An independent SPY-only $15,000 simulated account was also approved,
using the same baseline rules and shared fill/exit engine. It has its own
ledger, technical qualification and inception, not the moderate-delta/IV
filter. Both-side contract probes supply research coverage without forcing
trades. See `SPY_SHADOW_AND_REPORTING.md`. The primary comparison's two
policies and parameters remain the same. Source/manifest fingerprints were
refreshed before either live ledger existed; no experiment was reset or
historical return backfilled. November 1 validation: 192 tests passed.
