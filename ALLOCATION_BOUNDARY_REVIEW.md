# Allocation boundary evidence — November 24, 2026

## Conclusion

The cutoff excludes some genuine opportunities, but the evidence does not
establish that a blanket threshold reduction improves the complete portfolio.
The review identifies specific missed price moves and their concentration,
while showing that many otherwise qualified opportunities above the cutoff
were also unfunded because of portfolio constraints. Admission and allocation
must therefore be evaluated together. No strategy parameter was changed.

This is a refinement review against a profitable baseline. It does not presume
the existing engine needs replacement or infer that fewer trades are always
safer or more profitable.

## Population and method

Use all 43 September-25–November-24 daily runs from the previously reproduced
baseline. Compare candidates near the final 70-point admission boundary, after
the recorded two-point entry hurdle and recorded marginal portfolio penalty.
Use predeclared windows of +/-2, +/-5 and +/-10 points; do not select an optimal
window after seeing returns.

Recheck recorded initial non-score eligibility using the same contract quantity,
entry, execution, earnings, first-hour, oil and incumbent-exposure inputs.
Remove only the forward-score failure from this initial viability check.
Capital/position/concentration capacity remains a separate later decision.
The study contains 522 otherwise-recorded-viable observations in the widest
window, including repeated dates/tickers. A historical execution score is not
proof that the entire quoted size would fill.

Original IDs are used where recorded. Older observations require a unique
date/contract/entry/score inference; unresolved links remain missing. Actual
broker dollar outcomes, finalized stock-direction horizons and fixed-horizon
option quote changes are distinct evidence types.

## Main five-point boundary comparison

| Recorded outcome | Below boundary | At/above boundary |
|---|---:|---:|
| Otherwise-recorded-viable observations | 32 | 113 |
| Decision dates represented | 12 | 31 |
| New/add recommendations issued | 0 | 14 |
| Other unfunded opportunities | 32 | 99 |
| Linked fully closed actual broker cases | 0 | 11 |
| Actual closed net P/L | Not observed | +$1,157.24 |

The 99 unfunded above-boundary observations were blocked by active-position
capacity (63), aggregate stop-risk budget (24), or premium-utilization budget
(12). Lowering the admission cutoff does not remove those constraints or make
every newly admitted trade an additional feasible investment. Broker executions
are a further subset because recommendations do not guarantee an actual entry.

Finalized three-session stock outcomes have eleven mature below-boundary
episodes, five favorable/six unfavorable, averaging -0.78% directional return;
the above-boundary side has seventy-one mature episodes, forty-two favorable/
twenty-nine unfavorable, averaging +0.50%. The regimes, dates, directions and
maturity distributions differ, so this is not a randomized comparison. Matching
the same decision date and direction leaves nine groups; available stock
outcomes remain mixed. These stock returns are not option P/L and cannot
reconstruct stop/target execution.

## Exact option-price evidence and missed opportunities

The study scanned 875 compressed minute bundles only in predeclared entry/
endpoint windows, preserving one unreadable October 16 bundle as an explicit
exclusion. Valid observations require exact standard contract identity,
positive noncrossed real-time bid/ask and quote age no greater than sixty seconds.
The entry snapshot is the first available within fifteen minutes of the
recorded decision; the endpoint is the last available in the final five minutes
of the first or third subsequent regular session. There is no interpolation or
selection of a favorable intraday high. Holidays and early closes use the
exchange calendar.

For below-boundary cases in the main window:

| Endpoint | Mature endpoints | Complete price pairs | Price pairs higher | Gross midpoint change, one contract each |
|---|---:|---:|---:|---:|
| One subsequent session | 26 | 24 | 11 | +$4,344.00 |
| Three subsequent sessions | 19 | 16 | 9 | +$1,342.50 |

Six one-session and thirteen three-session endpoints remain pending; two and
three mature endpoints respectively lack complete price pairs. Missing/pending
returns are not zeros. These sums use one contract per observed decision and
are **quoted price changes, not hypothetical realized trading profits or a
funded portfolio return**. They omit executable-size uncertainty, stop/target
paths, fees, cash propagation and displaced holdings. A separate bid/ask
friction sensitivity is retained in JSON, not asserted to predict broker fills.

The positive one-session result is highly concentrated: November 19 contributes
$5,673 while the other covered dates together contribute -$1,329. META, GOOG
and GOOGL on November 19 account for $4,450; all remaining covered observations
together total -$106. Those are legitimate observed gains, not grounds for
deleting outliers, but three correlated positions on one day cannot establish
a broadly superior relaxed admission rule. GOOG and GOOGL are also two share
classes of the same issuer, not independent diversification.

The tighter two-point window has fourteen below-boundary observations: eleven
covered one-session changes total +$301, with five higher; eight covered
three-session changes total +$188, with four higher. The wider ten-point view
is retained too. The result depends on which cases and horizons are included.

### Concrete example: DIS on November 23

DIS's call had Institutional Trade Score 89.1, a ten-point Defensive deduction
and a ten-point bearish-market directional deduction, giving portfolio score
69.1 before the two-point new-entry hurdle. Its first-hour stock behavior was
confirmed in the call direction. The exact January $120 call's recorded
midpoint went from $4.15 in the entry observation to $5.675 at the next-session
endpoint, +36.7%. This is a useful counterexample to assuming all rejected
counter-market calls lacked merit. It is not proof of a missed executable
$152.50 profit: the actual entry/exit path and portfolio replacement matter.

## Decision implication

The evidence supports reviewing how market context and operational costs are
used, particularly a hard exclusion of a strong, direction-confirmed contract.
It does not yet select a universally better cutoff or justify removing
execution, data, event or portfolio-risk controls.

A focused next candidate can preserve raw opportunity quality and ask whether
current market uncertainty calls for a different exposure budget or size.
Evaluate its own holdings, cash, replacements and missed winners against the
current engine. Do not count the upside of newly admitted contracts while
silently retaining every gain from the original portfolio. This is the whole-
portfolio evaluation contract in `ADAPTIVE_ALLOCATION_REVIEW.md`, not an
automatic new six-week test requirement.

## Artifacts and validation

Implementation: `src/allocation_boundary_review.py`. Detailed observations,
reasons, sources, quote coverage, corrupt-file exclusions, same-date/direction
matching and all window sensitivities are in
`reports/allocation_boundary_20261124/review_final.json`. The initial generated
artifact remains preserved. Five fixtures cover soft versus genuine eligibility
failures, effective scores, existing exposure, quote-versus-profit semantics
and unavailable outcomes. Source hashes, all cohort totals, endpoint/maturity
counts and observed-price arithmetic were checked. Historical recommendations,
broker results, original reports and strategy configuration are unchanged.
All 341 repository tests pass. Both frozen experiment manifests and ledgers
still match their source fingerprints; all 875 scanned quote-source hashes verify.
