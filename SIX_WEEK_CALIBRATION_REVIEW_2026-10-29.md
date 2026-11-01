**Later implementation update:** The option-return comparison is now implemented and tested; see SHADOW_OPTION_COMPARISON.md. The checkpoint evidence and earlier readiness assessments below are retained as a dated record. Activation remains off until Sunday.

# Six-week calibration — October 29, 2026

**Decision: prepare a Sunday shadow release, with the existing paper recommendations retained.** Brian selected shadow comparison first. No release has been activated, pushed or scheduled by this review. The new candidate is a diagnostic experiment; its retrospective validation does not justify promotion.

## What changed in our understanding

The directional research remains encouraging: 732 matured current-policy episodes, 55.9% wins, +0.584% average seven-session underlying directional return and 1.28 profit factor after the reviewed CTVA exclusion. Week six added 109 outcomes with 61.5% wins and 1.97 profit factor. These are stock-direction outcomes, not option or account returns.

There is now concrete evidence for where the explanation breaks down:

- Across 364 post-September-24 episodes on 18 dates, higher within-date Research Score quartiles generally perform better. However, treating score/100 as a probability is badly overconfident.
- In 158 chronological test episodes on seven dates, the simple score-plus-direction logistic challenger has Brier loss **0.2540**, versus **0.2490** for a training-only base rate and **0.2815** for score/100. Lower is better. Its AUC is 0.409, versus 0.666 for the raw score on those same episodes. It improves on naive score probabilities but fails the more relevant simple forecasting benchmark.
- Matched top-three research selection: legacy score averages **+3.89%** underlying directional return versus **+3.62%** for the challenger, over only 21 selected episodes apiece. Neither is an executable portfolio replay. The challenger does not earn production replacement.
- The old confidence-plus-headroom ranking hypothesis weakens on the expanded sample: same-date top-three means **-1.17%**, versus **+1.31%** for legacy score, across 54 selections per policy on 18 dates. Preserve its ledger, but stop treating its earlier four-date discovery as a promising validated result.
- Exploratory top-three time-edge selections average **+2.30%**, momentum-alignment **+1.79%**, and conviction **+0.30%** on the same 18 dates. These are full-sample, multiple-comparison diagnostics, not a reason to replace weights tonight. Trend extension alone performs poorly in this sample.
- Of 152 fully closed, nearby matched opening lots with mature directional labels, **81 had a positive seven-session underlying thesis but 42 of those lost gross option money**. Exits may occur before that horizon, and overlapping lots are not independent. This identifies the bridge we must explain; it does not identify a unique cause such as theta or tight stops.

Actual account NAV is $99,226.87, **-$270.36 since the experiment's opening account value**. The existing research-adjusted view is +$382.64 after $653 reviewed exclusions, with actual fees retained. The two views remain separately labeled.

## Validation and uncertainty

Training is expanding and chronological. A training label must mature strictly before the business day preceding the prediction date. All candidates from a test date are held out together. Earliest usable test date is October 9; the earlier collected weeks provide training history rather than disappearing from the analysis. This is why there are seven test dates despite weeks of collection.

Feature scaling uses fixed score units; no future mean or standard deviation is fitted. One simple regularized score-and-direction model was specified, without a parameter search. Test predictions and each training cutoff are saved in chronological_predictions.csv. No option return is replaced by a stock return.

The date-block bootstrap interval for challenger-minus-base-rate Brier loss is approximately **[-0.0035, +0.0156]**. Descriptive calibration slope is -4.04 and intercept 0.60: forecast ordering was unstable across these folds. Seven dates, overlapping market exposures and previously inspected historical evidence prevent a strong significance or regime-robustness claim. The frozen model uses 364 available post-fix episodes; prospective observations are the confirmation stage, not a continuation of historical tuning.

## Architecture decisions

Every layer was reviewed. “Retain” below means retain as the operating baseline for a paired experiment, not certify that its constants are optimal.

