# SPY shadow and experiment reporting

## Independent SPY experiment

Brian approved a separate SPY trading shadow on November 1, starting with the
first eligible daily decision on November 2. It begins with $15,000 cash and
no inherited holdings. It does not compete for the broad baseline's capital
and does not apply the moderate-delta/IV challenger filter.

The daily post-email sidecar records SPY's technical research inputs and
selects call and put contracts using the existing selector, liquidity and
execution checks and a minimum 45 DTE. Both sides are research probes; the
normal opportunity rules choose a qualified call, put, watch or pass decision.
No daily trade is forced. Contract-fit holding horizon is seven days; the
existing decision-enrichment and position-review rules determine actual
thesis windows, time exits and profit protection. Corporate earnings dates
are not applicable to the ETF itself. This does not remove constituent
earnings, macro announcements, distributions or other market risks.

SPY candidates use the completed broad scan's same-session market context,
with separate recommendation IDs and immutable daily selection records.
They never enter the broad production recommendation CSV, journal, account
portfolio, email order list or broad shadow input set. Scored alternatives
and unsuccessful selections remain evidence. Existing stock scoring and
selection defaults are unchanged; optional dependency hooks let the SPY
candidate reuse the already-selected contract without requesting it again.

The isolated `data/processed/spy_option_research/ledger.sqlite` uses the same
accounting/fill engine with **one baseline-rules portfolio**. It models ask-
limited entries, bid-driven stops and targets, fees of $0.70 per contract per
side and $0.01/share market slippage. It shares sizing, daily position review,
partial exits, cash reservation, deferred decisions and restart protections.
It sends no broker orders. Missing quotes are not invented fills or returns.

SPY's selected contracts and its active orders/holdings join the existing
minute collector after the approved comparison's priority contracts. They
also remain watched during the enabled comparison's cached-authorization-only
scan-pause path. The existing collection budget is retained. Exact-contract
quote bundles remain immutable, with SPY-specific derived quote health and
portfolio summaries. Valid contract-minute counts are not claims of complete
path coverage, available order-book size or guaranteed execution.

Daily SPY selection has a 90-second parent timeout after baseline email and
the approved comparison decision. Failures are isolated and visible. Cached
authorization and the existing regular-session/calendar controls still apply.
The first actual capture remains pending Monday's run and valid authorization.

## Reports

`src/experiment_reporting.py` reads ledger state, events, valuations and
coverage through read-only SQLite connections. It never creates or resets
an account. Hindsight and weekly-learning generators include the same view
in both Markdown and JSON. Future manually prepared broker weekly recaps
should reuse this view as well.

The primary controlled comparison is broad **baseline versus moderate
delta/IV challenger**, with common inception and matched valuation timestamps.
Reports show this week and since inception: net P/L, return on starting NAV,
fees, time-weighted average deployed entry premium including entry fees,
cash, completed trades and sampled drawdown. Realized net changes and changes
in open net P/L are separate. Challenger advantage is shown in dollars and
percentage points. Weekly returns do not substitute a stale prior-week mark
when the current week has no observations.

Coverage counts, recorded gaps, stale/missing marks and settlement flags
qualify interpretation. Hindsight includes shared and different recommendation
selections with allocation actions and reasons. These describe differing
exposures; they do not claim a causal, selection-only return decomposition.
Returns include fees; listed fees are not subtracted a second time.

Actual broker statement NAV, cash and option value appear separately with
the statement date. The account has different capital, existing holdings and
manual fills, so it is not relabeled an equal-capital shadow control. The
independent SPY book has its own inception, weekly/since-start returns,
realized/open components, fees, exposure, drawdown, selections and quote health.
Its different universe is explicit. No return is shown before first forward
observations, and no historical SPY trades are fabricated.

Stock-specialist narrowing remains deferred. Neither this experiment nor
reporting changes enable a ticker shortlist or change production rules.

## Files and operation

- SPY settings: `research/spy_option_research/settings.json`.
- SPY immutable selections: `data/processed/spy_option_research/selections/`.
- SPY state: `ledger.sqlite`, `portfolio_latest.json`, `health_latest.json`,
  `processing_health_latest.json` and per-session `quote_health/` in that directory.
- Shared sampled quotes: `data/processed/intraday_option_paths/`.
- Comparison reporting: `hindsight_analytics_*.md/json` and
  `weekly_learning_*.md/json`, through their existing generators.
- Disable SPY alone by setting its `enabled` flag false. This suspends SPY
  collection/processing without liquidating positions or deleting evidence;
  subsequent missing intervals remain limitations. It does not disable the
  approved broad comparison.
- After SPY starts, a policy/dependency change is rejected. Review a new
  version/account rather than silently mixing rules or resetting history.

The November 1 additions precede both portfolios' first live observations.
The approved comparison manifest must be refreshed against these reviewed
sources before Monday; activation remains as explicitly set by Brian.
