# Signal and option-structure research

Implemented November 4, 2026 at Brian's request. Owner: Outcome Review /
Learning; contract selection owns candidate definitions. This is a separate
prospective research harness. It is not another funded portfolio, production
strategy, or modification to either frozen shadow experiment.

## Questions and scope

1. Does the underlying move in the signal's direction, before option pricing?
2. Would higher-delta or later-expiration contracts express the same thesis
   better than the selected outright option?
3. Does a debit vertical reduce losses/capital at risk enough to justify its
   capped upside and additional costs?
4. Later: would a defined-risk credit vertical improve the same directional
   thesis? Code supports this, but the default configuration leaves it off.

Stock-only attribution is a direction-adjusted underlying bid/ask price-return
diagnostic. Bearish observations are not a simulated short-stock portfolio:
borrow, dividends, financing and unlimited short-stock risk are not modeled.
It must not be ranked as a funded account against the option studies.
Calendars, diagonals, condors, uncovered selling and automatic strategy
promotion are not implemented.

## Frozen initial research protocol

`research/structure_research/settings.json` is the independently versioned
configuration. At most two distinct tickers per session are selected from
normal allocated recommendations by forward score, with ticker tie-break.
The bounded sample is not the full engine universe. The exact recommendation
ID, committed CSV checksum, research-policy fingerprint and any production
risk-overlay version are preserved. Repeated signals remain separate paired
observations, not independent evidence of a new stock thesis each day.

Each signal gets its selected outright option as control. Alternatives:

- Higher delta: same expiration and direction, absolute delta 0.55–0.75,
  closest to 0.65 and greater than the base delta.
- Later expiration: nearest later available expiry, closest delta to base.
- Debit vertical: buy the base contract and sell the nearest farther-out
  strike in the same expiration. This first recipe is not optimized to a
  predicted stock target; option-premium targets are not stock-price targets.
- Staged credit vertical: opposite option type in the same expiry; short
  absolute delta closest to 0.30 in 0.20–0.40, with a farther-out protective
  wing. Bullish put spread or bearish call spread. No missing leg is invented.

Alternative legs require positive bid, uncrossed market, at least 100 open
interest, bid/ask spread <=10% of midpoint, standard 100-share delivery and
at least 45 DTE. These are explicit research gates, not a claim of validated
parameters or a reuse of every production contract score. The forward chain
supplies both option types. Historical one-sided selector metadata is
insufficient to fabricate credit legs, and old comparison metadata lacks
open-interest qualification fields.

All available variants in a family enter at one common post-capture sample.
The underlying and every required option leg must be realtime, positive-bid,
no more than 60 seconds old, timestamped after the durable decision, with
at most five seconds between leg timestamps. Missing/stale/zero/future or
unsynchronized observations cannot create a fill. Entry expires after 30
minutes or the original session; there is no next-day/backdated entry.

Buys use ask +$0.01/share; sells use bid -$0.01/share. Each option side costs
$0.70/contract. Each variant gets a $1,000 theoretical maximum-loss budget
including modeled round-trip fees, rounded down to whole contracts.
Unaffordable variants are explicit. Credit-spread sizing uses width less
credit, not credit received. Results show both return on actual maximum
loss and on the common budget; residual cash and integer sizing matter.

The initial endpoint is five subsequent NYSE sessions, five minutes before
that session's close (including early closes/holidays). Exit must be supported
by fresh synchronized quotes in the last five minutes. If no valid exit
arrives, the window is marked missed; no later price is silently used as an
on-time fill. Missing samples are not interpolated. Paired dollar differences
require both variants to close at the same observation time. The protocol
does not simulate independent stops, targets, assignments, expiration or
rolls; those require a later lifecycle experiment before funded deployment.

These parameter values define hypotheses to compare, not optimal settings.
Five-session results do not establish long-run performance. Multiple tests,
repeated ticker signals and common entry dates limit independence; review
cohort coverage and outlier sensitivity before making a selection claim.

## Operational integration and integrity

- `daily_run.py` captures after the config comparison and SPY, after email.
  Maximum parent subprocess time is 25 seconds; each of at most two chain
  requests has a five-second timeout and uses cached authorization only.
- `run_intraday_options.ps1` gives structure and observational VIX research
  a shared ten-second auxiliary deadline after the existing collector.
  It skips this extra work while the daily
  scan runs, preserving the existing shadow priority. No scheduler change.
- One request per invocation, maximum 50 symbols. Whole families rotate by
  least-recent sample time. Unserved families are explicit budget exclusions;
  this is bounded sampled coverage, not a promise of every-minute prices.
- Quotes are acquired read-only using cached Market Data authorization; the
  new path never refreshes OAuth, sends email, or places broker orders.
- SQLite under ignored `data/processed/structure_research/` stores initial
  captures, normalized quote batches, family states and per-minute samples.
  Samples link to batch IDs. Atomic transactions and unique family/minute
  keys prevent duplicate simulated entries/exits on reruns. Initial captures
  and sample records are retained; only derived current states are updated.
- Configuration plus source checksum is frozen per family. Active studies
  fail closed if it changes. Reports exclude other-policy families from
  current-policy aggregates rather than pooling across credit activation or
  revised rules. Review/migrate or finish old families before changing policy.
- No journal, broker portfolio, capital ledger, existing shadow policy or
  ledger is modified. Both frozen fingerprint checks passed after wiring.

## Reports and commands

`data/processed/structure_research/latest.md` and `latest.json` are refreshed
by the independent capture/collector. Hindsight and weekly comparison views
read the same research state, labeled separately from portfolio returns.
No completed samples display as unavailable, not zero-performance evidence.
Reports expose unavailable legs, missed windows, sample failures and expected
elapsed market minutes versus actual sampled coverage. Net P/L is a sum of
independent risk-budgeted trade studies; there is no common cash constraint,
portfolio compounding or account ROI. Full funded-shadow validation remains
post-week-12 work.

Read-only-state report (publishes derived report files only):

```powershell
.\.venv\Scripts\python.exe src\structure_research.py report
```

Preview an existing recommendation snapshot without API calls, capture,
quotes or hypothetical historical fills:

```powershell
.\.venv\Scripts\python.exe src\structure_research.py preview --source <recommendations.csv>
```

The next fresh regular-session daily capture establishes prospective
inception. Nothing was backfilled or launched using today's old decisions.
To stop the new collection, set its settings `enabled` to false; existing
research evidence remains. This does not stop either original experiment.

Validation: 223 fixture tests passed, module compilation and PowerShell
parser checks passed, and both existing frozen fingerprints still match.
The initial report is NOT_STARTED. Live provider collection/coverage remains
to be verified after the next fresh scheduled capture; fixture validation
does not claim an observed real-market entry or spread fill.
