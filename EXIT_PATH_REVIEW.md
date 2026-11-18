# Stop-loss and profit-target evidence review

Outcome Review / Learning owns this read-only analysis of the existing
Intraday Profit Protection and Overnight Hold Decisions backlog. It adds no
daily job, order instruction or policy setting. Historical inputs remain
immutable; derived reports live under `reports/exit_path_review_20261106*`.

## November 6 findings, through the November 5 statement

Completed output: `reports/exit_path_review_20261106_complete/review.md` and
`review.json`. Scanned all 10,472 in-scope bundles across 28 recorded sessions,
September 25-November 5. Ten corrupt bundles are identified with checksums;
originals are preserved. This is actual-trade option-price evidence, not
underlying-stock returns.

- Of 156 closed long-entry groups, 93 included a stop sale and 81 of those
  lost money. The median gross return of the 93 stop-containing groups was
  -13.3%; seven lost more than 20%. These are actual combined group returns,
  not a claim that every sale in a group was a stop or that gaps were avoidable.
- All 81 losing stop groups have later sampled quotes before the earlier of
  the fifth subsequent session endpoint or November 5. In 55, bids eventually
  reached entry again; 15 reached the original target. But 80 also showed a
  further decline after sale. Among the 55 recoveries, 35 had an observed bid
  more than 20% below entry before recovery. Recovery does not prove that
  holding or widening the stop would have paid; observation windows vary and
  incomplete paths cannot yield recovery probabilities.
- There are 129 mature five-session windows with median 89.8% contract-minute
  coverage. None passes every preset qualification: every window has at least
  one gap longer than five market minutes. Missing October 14/22 sessions,
  scan pauses and rotating contract collection remain evidence gaps. The
  sparse replay does not establish a production winner.
- The sparse replay's target-distance x1.25 hypothesis improved modeled net
  dollars versus static original OCO levels by $360.75 in training (57 groups)
  and $456.50 in the later holdout (32 groups). At $0.05 slippage those benefits
  were $340.75 and $448.50; removing each period's best improvement left
  $238.75 and $354.25 under the $0.01 model. Both modeled baseline cohorts were
  losing, unlike the full actual-trade population. This is an exploratory lead
  on letting winners run, not an estimate of what the actual account would earn.
- Fifty-three shorter entry-to-actual-sale paths qualify for earlier-sale
  overlays: 28 training and 25 holdout. This subset has 11 winners, 42 losers,
  and actual net -$2,297.79, versus +$4,067.52 for all 156 closed groups. It is
  not representative of the full book. Tighter stops changed profit relative
  to the original-level overlay by -$386.29 training / +$232.78 holdout; the
  trailing rule changed it by $0 / -$297.04. Neither is consistently superior.
  Breakeven activation provided no incremental change versus the original-level
  overlay in this sample. Comparisons to actual fills are separately reported;
  the static OCO overlay itself differs materially from actual execution.

No blanket tightening, widening, trailing or confidence-based policy is
validated. Keep existing production and frozen shadows unchanged. The useful
next hypothesis is preserving more upside without widening downside, followed
by a matched prospective exit test once collection covers the required paths.
It is not authorization to add another funded shadow now.

## What is compared

Start with actual post-September-25 long-option opening fills, including
closed and still-open groups. Use the exact option contract, actual quantity,
entry price and entry fee. Recommendation links remain explicitly inferred
from contract and time. Separate actual broker-exit diagnostics from modeled
alternative exits.

The replay uses a common endpoint one minute before the close of the fifth
subsequent NYSE session. This lets wider stops continue beyond the actual sale
without conditioning every alternative's holding period on the actual outcome.
It is a controlled exit diagnostic, not the existing funded shadow lifecycle.
The static original OCO levels are the comparison reference, not a full replay
of daily portfolio reviews or the production profit-protection ratchet.

Eight rules are specified before viewing results: original levels, stop
distance multiplied by 0.75 or 1.25, target distance multiplied by 0.75 or 1.25,
breakeven activation halfway to the target, trailing protection after reaching
three quarters of the target distance (retain 75% of peak profit), and stop
distance multiplied by 1.25 for Research Score >=90 or 0.75 otherwise.
Research Score is not calibrated confidence; the last rule is only a hypothesis.
Wider-stop research does not authorize exceeding the live risk backstop.

## Evidence boundaries

Scan every in-scope immutable compressed archive bundle, not only recent
sessions. Independently reject zero bids, invalid/crossed markets, stale quotes,
future timestamps and delayed feeds. Repeated broker timestamps count once.
Require both receipt and broker quote times after the actual entry. Retain
corrupt-file identities and source checksums without repairing original files.

Coverage-qualified sampled paths need >=95% expected market minutes, no more
than five consecutive missing market minutes, and entry/endpoint observations
within two minutes. Even these are sampled paths, not tick-complete execution.
Sparse paths get a separately labeled diagnostic table and cannot select a
policy. A common observed endpoint is required for all rules, including rules
that would have exited early, to avoid selectively including successful exits.

Stops execute at the first observed triggering bid minus adverse slippage,
not the trigger price. Targets require bid headroom for slippage. Endpoint
sales use bid minus slippage. Test $0.01 and $0.05 per share slippage with a
$0.70 per-contract exit fee. No interpolation, replacements, cash recycling or
guaranteed fills. Position size at the bid is not known.

Training entry dates end October 21; training paths must also mature by then.
Later entries are a separate holdout. Cross-boundary training outcomes are
purged. Sparse evidence is never promoted merely because it produces a larger
number. Tables include net dollars, profits sacrificed versus improvements,
baseline winning dollars retained, worst trade and realized-only event
drawdown. That drawdown excludes open marks and is not portfolio drawdown.

## Reproduction

Run `.venv\Scripts\python.exe src/exit_path_review.py --attribution
reports/broker_attribution_20261106/post-september-changes/attribution.json
--archive data/processed/intraday_option_paths --output reports/NEW_DIRECTORY`
as one command. Output directories are exclusive. A later source revision can
reuse the saved `quote_projection.json` with `--projection` instead of
`--archive`; it checks attribution identity and carries the source manifest.
No provider API or credential access is required.

## Next validation

Any proposed exit policy needs a sufficiently observed chronological sample,
call/put and date stability, slippage and largest-improvement sensitivity, and
a forward matched test including funded exposure and open-position drawdowns.
Post-stop recovery examples alone cannot establish that wider stops improve
returns: a path can recover and also suffer a much larger loss first.

Record as an evidence dependency: verify exact actual-trade contract collection
during daily scans and through the full research endpoint, including missing
invocations and corrupt-file visibility. Existing broad/SPY shadow priority
collection does not certify historical actual-trade coverage. Fix collection
in an isolated observational sidecar if needed; do not change either frozen
experiment or manufacture missing past minutes.
