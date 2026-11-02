# Conditions and performance monitoring

Implemented November 2, 2026. Owned by Outcome Review / Learning, fulfilling
the six-week plan's market-adaptation monitoring work. This is an observational
review system, not a validated predictor of regime changes. It has no authority
to change scores, qualification, selection, sizing, exits or experiments.

## What it checks

- **Conditions:** one canonical scan per session, with market regime, risk
  mode and breadth. Session transitions are shown without calling them
  strategy deterioration. Candidate-level delta, IV, spread and execution
  scores are summarized by date, not treated as independent market observations.
- **Input/execution context:** within the same recorded policy fingerprint,
  the latest five session medians are compared with up to twenty earlier
  sessions. At least five recent and eight reference dates are required.
  Values outside the historical range are review flags, not calibrated alarms.
  Wider spreads or weaker execution quality get distinct execution flags.
- **Directional outcomes:** the existing canonical current-era/post-September-
  24 seven-session episode definition is retained. Episode boundaries are
  constructed before the post-fix filter. CTVA pre-October-1 price-basis rows
  are excluded in both directions only in this derived view. Future/unknown
  evaluation dates and incomplete outcomes do not become mature evidence.
- **Conditional performance:** comparisons are split by exact policy lineage,
  direction, market regime, and delta/IV profile where recorded fields permit.
  Missing policy lineage is never silently treated as a compatible version.
  Within-date research-score/outcome rank relationships are also retained as
  descriptive diagnostics, not probability calibration.
- **Option results:** each broad shadow book and the independent SPY book
  is read through a read-only SQLite connection. Completed positions and their
  net results are grouped by entry date and as-known regime when available.
  Quotes, partial exits and multiple contracts are not independent closed trades.
  Net dollars per completed position are size-sensitive; these comparisons
  are not relabeled equal-capital returns or hit probabilities.
- **Operational quality:** missing/failed experiment captures, stale trading-
  session updates, stale/missing valuation marks, settlement issues, candidate
  source errors and outdated hindsight are separate from performance flags.
  The expected last completed session respects NYSE holidays, early closes
  and whether today's session has actually closed.

## Evidence and uncertainty

The performance window is **five recent distinct entry dates versus up to
twenty earlier, disjoint dates**, within each policy and condition. At least
five recent dates, eight reference dates, and twenty episodes per window are
required. These are transparent initial monitoring settings, not optimized
trading rules or guarantees of statistical sufficiency.

Mean, median, positive-outcome rate, episode counts and entry-date counts are
reported for both windows. The difference in equal-date-weighted means has
a 95% descriptive interval from resampling dates. A wholly negative interval
flags deterioration for human review. It is not a multiple-testing-adjusted
significance claim, proof of a causal condition change, or authority to pause
trading. Date clustering cannot remove all ticker/market dependence.

`NO_CLEAR_DETERIORATION` means the monitor did not detect deterioration in
that comparison. It does not mean the strategy has an edge or will remain
stable. `INSUFFICIENT_EVIDENCE` is an expected outcome for new experiments,
rare conditions and recently changed fingerprints. Prior versions remain
visible separately; they cannot validate the current version automatically.

Alert topics are tracked as new, ongoing or absent in the latest check.
Repeated report generation does not multiply the evidence. A disappearing
flag is not proof of recovery. No additional email, alert automation or
automatic configuration response was introduced.

Actual broker statements remain authoritative. Deterministic recommendation-
to-order linkage is still missing, so this monitor does not invent actual
broker option returns by condition from account NAV or heuristic matches.
No calibrated probability model is active, so probability-calibration drift
is explicitly unavailable rather than measured using score/100.

## Operation and reports

`src/evidence_monitor.py` runs as a bounded 45-second subprocess at the end
of the daily workflow, after baseline email, shadow capture and the evidence
audit. Failure cannot change trading decisions or resend email. It uses only
saved artifacts and makes no market-data request.

Outputs are isolated under `data/processed/evidence_monitor/`:

- `latest.md`: compact human review.
- `latest.json`: all cohort metrics, intervals, source identity, contexts,
  operational findings, limitations and alert-topic changes.
- `monitor_*.json`: dated monitoring snapshots, never rewritten history.

Hindsight and weekly-learning generators embed the monitor in both Markdown
and JSON. Their read-only builders do not create or reset trading accounts.
Future manually prepared broker weekly recaps should include the same view.

Run a check manually from the repository root:

```powershell
.venv\Scripts\python.exe src/evidence_monitor.py
```

## First live review

November 2's saved scan changed from Bullish / Normal / Healthy Breadth to
Neutral / Selective / Neutral Breadth. The existing hindsight file needs
refreshing, current-policy mature evidence is unavailable, and the newly
started broad shadows have insufficient closed history for deterioration
assessment. SPY's morning capture failed with TypeError and has not started;
the monitor flags this as a data/operations issue, not a strategy loss.
That separate failure still requires diagnosis/correction. No SPY return is
inferred and no lost observations or trades are backfilled.

Only reporting/monitoring and its daily invocation were changed. Both live
experiments' frozen trading-policy fingerprints remain identical to their
reviewed values. No experiment ledger is reset or rewritten by the monitor.