| Layer | Checkpoint decision | Evidence / required next measurement |
|---|---|---|
| Universe and discovery | Retain broad universe; defer specialization | Train-only selection of up to five stocks with at least three matured thesis dates yields just one eligible holdout observation. No stock-specialist edge established. |
| Market-data adapters | Modify derived quality handling | Explicit CTVA pre-October-1 mixed-basis exclusion, both directions, with row audit. Raw prices and recommendations stay immutable. General corporate-action reconciliation remains unresolved. |
| Research signals | Retain baseline; investigate time-edge/momentum | Expanded component comparisons recorded, with date and direction caveats. Do not retune from the best in-sample feature. |
| Direction and regime | Retain; separate monitoring by direction | Bullish 64.2% win / +1.56% mean; bearish 45.0% / -0.52%. Date/regime confounding prevents concluding puts should be disabled. |
| Confidence and probabilities | Diagnostic frozen shadow | Chronological test does not beat the base rate. Do not feed these probabilities into capital or stops. |
| Strategy expression | Retain long calls/puts; defer spreads comparison | No preserved alternative-strategy executable outcomes. Directional wins with option losses make expression a material research question. |
| Contract selection | Retain gates; defer weight replacement | 4,771 joint-complete structured observations in the audit, but unselected alternative chains and decision states are not uniformly preserved. |
| Execution and order lifecycle | Retain bid/ask discipline; explicit attribution | Quotes are not fills. 205/213 opening lots linked heuristically; no confirmed broker-order recommendation IDs. DVN/FAST reviewed quantity overlay retained separately. |
| Trade scoring and ranking | Retain legacy; reject old v1 promotion | Expanded headroom comparison deteriorates. New probability shadow has no authority to fund trades. |
| Portfolio selection | Retain; defer exact counterfactual replay | Only 33 mature allocated directional episodes; historical holdings/reserves/order states insufficient for an exact path-consistent alternative portfolio. |
| Sizing and capital use | Retain risk limits; no score-probability sizing | $15k experiment sizing is distinct from broker NAV. Integer contracts, 3-contract cap, materiality floor, utilization and full-premium risk remain explicit review parameters. No optimality claim. |
| Correlation and diversification | Retain baseline proxy constraints; collect measured comparison | Nine preserved snapshots, October 19–29, all pair rows measured. Some same-ticker candidate/holding pairs are exactly correlated. Pair count is not independent outcome count. No historical correlation-benefit claim. |
| Exits and holding horizon | Research above/below 20%; retain baseline pending validation | Full archive rerun and dynamic feasibility analysis in option-path outputs. Calibrated confidence is not yet supported, so confidence-driven risk changes cannot be justified. |
| Broker state and accounting | Retain broker truth plus explicit overlays | NAV, cash and option value reconcile. Lot ledger gross P/L excludes unallocated account fees; cumulative account performance retains all fees. Unsupported shorts remain outside long-option replay. |
| Learning and hindsight | Modify validation and quality gates | Chronological purge/embargo, date-grouped diagnostics, raw/derived separation and explicit corporate-action exclusion. Keep causal claims separate from diagnostics. |
| Storage and provenance | Retain canonical history; use slim derived artifacts | Checksums, code revision, source inventory, prediction ledgers and exclusions captured. The journal is not tracked. Against the cached origin branch, the one existing unpushed commit has only three blobs, largest 238,743 bytes; none exceeds 100MB. Fresh remote state still needs checking Sunday. |
| Reporting and explainability | Add signal-to-broker bridge | signal_to_broker_lot_ledger.csv exposes signal, selection, quantities, entry bases, actual exits and underlying outcome. Heuristic match and fee gaps are explicit. |
| Operations and deployment | Opt-in sidecar after existing email/collection | Disabled activation file; no network test scan or email sent. Shadow failure warns without stopping baseline. Laptop/scheduler reliability is not solved by this statistical release. |
| Experiment governance | One frozen diagnostic comparison; no automatic promotion | Start forward lineage only after Sunday activation, first normal session November 2. No historical row is relabeled prospective. Promotion requires separate reviewed outcome evidence, including option economics. |

## Data inventory and explanation artifacts

The automated audit inventories **97 settings**. Six structured-collection families are partial: contract selection, allocation/capital, exits/profit protection, Greeks/volatility, earnings and policy provenance. The one unmapped setting is the September 24 correction boundary, which this review applies explicitly. Collection-present is not calibration-ready.

The broker explanation ledger has 213 experiment-era long opening lots, 205 nearest-prior exact-contract matches within 72 hours, and eight unmatched lots. These are inferred matches, not confirmed order linkage. Only same-day/nearby matches enter the tighter directional-versus-option diagnostic. Three rows carry explicit DVN/FAST reviewed-quantity references. The separate reviewed_quantity_overlay.csv documents intended and excess quantities; whole trades and legitimate intended-size losses are not excluded.

The earlier weekly review and the quality_analytics subfolder retain week-by-week and multi-horizon breakdowns. The production-quality candidate reproduces **732 current-policy matured episodes** and excludes **68 raw pre-October-1 CTVA observations** with a row-level audit. This is an unresolved basis exclusion, not a reconstructed economic price series or a general corporate-action solution.

## Dynamic algorithms and changes we are not yet entitled to make

