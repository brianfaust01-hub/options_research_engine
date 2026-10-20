# Project Stonks — Six-Week Configuration Checkpoint Preparation

**Prepared:** 2026-10-10
**Policy era:** `PE-2026-09-08`
**Baseline checkpoint:** after six complete simulation weeks
**Decision status:** preparation only; no production configuration change authorized

## Objective

Freeze one bounded challenger at the six-week checkpoint, then compare it with
the unchanged baseline on the same subsequent recommendations through week 12.
The purpose is to improve the allocator's ability to capture the positive edge
already present in the research population without weakening liquidity,
execution, portfolio-risk, or data-integrity controls.

## Current Evidence

The October 9 hindsight refresh contains 474 matured, deduplicated,
current-policy seven-day episodes:

| Population | Episodes | Win rate | Average return | Profit factor |
| --- | ---: | ---: | ---: | ---: |
| All current-policy episodes | 474 | 55.9% | +0.63% | 1.32 |
| Allocated | 19 | 26.3% | -1.84% | 0.37 |
| No Allocation | 418 | 58.6% | +0.79% | Not frozen yet |
| Watch | 37 | 40.5% | +0.13% | Not frozen yet |

The research population has positive expectancy. The current allocation sample
is preliminary, but it materially underperforms the unallocated population.
The checkpoint should therefore focus first on ranking and capital selection,
not on broadening the universe or relaxing execution standards.

## Required Cohort Separation

The September 24 run was the first production run after the symmetric
directional-confidence correction. Pre-fix and post-fix observations must not
be pooled when evaluating the corrected scoring behavior.

| Cohort | Direction | Episodes | Win rate | Average return |
| --- | --- | ---: | ---: | ---: |
| Pre-fix | Bearish | 184 | 82.1% | +2.68% |
| Pre-fix | Bullish | 186 | 32.8% | -1.36% |
| Post-fix | Bearish | 84 | 53.6% | +0.68% |
| Post-fix | Bullish | 20 | 40.0% | +0.08% |

The pre-fix bearish results came from a directional-score defect and correlated
market windows. They remain immutable historical evidence but must not be used
to calibrate the corrected score scale. The 104 matured post-fix episodes are
useful early evidence, but the 20-episode bullish sample is not yet sufficient
for a stable call-side calibration.

## Preliminary Findings to Test, Not Production Conclusions

1. **Allocation is not capturing the research edge.** Post-fix unallocated
   episodes are 51/95 winners (53.7%, +0.71% average return), while only three
   post-fix allocated episodes have matured. The allocation comparison remains
   too small for a final rule but is the primary checkpoint question.

2. **Raw score bands are direction-confounded.** Across the full policy era,
   low Research Score and Time Edge bands appear strongest because many
   successful pre-fix bearish episodes received artificially low bullish-scale
   component scores. Global score thresholds must not be tuned from these
   pooled results.

3. **Direction is a control variable, not the optimization target.** The
   checkpoint should measure actual trade configurations after subtracting the
   average return associated with each direction. This lets delta, IV, theta
   drag, vega, horizon fit, execution, and contract quality compete on a
   comparable basis without turning the challenger into a bullish-versus-
   bearish selector.

4. **Confirmed earnings exposure is a credible risk signal.** Current-policy
   episodes with confirmed earnings are 29/82 winners (35.4%, -1.03% average
   return), versus 236/392 (60.2%, +0.98%) where earnings were not checked.
   This is a strong hypothesis, but `NOT_CHECKED` is not equivalent to
   confirmed absence of earnings. Data completeness must be resolved before
   converting this finding into a production penalty.

5. **Theta drag may matter after direction control.** In the post-fix bearish
   sample, the highest theta-drag group averaged -2.40% versus positive returns
   in the lower groups. The bullish sample is too small and shows a different
   pattern, so a global theta cutoff is not justified yet.

6. **Execution Score is not monotonic.** Middle post-fix execution bands
   outperformed the highest band. Execution quality remains a hard guardrail,
   but the evidence does not support simply increasing its ranking weight.

7. **Configuration profiles are more informative than isolated bands.** A
   broader post-fix discovery search identified two comparatively interpretable
   pairwise candidates: Research Score 90-99 with theta drag below 1% (26
   episodes, 61.5% wins, +0.81% average return, 1.76 profit factor) and absolute
   delta 0.35-0.50 with IV 20-40% (18 episodes, 61.1% wins, +0.68% average
   return, 2.22 profit factor). Both remained direction-adjusted positive in
   the early and later sample. A narrower Research Score 90-99, Time Edge
   50-59, and theta-drag-below-1% profile reached 8/12 wins and 2.58 profit
   factor, but all 12 were puts and the three-field sample is exploratory.
   These results are candidate challenger shapes, not authorized thresholds.

