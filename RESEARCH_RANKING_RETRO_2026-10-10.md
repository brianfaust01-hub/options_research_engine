# Research Ranking Retrospective Replay — 2026-10-10

**Cohort:** 104 matured post-directional-fix seven-day thesis episodes
**Recommendation dates:** 2026-09-24, 2026-09-25, 2026-09-28, 2026-09-29
**Status:** read-only counterfactual; no production decision changed

## Results

| Daily selection | Policy | N | Win rate | Average return | Profit factor | Worst return |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Top 3 | Legacy | 12 | 58.3% | +0.52% | 1.48 | -4.64% |
| Top 3 | Shadow | 12 | 50.0% | +0.12% | 1.06 | -8.21% |
| Top 5 | Legacy | 20 | 55.0% | +0.34% | 1.27 | -6.20% |
| Top 5 | Shadow | 20 | 60.0% | +0.62% | 1.44 | -8.21% |
| Top 10 | Legacy | 40 | 55.0% | -0.63% | 0.71 | -19.42% |
| Top 10 | Shadow | 40 | 57.5% | +1.67% | 1.94 | -16.32% |
| Actual allocated | Production | 3 | 33.3% | -0.97% | 0.26 | -2.64% |
| Top 3 after shadow top-8 shortlist | Two-stage shadow | 12 | 75.0% | +5.95% | 4.12 | -16.32% |
| Top 5 after shadow top-8 shortlist | Two-stage shadow | 20 | 65.0% | +3.31% | 2.64 | -16.32% |

The complete post-fix population was 51.0% winners, +0.56% average return, and
1.32 profit factor.

## Interpretation

- Shadow ranking improves broad shortlist quality, especially at ten candidates.
- It does not improve the narrow top-three replay and is not ready to replace
  production selection.
- The evidence supports a layered design: research ranking creates a broad
  shortlist; contract efficiency and portfolio competition select recipients.
- Date-level top-five results were uneven. Four dates are insufficient for
  promotion.
- The 0.616 population AUC is promising discovery evidence, not proof of
  production decision quality.
- A two-stage hypothesis—shadow top-eight shortlist followed by legacy
  confidence ranking—was materially stronger, but its average return is
  outlier-sensitive and 11/12 top-three selections were puts. It is now logged
  for forward shadow evaluation rather than promoted.

Historical recommendations and original decisions remain unchanged.

## Breadth and Time-Concentration Stress Test

Holding the shadow shortlist at eight names per recommendation date and
expanding the number retained produced:

| Retained per date | Episodes | Win rate | Average return | Profit factor | Calls / puts |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 12 | 75.0% | +5.95% | 4.12 | 1 / 11 |
| 4 | 16 | 68.8% | +4.27% | 3.14 | 1 / 15 |
| 5 | 20 | 65.0% | +3.31% | 2.64 | 1 / 19 |
| 6 | 24 | 70.8% | +3.39% | 3.02 | 2 / 22 |
| 7 | 28 | 67.9% | +2.96% | 2.60 | 2 / 26 |
| 8 | 32 | 62.5% | +2.41% | 2.32 | 3 / 29 |

Breadth does not immediately destroy the aggregate signal, but date-level
performance is uneven. For all eight shortlisted names, September 24 produced
100% wins and +2.56%, September 25 produced 50% and +0.29%, September 28
produced 50% and -1.78%, and September 29 produced 50% and +8.59%. The final
date contributes disproportionate return.

The direction mix partly reflects candidate supply: the clean cohort itself is
84 puts and 20 calls, while the top-three selection is 11 puts and one call.
This is modest additional put concentration on top of a heavily put-oriented
eligible population.

The pre-fix sensitivity cohort contains 370 episodes across 12 dates, but it
cannot validate the new ranking because the asymmetric directional-confidence
defect changes the inputs and scale. A deliberately labeled replay performed
poorly: top three had 36.1% wins and -1.55% average return and selected 36 calls
and zero puts. This confirms that the attractive post-fix result is recent and
policy-dependent, not established across the full experiment.