Twenty percent remains an unproven baseline cap. The exit review tests 10%, 15%, 20%, 25%, 30% and 40% against identical sampled paths, holding original targets fixed, plus target sensitivity. It distinguishes stop survival from eventual recovery, tracks observed overshoots, and applies coverage gates before comparing results. Costs, gaps and full-premium loss remain material.

The intended dynamic design is conditional on option-return paths and a separately validated probability forecast: estimate adverse excursion, upside and time-to-outcome distributions using only earlier matured comparable paths; derive stop/target/time rules from those distributions; size integer contracts against stressed dollar loss and full-premium risk; adapt at entry and permit later tightening, with widening requiring a separately approved policy. Unknown or sparse contexts fall back visibly. Percentile choices, minimum evidence, risk budgets and bounds remain explicit research parameters, not silently declared optimal.

A fixed global winner from the stop grid would not meet this requirement. A failed confidence forecast must not be smuggled into a dynamic exit formula. The current release collects evidence and preserves the baseline; a validated confidence-conditioned exit replacement is deferred with these named dependencies.

## Sunday release and rollback

Prepared source modules: six_week_calibration.py, six_week_release.py and hindsight_quality.py; opt-in hooks in daily_run.py and hindsight_analytics.py; frozen challenger and disabled activation.json under research/six_week_20261029. No baseline scoring/allocation/exit constants change.

Sunday steps:

1. Review this report and exit findings. Keep the diagnostic challenger separate from any claim of improved expected returns.
2. Check the exact code/artifact manifest and regression result, verify remote branch state, and commit/push only the reviewed release files plus separately chosen existing work. Do not stage the entire working tree: it contains unrelated holdings, journals and large historical state.
3. Verify weekly market-data token readiness and the next scheduled daily run. No secret contents belong in the release.
4. Set research/six_week_20261029/activation.json to `{"enabled": true, "quality_review": true}`. The calendar gate rejects activation before November 1. No new trading account permission is required or requested.
5. On November 2, verify a fresh baseline report and a separate timestamped CSV under data/processed/six_week_shadow. Confirm policy version, probability target, source recommendation IDs and no missing latest-day candidate set. Before counting evidence, check source completeness and duplicates across reruns.

Rollback: set enabled false. Preserve all previously written shadow and quality audit artifacts. This disables the sidecar and quality-review opt-in; broker state, immutable recommendations and the paper baseline are not reset. If rolling back the quality gate, raw CTVA metrics again require an explicit caveat until reconciliation.

## Forward monitoring and promotion

Track matched recommendation IDs, mature versus censored labels, date/direction/regime coverage, Brier/log loss/reliability, legacy ordering, net option outcomes, execution differences and concentration. Compare with the frozen base rate and frozen baseline on the same observations. The existing >=100 matched-observation gate is a minimum, not sufficient proof; require adequate independent dates, favorable expectancy/PF, tail/cohort stability and actual option economics before a separate promotion decision.

Data errors or missing/stale runs trigger investigation and exclusion from decision-quality comparisons with reasons. Deteriorating calibration triggers reduced reliance on the challenger (the baseline already owns all guidance). A short losing streak alone does not retrain or alter policy. A new model or parameter set gets a new version and forward clock.

Historical performance analysis, architecture decisions and the diagnostic release are prepared here. Specific claims blocked by missing alternate chains, orders, IV benchmark history, regime diversity or validated confidence remain explicitly deferred; no historical data completeness is implied by listing those analyses.

## Completed exit refresh and verification

# Full archive exit review — October 29

All 10,073 available bundles were scanned across 28 recorded dates, September 18–October 29: 16,283,195 observations, 13,375,794 valid real-time quotes. Three corrupt/interrupted files remain preserved and fingerprinted. September 22 has no usable quotes; October 14 and October 22 have no artifacts. There are 30 expected sessions, 9,357 usable sampled minute slots out of 11,700, with uneven exact-contract coverage.

The audit follows 161 broker opening lots across 27 dates and separately 180 allocated contract/date references across 30 dates. These overlap; they are not 341 independent trades. There are 122 mature broker windows, but only **31 coverage-qualified full-thesis paths on seven dates**, all calls. Coverage requires >=90% expected minutes, first/end observations within five minutes and no gap over 30 trading minutes. Later collection does not repair a missing October 14/22 session. Historical pre-minute-collection trades remain available for broker and directional analysis, not invented intraday paths.

## Stop-distance comparison

Original targets held fixed, sampled bid liquidation, same 31 broker paths. Differences are percentage points of option premium return, not dollars or account returns. No fees are deducted in these proxies; gaps and observed bid overshoots remain. These are static initial plans, not the full daily ratchet/portfolio-exit lifecycle.