8. **Research Score is not presently a calibrated ranking signal.** In the 104
   corrected post-fix episodes, Research Score has effectively zero Spearman
   relationship with seven-day return and 0.519 win/loss AUC, where 0.500 is
   random. Score bands are non-monotonic: 70-79 produced 57.9% wins and +1.2%
   average return, 80-89 produced 45.8% and +1.1%, and 90-99 produced 54.1%
   and -0.5%. Within-day score quartiles were also non-monotonic. The current
   score remains useful as a candidate gate, but the evidence does not support
   treating it as a calibrated probability or primary expected-return ranking
   variable. Research-layer recalibration must precede contract-configuration
   optimization at the checkpoint.

## Checkpoint Analysis Package

At the six-week checkpoint, freeze the source dataset and run these analyses on
deduplicated executable seven-day thesis episodes:

1. Separate pre-fix and post-fix cohorts using the September 24 effective date.
2. Calculate direction-adjusted configuration returns before any combined
   ranking analysis; retain the direction-level tables only as audit controls.
   Evaluate configuration interactions as profiles rather than treating
   isolated bands as additive evidence. Begin with pairwise intersections and
   require positive results in both chronological halves; defer three-way
   searches until the post-fix sample is materially larger.
3. Compare allocated, unallocated, watch, affordability-rejected, and
   quality-rejected candidates.
4. Measure score monotonicity within direction for Research Score, Time Edge,
   Institutional Trade Score, Execution Score, and Portfolio Score.
5. Evaluate Greeks, DTE, IV, theta drag, vega exposure, spread, liquidity,
   earnings proximity, regime, and holding horizon within direction.
6. Test alternative-NAV shadow allocation and distinguish affordability misses
   from ranking misses.
7. Run regime-component ablation rather than deleting the regime model based on
   a pooled result.
8. Repeat every proposed improvement with winsorized returns and with the five
   best and five worst episodes removed.
9. Reject any rule whose apparent improvement depends on one date cohort,
   ticker, direction, or market regime.
10. Preserve the baseline and challenger outputs for every weeks 7-12
    recommendation so both policies face identical market opportunities.
11. Calibrate candidate win probabilities with date-grouped out-of-sample
    predictions. Report reliability tables, Brier score, log loss, calibration
    slope/intercept, and direction-separated results; never calibrate and score
    the same recommendation-date cohort in sample.
12. Evaluate measured 60-session, direction-adjusted return correlations among
    executable candidates and existing holdings. Compare the measured result
    with the sector/theme proxy and test incremental portfolio concentration;
    correlation evidence may not enter production allocation until the frozen
    challenger is approved.

## Bounded Challenger Design Rules

The checkpoint may freeze only one challenger. It should modify the smallest
coherent part of the allocation ranking needed to test the evidence. The
preferred design direction is a **direction-decoupled configuration challenger**
that:

- leaves research generation, contract selection, liquidity gates, entry
  pricing, stops, targets, position limits, and capital limits unchanged;
- ranks actual trade configurations using direction-adjusted evidence, with
  direction retained only to remove confounding before portfolio competition;
- is built from a coherent configuration profile (for example delta plus
  theta/IV characteristics), not a collection of independently favorable
  bands assumed to be additive;
- uses only fields already captured prospectively and available at decision
  time;
- produces a complete shadow decision record even when the baseline receives
  the paper allocation; and
- cannot change itself during the matched weeks 7-12 comparison.

The exact formula is deliberately not frozen in this preparation document. It
must be selected once the six-week dataset is locked and the required analyses
have been reviewed.

The freeze uses only outcomes already matured on the checkpoint date. Episodes
from the final baseline sessions that have not yet completed seven trading days
remain valid baseline evidence when they later mature, but they cannot be used
to retune the already-frozen challenger. This prevents look-ahead leakage while
allowing matched shadow collection to begin promptly.

## Challenger Acceptance Criteria

The challenger advances only if the matched weeks 7-12 comparison shows:

- at least 100 matched shadow observations;
- positive expected return and profit factor above 1.0;
- improvement over baseline allocation expectancy, not merely win rate;
- no material deterioration in 5% tail-loss rate or worst-case drawdown;
- stable results across calls and puts, or an explicit evidence-based reason
  to limit one direction;
- no reliance on one ticker, date cohort, or a few outliers;
- unchanged liquidity and execution guardrail compliance; and
- reproducible decisions from immutable inputs and a frozen challenger version.

## Freeze Checklist

- [ ] Complete six full baseline weeks.
- [ ] Refresh hindsight after the final week-six session matures.
- [ ] Record the exact source CSV hash and policy-evidence coverage.
- [ ] Resolve missing/ambiguous earnings-status coverage.
- [ ] Produce direction-separated calibration tables.
- [ ] Produce date-grouped out-of-sample probability calibration diagnostics.
- [ ] Audit measured candidate/holding correlation coverage and stability.
- [ ] Produce affordability-versus-quality rejection analysis.
- [ ] Complete outlier, cohort-stability, and regime-ablation checks.
- [ ] Select and document one challenger formula and version identifier.
- [ ] Add deterministic regression fixtures for baseline and challenger.
- [ ] Start matched shadow logging without rewriting historical records.

No production scoring, allocation, recommendation, or historical record was
changed by this preparation work.
