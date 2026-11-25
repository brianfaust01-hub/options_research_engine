# Friday holdings-only weekend review

Brian approved this brief on November 23, 2026. Portfolio Management owns the
decision-support view; Reporting/Operations owns delivery. This implements the
Friday portion of the existing Intraday Profit Protection and Overnight Hold
Decisions backlog. Continuous management and broker execution remain separate.

## Evidence and purpose

Actual broker holdings across eight completed weekends (September 25 through
November 16) contained 49 position-weekends and 105 contract-weekends. Their
Friday-closing-mark to Monday-exit/closing-mark contribution was +$3,095.08,
including Monday intraday price changes. Seven positions stopped by 9:45 Monday,
giving back $700.62 from Friday marks. Opening-stop frequency was 14.3% after
weekends versus 12.3% after weekday nights. These repeated observations do not
establish a weekend-specific effect or a validated selective-close rule.

The brief makes an existing holder's decision explicit. It does not scan for
new opportunities, select contracts, allocate capital, modify orders, save
portfolio/stop state, run hindsight, or advance either frozen shadow ledger.

## Contents and advisory logic

- Existing contracts and quantities, with the last broker-statement date and
  an explicit intraday holdings-confirmation warning.
- Fresh option bid/ask, midpoint open P/L, bid-based P/L, remaining dollars to
  the original reference target, giveback to the recorded stop and bid value
  exposed to weekend risk. Open P/L is gross, not realized profit after fees.
- Recomputed existing trend/momentum/regime research for held stocks and SPY.
  Yesterday's completed daily history is combined with today's complete
  session-to-cutoff OHLCV. Today's daily bar is provisional; current partial
  volume is not a full-session confirmation. Session and last-hour movement
  and volume-weighted minute typical price provide afternoon context.
- Fresh earnings-date lookup through the existing provider; expiration before
  the next session; classified shared sector/industry/theme exposure.
- HOLD when fresh daily and intraday evidence support the position and no
  review condition intervenes; CONSIDER CLOSING when both oppose it, or
  expiration/known earnings require attention; otherwise REASSESS.
- Positive gains whose giveback to the reference stop is at least the remaining
  target reward are flagged for judgment. There is no fixed 20/30/40% take-profit
  rule. These explainable prompts are advisory heuristics, not calibrated
  return probabilities or demonstrated predictors of Monday outcomes.

The user decides. A bid touching a stop is explicitly not described as an STD
trigger or a completed sale. Current broker OCO levels and holdings must be
checked before acting. No stop-price loss guarantee is implied across a gap.

## Data integrity and gaps

The report reads `data/paper_portfolio.csv` directly, avoiding the morning
review's mutable stop/peak updates. The last imported account snapshot supplies
the statement date, not live position confirmation. `LastReviewed` and file
modification time are not treated as a broker holdings timestamp. If the
portfolio changes during collection, an email is suppressed rather than sent
against inconsistent quantities.

Original targets are recovered only by exact RecommendationID and matching
contract from the immutable journal. Conflicting IDs and unavailable plans
remain unknown; the old default 75% target is never substituted. The recorded
stop may reflect the last engine review and is not a live broker order query.
The November 24 normal-portfolio repair now addresses the separate morning
original-plan propagation defect; see `EXIT_PLAN_AND_COLLECTION_REPAIRS.md`.

Only positive, noncrossed real-time option quotes no more than sixty seconds
old at report construction are used for pricing conclusions. Missing, stale,
future or invalid quotes are shown as unavailable. Missing daily/minute data
and unknown earnings dates prevent an unqualified HOLD. Stock evidence stops
at the last completed minute; its cutoff is archived separately from report
receipt time. Provider errors are captured by error type without credentials.

The earnings feed does not certify an absence of events. Unscheduled news,
macro releases, national elections and empirical cross-stock correlations are
not covered by a complete calendar/model; the brief says so. Unknown exposure
classifications remain unknown rather than being guessed. Midpoints and bids
are observations, not guaranteed fills.

Each run saves Markdown, HTML and an immutable JSON decision snapshot with
source holdings hash, recommendation IDs, reference levels, quote timestamps,
daily/minute evidence, reasons and coverage under
`reports/weekend_review/YYYY-MM-DD/`. These are report recommendations, not
claims that Brian acted. Actual actions/results still require broker records;
discretionary intent is not inferred from the recommendation.

## Scheduling and operation

Install from the project directory in normal PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup_weekend_review.ps1
```

The installer registers only `Project Stonks Friday Holdings Review`, using
the project virtual environment and existing SMTP configuration. The two Friday
triggers are noon and 3 p.m. Eastern. The calendar guard permits only one hour
before the NYSE session close: 3 p.m. normally, noon for a 1 p.m. early close.
The other trigger and holidays do nothing. November 27, 2026 is an early-close
fixture. Runs more than fifteen minutes late are skipped; recovery after the
close never sends stale advice. Windows must use Eastern Time for installation.
The date was independently checked against the
[NYSE calendar](https://www.nyse.com/trade/hours-calendars).

The task runs hidden, permits battery operation, wakes when available and
ignores overlapping invocations. The laptop/user-session requirements match
the existing daily task. Logs go to `logs/weekend_review_YYYY-MM-DD.log`.

Preview during a Friday session without sending:

```powershell
.\.venv\Scripts\python.exe src\weekend_brief.py
```

The scheduled wrapper supplies `--scheduled --send`. No preview/send bypasses
the trading calendar. A process lock and date-scoped delivery receipt prevent
duplicate sends. An interrupted/uncertain SMTP transaction is not automatically
resent: inspect that date's report and `delivery.json` first. A SENT receipt
means the SMTP transaction returned successfully, not proof of inbox receipt.

## Validation

Fixture coverage includes regular/early-close/holiday/DST windows, late starts,
current provisional thesis construction, missing bars and future daily data,
price/quantity arithmetic, adverse last-hour action, stale/zero/crossed/future
quotes, exact-plan conflicts, missing plans/events, STD stop semantics, HTML
escaping, no source-file mutation, preview isolation and duplicate/ambiguous
delivery. No test sends real mail or changes broker/production state.
All seventeen focused fixtures and all 312 repository tests passed, along
with Python compilation, PowerShell parser validation and scoped whitespace
checks. A labeled fixture preview is available in the chat outputs.

Scheduler activation must be verified from the desktop PowerShell session:
the Codex app cannot access Windows scheduler CIM/RPC resources in this
environment. The installer and runner are prepared; a successful registration
has not been claimed.
