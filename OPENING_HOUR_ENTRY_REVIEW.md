# First-hour stock confirmation

Implemented November 5, 2026 after Brian identified a higher-priority gap
than the proposed VIX discussion: the 10:30 stock thesis used yesterday's
completed daily candles, without the 09:30–10:30 price path. Today's actual
saved input ended November 4. Current option quotes did not close that gap.

## Production behavior

Daily history still owns the multi-day thesis, SMA, RSI and MACD. The normal
`production_scan.py` entry point now runs an independently versioned
first-hour entry review before the existing oil/concentration arbitration.
It requests regular-session, one-minute stock history for the bounded
earnings-reviewed candidate pool (up to 30 tickers), up to ten holdings,
and SPY. It does not substitute 60 minute bars into a daily moving average.

The decision window is exactly 09:30 inclusive to 10:30 exclusive Eastern
on the NYSE session calendar, respecting DST and holidays. Provider minute
timestamps label bar starts; 10:29 is the final completed bar. Premarket,
10:30 and later bars are excluded. Sixty unique valid OHLCV bars are required;
missing, duplicated, malformed bars and zero total volume fail validation.

The review records opening price, 10:29 close, range, volume, return from
open, and a minute-bar VWAP approximation using volume-weighted typical
price (high + low + close)/3. This is not exchange trade-by-trade VWAP.
SPY's first-hour return supplies contemporaneous broad-market context;
it does not automatically dictate the direction of every stock trade.

Initial, explicitly versioned entry rule:

- Stock move and price-versus-bar-VWAP both agree with daily direction:
  **CONFIRMED**. Existing quality, liquidity, earnings and risk gates remain.
- Both oppose daily direction: **CONTRADICTED**; exclude the new entry/ADD.
- Mixed or flat: **MIXED**; preserve original qualification/risk decisions.
- Incomplete stock or SPY first-hour history: **DATA_UNAVAILABLE**; defer
  new entries instead of silently falling back to yesterday's indicators.
- Outside the bounded candidate review pool: explicitly not reviewed and
  cannot receive a new allocation from this overlay.

This confirmation rule is a precautionary hypothesis, not a proven edge or
an optimized threshold. It may miss recoveries and pullback entries. It
does not force existing holdings closed, loosen a stop, select inverse
contracts, or guarantee that prices remain aligned after 10:30. Entries
filled later still require live option pricing and original order limits.

## Evidence, isolation and operation

`src/opening_hour.py` owns capture and evaluation. Exact minute evidence and
source/code hashes are archived atomically before use under ignored
`data/processed/opening_hour/`. New recommendations and position-action
outputs carry separate `OpeningHourPolicyVersion`, checksum, evidence path,
stock measures and SPY context. Core daily research lineage is unchanged;
attribution must include this additional execution-overlay version rather
than pooling it with pre-overlay actual allocations.

The original research action/direction is restored after allocation, with
the rejection reason retained in the portfolio action. The frozen broad
and SPY shadows recompute allocation independently; neither imports the
overlay. Both existing frozen policy fingerprints were checked unchanged.
Historical recommendations, snapshots and broker fills are never rewritten.

The daily HTML and Markdown action brief includes a first-hour table and
explicit confirmation/data status. Older snapshots say that first-hour
confirmation was not captured, rather than inventing a review.

At most 41 symbols, eight concurrent requests, three-second request timeouts
and no retries bound the additional scan cost (roughly six request waves
at maximum timeout). Cached authorization is read once; the normal preflight
retains responsibility for refreshing Market Data authorization. Missing
authorization or provider failures are recorded without credential/error
response bodies. A complete daily run is still required; no new scheduler
or intraday re-evaluation service is introduced.

Canonical operation remains `run_daily_stonks.bat` / `daily_run.py`.
Directly running legacy `weekly_scan.py` bypasses production overlays.
Rollback removes the first-hour wrapper in `production_scan.py` while
keeping the oil wrapper and all evidence intact.

Owner: Portfolio Allocation / Entry Risk; data adapter owns minute history,
Outcome Review owns evaluation. Regression risks include partial/future bars,
delayed feeds, stale daily fallbacks, wrong put/call sign, API latency,
shadow contamination and hiding rejection reasons in the brief. Fixture tests
cover those boundaries. Live provider coverage is a separate verification
step, not established merely by the fixture suite.

Validation: all 232 repository fixture tests passed, modules compiled, and
both frozen policy fingerprints still match. A separate read-only provider
check obtained all 60 first-hour bars for SPY, AMZN, AAPL, NFLX and HAL on
November 5. SPY fell 2.37% open-to-10:30; AMZN fell 5.63%, AAPL 1.15%, NFLX
2.42% and HAL 1.53%. All four stocks were below their first-hour bar-VWAP.
AMZN/AAPL's daily calls therefore illustrate contradictions; NFLX/HAL puts
illustrate agreement. This was an after-session historical fetch, not proof
of an as-of replay, a guaranteed avoided loss or a profitable inverse option.
No production scan, email, broker order or historical recommendation was
rerun. The first scheduled live review remains to be checked operationally.

## Daily mismatch and inverse-trade research

Brian asked whether a mismatch should lead to the opposite trade. Preserve
three distinct hypotheses: original daily trade, stand aside, independently
qualified opposite trade. Do not assume that a first-hour contradiction
establishes reversal: it can also be a temporary pullback or rebound.

A future paired comparison needs prospectively selected opposite contracts,
both sides' bid/ask paths, shared decision times, liquidity, earnings/event
and risk qualification, fees, sample coverage and policy versions. Current
quote collection of original recommendations does not establish complete
opposite-contract paths. This remains research scope; no automatic trade
inversion or new opposite-direction allocation was implemented.