| Stop | Mean return difference vs original | Better / worse paths | Difference after removing best improvement | Worst sampled proxy return |
|---|---:|---:|---:|---:|
| 10% | +1.91 pp | 19 / 3 | +1.25 pp | -21.9% |
| 15% | +2.40 pp | 10 / 7 | +0.71 pp | -35.2% |
| 20% | +0.15 pp | 2 / 18 | -1.61 pp | -35.2% |
| 25% | +1.59 pp | 5 / 18 | -0.12 pp | -43.5% |
| 30% | -1.99 pp | 5 / 19 | -3.83 pp | -43.5% |
| 40% | -5.51 pp | 6 / 20 | -7.46 pp | -51.9% |

Twenty-five percent's average improvement disappears when its best improvement is removed. Thirty and forty percent deteriorate on average. Ten and fifteen percent look better in this limited call cohort, but choosing the highest number from this exploratory grid is not validation of a global cap or a dynamic algorithm. All original-plan proxy means are negative in this subset, so improving a negative baseline does not establish a profitable policy. Mean and equal-date-weighted results differ materially; see comparison_summary.csv.

Actual losing-stop follow-up: in the strongest cohort, 10 of 14 losing exits later reach break-even bids and three reach the original target. Across mature windows with partial coverage, 41 of 61 later show break-even and nine reach target. Eventual recovery is different from surviving an alternate stop along the path. Overnight prices and true first-event ordering are unavailable.

## Shorter fixed-horizon checks

These extend date coverage without being relabeled full thesis windows. The uniform-20% comparison holds original targets fixed.

| Sessions after entry | Qualified paths | Entry dates | Latest entry | Mean change from uniform 20% |
|---|---:|---:|---|---:|
| 1 | 112 | 19 | 2026-10-28 | -0.43 pp |
| 3 | 73 | 12 | 2026-10-16 | -1.54 pp |
| 5 | 47 | 8 | 2026-10-02 | -0.84 pp |
| 7 | 37 | 6 | 2026-09-30 | -1.81 pp |
| 14 | 0 | 0 | — | Unavailable |

## Conditional dynamic feasibility

A timestamped training projection preserves the 31 qualified reference paths: 26 seven-session calls and five five-session calls, with exact IDs, maturity timestamps, coverage and recorded context. No qualified puts are inferred. Conditional excursion quantiles are descriptive and saved in dynamic_exit_research.json.

Using earlier matured paths, an additional one-day separation and exact strategy/horizon matching, **none of 180 reference decisions reaches the existing provisional 30-path support threshold**. Maximum prior comparable support is 26. A calibrated confidence input also fails the separate chronological forecasting benchmark. These facts block a defensible confidence-conditioned exit policy today; they do not establish 30 as an optimal evidence threshold.

The existing empirical_exit_policy.py is a research scaffold, not a fully calibrated production module: its default option_exit_paths.csv does not exist, the raw gzip archive is not automatically converted to that input, its matching can fall back across all option paths, and its replay assumes a configured stop/slippage loss rather than the observed overshoot used here. Do not populate that default file with the 31 call paths and allow them to calibrate puts or incompatible horizons. The new projection stays isolated in this review directory.

Before testing a dynamic replacement: wire a versioned coverage/maturity-aware training adapter; forbid unmatched strategy/horizon pooling; handle sparse contexts explicitly; validate confidence separately; derive conditional risk/target distributions from earlier paths; size against stressed dollar risk and full-premium loss; preserve record-level decisions and validate on forward paths. Review percentile, sample-support and risk-bound choices as research assumptions. Start with entry adaptation plus later tightening; widening after entry requires a distinct reviewed policy.

## Verification and limits

Eight synthetic replay tests pass. Four contract examples independently trace extrema back to raw gzip files and recompute threshold events. All raw sources remain unchanged; the manifest includes interrupted bundles. Broker timestamps are naive: Eastern is the working assumption, with Central sensitivity retained. Trade-to-recommendation matching is inferred. Proxy comparisons are per path and quantity-independent; actual dollar attribution uses the separate broker lot ledger and reviewed DVN/FAST overlay.

Entry ask touches and sampled bid crossings are feasibility observations, not guaranteed fills. Missing or censored windows are never counted as zero-return trades. New configurations, order lifecycle and alternate strategies cannot be inferred from these static tests.


Final regression: **145 repository tests passed**, plus **eight option-path replay tests**, four independently traced raw-contract examples, successful module compilation and a real-source quality-gate smoke check. Activation remains false.
