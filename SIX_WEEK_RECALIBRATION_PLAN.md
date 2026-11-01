# Project Stonks — Six-Week Recalibration and Architecture Review

Prepared October 22, 2026. Policy baseline: PE-2026-09-08.
Status: agreed investigation scope; analyses and decisions below are pending unless explicitly identified as existing evidence. This document does not change production behavior or restart the twelve-week experiment.

## 1. Purpose and decision standard

The project is progressing as expected. The checkpoint is the next learning step toward sustained, explainable, risk-adjusted returns—not a presumption that the existing system has failed.

The central question is: **Can we explain how an observed signal becomes an investment outcome, identify which relationships are dependable, and recognize when changing market conditions weaken them?**

Improving aggregate results and identifying interesting investments are encouraging. They do not establish which scores predict success, whether reported confidence is calibrated, or whether allocation and option execution capture the research edge. The review must reconcile those questions with actual broker performance.

Every architectural choice is open to review. Retaining a component requires a recorded rationale just as changing one does. Prefer simple, interpretable algorithms supported by evidence; complexity and dynamism are not goals by themselves.

Deliver a decision for each component: retain with evidence, modify in shadow, replace in a controlled experiment, retire, or defer because a named measurement is missing. Distinguish observations, hypotheses, validated findings, and approved production decisions throughout.

## 2. Freeze the evidence and reconcile the experiment

- [ ] Record the checkpoint timestamp, code revision, configuration, policy versions, source identities, checksums, and outcome availability as known at that timestamp.
- [ ] Reconcile the September 8 baseline clock, September 24 directional-confidence correction, week definitions, and any later instrumentation changes. Do not pool incompatible policies for calibration.
- [ ] Produce a data inventory with actual coverage by date, ticker, exact contract, recommendation, position, and outcome horizon—not simply field presence or the collector's PARTIAL label.
- [ ] Preserve immutable recommendations and broker exports. Corrections, derived data, exclusions, and later interpretations must carry separate provenance.
- [ ] Deduplicate observations into clearly defined research episodes and broker entry/exit lots. Identify repeated signals, overlapping holding windows, common market exposures, duplicate fills, and unsupported short exposures.
- [ ] Distinguish mature, censored, missing, ambiguous, stale, and unavailable outcomes. Missing outcomes are not losses, successes, or zero returns.
- [ ] Use only matured outcomes available at the training cutoff to select a challenger. Later-maturing baseline outcomes may inform reporting but must not retroactively retune the frozen challenger.
- [ ] Verify broker/export timezone, quote timestamps, order attribution, corporate actions, contract adjustments, and universe survivorship. Document unresolved ambiguity rather than assuming it away.

Timing must be explicit: six calendar weeks do not mean every week-six thesis or option path has matured. A report stage label is not proof that a challenger has been approved or started.

### Historical data readiness: inclusion is not a claim of completeness

The scope above is an investigation agenda, not a certification that every
question can be answered from historical records. The first deliverable must
verify these provisional classifications against the frozen sources. Report
what is answerable now, what can be tested only with explicit assumptions,
and what needs prospective collection. Do not silently fill gaps.

| Work item | Current evidence and dependency |
|---|---|
| Directional outcomes and weekly cohorts | Available now for matured recorded recommendations, subject to missing market data, policy separation and dependence controls. |
| Score/ranking evaluation | Recorded scores and components support historical tests. Coverage and distinct recommendation dates limit fine-grained calibration; out-of-sample validation is still required. |
| Probability calibration | Can begin using recorded inputs and outcomes. Historical scores are not historical calibrated probabilities; candidate forecasts must be generated with leakage-controlled training/holdout procedures. |
| Broker P/L and account reconciliation | Broker exports, fills and account snapshots exist. Missing daily snapshots, incomplete order linkage, overlapping exports and unsupported positions limit some exact capital-weighted or decision-level attribution. |
| Option-path exits and recovery | Existing quote archive supports sampled, coverage-qualified analysis now. Long complete windows and put examples are limited; no tick-complete or overnight paths, guaranteed fills, or fully reconstructed dynamic exit lifecycle are assumed. |
| Dynamic confidence-based exit algorithms | Enough evidence for initial bounded research and simpler comparisons, not certification of a detailed algorithm across every score/Greek/regime combination. Some validation will require new forward observations. |
| Recorded contract characteristics | Selected contracts have IV/Greek/DTE/spread evidence with variable historical coverage. Alternative contracts and every historical selection state are not uniformly preserved; missing alternatives cannot be invented for a replay. |
| Historical IV Rank/Percentile | Not established by the current exact-contract quote archive. Requires an approved constant-maturity/moneyness benchmark and sufficient appropriate history, acquired or collected separately. |
| Entry-limit feasibility and execution | Quotes and actual fills support partial checks. Full historical submissions, modifications, cancellations, queue position and live fills are unavailable or incomplete; ask touches are not fill rates. |
| Portfolio/allocation counterfactuals | Recorded candidates, decisions and some portfolio state support bounded comparisons. Exact historical holdings, working-order reserves and all decision-time constraints require coverage verification; some replays will be approximate or unavailable. |
| Measured correlation | Prospective collection was added October 16, so preserved as-known snapshots are recent. Earlier underlying-return correlation may be reconstructed from appropriate historical prices but must be labeled retrospective, not previously known or complete portfolio replay evidence. |
| Earnings, regime and relative strength | Existing fields support some tests. Missing as-known earnings dates, sector mappings or point-in-time classifications can block causal/event or sector-relative comparisons. Present-day data must not be substituted silently. |
| Narrow-stock specialization | Broad-universe history permits discovery and some historical holdout tests. Selecting the best historical stocks does not validate specialization; adequate unseen dates, market conditions and prospective outcomes are needed. |
| Market adaptation and monitoring | Existing time series can inform a first playbook. Durable drift triggers, response policies and behavior across unobserved regimes require additional validation; they cannot be certified from this short experiment. |
| Architecture alternatives and operations | Current implementation and logs support review. Historical outcomes do not exist for unrun designs, uncaptured strategy vehicles, a new host or new order workflows; evaluate with fixtures, explicit simulations and/or prospective trials. |

If a work item lacks sufficient evidence, its valid checkpoint output is a
specific gap, collection/reconstruction plan, and deferred decision—not an
unsupported recommendation. Architecture can be reviewed now even where a
replacement's performance cannot yet be measured.

## 3. Build the signal-to-P/L explanation

Create a linked, auditable record for:

**As-known market data → component signals → research score → forecast/probability → strategy → contract → execution guidance → allocation/size → broker fills → exit decisions → realized and unrealized P/L.**

- [ ] Join recommendation ID, policy evidence, exact contract, position/lot, order/fill references where available, and all subsequent decisions. Report join coverage and unresolved matches.
- [ ] Preserve what each number means: ranking score, confidence label, predicted probability, expected return, risk estimate, or policy constraint. A score of 90 is not a demonstrated 90% probability.
- [ ] Compare research and decision-time prices with actual entry/exit fills. Separate paperMoney performance from assumptions about live execution.
- [ ] Reconcile broker NAV changes to cash flows, realized P/L, unrealized P/L, and fees. Keep broker totals distinct from reviewed research-performance adjustments.
- [ ] Report gross and net option returns, dollar P/L, account-NAV return, experiment-base return, and deployed-capital return with explicit denominators. Do not invent missing daily capital exposure.
- [ ] Explain representative winners, losers, correct-direction/losing-option trades, incorrect-direction/profitable exits, rejected winners, and allocated losers end to end.
- [ ] Attribute outcomes to forecast error, contract expression, volatility/theta effects, spread/slippage, entry timing, sizing, portfolio selection, exits, or operational/process events. Use quantitative reconciliation where possible and label qualitative or residual attribution.
- [ ] Do not claim causal contribution from observational correlations or an approximate Greeks decomposition. Check interactions and unmodeled residuals.

Required deliverable: an explanation ledger and a concise trade-review format that answers what we believed, why, how capital was committed, what happened, and which layer accounts for the result.

## 4. End-to-end architecture inventory

For every row, document purpose, current implementation, assumptions, dependencies, measured incremental value, alternatives, and retain/change/defer decision. No row is exempt from review.

| Layer | Questions and alternatives to evaluate |
|---|---|
| Investment mandate and universe | Is the broad S&P 500 useful, or would a smaller liquid universe, ETFs, or a handful of predictable stocks produce more durable learning and net returns? |
| Data acquisition and adapters | Are source quality, freshness, corporate actions, API reliability, quote cadence, and contract coverage sufficient? Is minute sampling adequate for the intended decisions? |
| Research signals | Which trend, momentum, breadth, risk, liquidity, relative-strength, and other components add independent predictive information? Which duplicate or conflict with others? |
| Direction and regime | Do broad market adjustments improve forecasts or suppress stock-specific opportunities? Compare continuous context, decomposed factors, and simpler alternatives. |
| Research scoring and confidence | Does score ordering predict outcomes within date and direction? Should confidence become an explicit calibrated forecast with uncertainty? |
| Strategy selection | Are long calls/puts the right expression of the thesis? Review long-premium suitability and constrained alternatives without assuming strategy expansion is necessary. |
| Contract selection | Evaluate delta, moneyness, DTE, liquidity, IV, theta, vega, affordability, and horizon fit jointly. Are current gates and weights supported? |
| Execution and orders | Are entry limits attainable? How do fills differ from guidance? Review order lifecycle, partial fills, OCO quantities, cancel/replace, and live-versus-paper assumptions. |
| Trade scoring and ranking | Do Research, Institutional, Execution, Contract, Time Edge, and Portfolio scores each add value? Compare simpler or staged ranking designs. |
| Portfolio selection | Why are particular opportunities funded or rejected? Compare incumbent-versus-candidate competition, turnover, affordability, and opportunity costs. |
| Sizing and capital use | Evaluate integer-contract effects, NAV assumptions, position counts, contract caps, utilization, cash, and full-premium risk. Distinguish useful risk policy from arbitrary parameters. |
| Exposure and diversification | Assess sector/theme proxies, measured correlation, directional exposure, existing holdings, concentration, and marginal candidate contribution. |
| Exits and holding horizon | Evaluate dynamic stops, targets, time exits, profit protection, thesis invalidation, and portfolio-driven exits. The 20% stop cap is a hypothesis, not an assumed optimum. |
| Broker state and accounting | Can holdings, fills, fees, cash, working orders, and NAV be reconciled without conflating broker truth and model assumptions? |
| Learning and hindsight | Are labels economically meaningful, samples independent enough, comparisons fair, and metrics resistant to leakage and selection bias? |
| Storage and provenance | Review compressed canonical evidence, slim analytics projections, manifests, schema evolution, reproducibility, and preservation of raw history. |
| Reporting and explainability | Can the user understand recommendations, uncertainty, risk, actual outcomes, and the source of changes without reverse-engineering the system? |
| Operations and deployment | Review scheduling, laptop dependency, wake behavior, failure detection, stale-run handling, collection gaps, email delivery, and suitability of a more reliable host. |
| Experiment governance | Review promotion, rollback, monitoring, and experiment structure itself. Architectural review is broad; production changes still require a concrete, attributable validation design. |

Protocol limits and contract mechanics are different from tunable research assumptions. Inventory both; do not promise that every constant can or should disappear.

## 5. Required analytical workstreams

### A. Direction, forecast quality, and probability calibration

- [ ] Refresh weekly and cumulative outcomes at multiple fixed horizons; preserve raw observations and deduplicated episodes separately.
- [ ] Separate pre/post September 24, bullish/bearish, ticker, date, regime, allocation status, and data-quality cohorts.
- [ ] Evaluate score monotonicity, within-date ranking, discrimination, expected-return relationships, and uncertainty. Test underlying direction and option profitability as separate prediction problems.
- [ ] Calibrate candidate probabilities with chronological, date-grouped out-of-sample predictions. Prevent leakage from overlapping contracts/episodes; use purging or embargo where needed.
- [ ] Report reliability tables, Brier score, log loss, calibration slope/intercept, discrimination, sample sizes, and uncertainty. Compare with simple base-rate forecasts.
- [ ] Assess whether probabilities predict target-before-stop, positive net option return, move magnitude, time to resolution, and recoverable drawdown—not just eventual stock direction.
- [ ] Identify weakly supported contexts and define shrinkage, uncertainty reporting, or fallback behavior rather than overfitting many tiny score buckets.

### B. Ranking, allocation, and opportunity cost

- [ ] Compare allocated, qualifying unallocated, Watch, non-executable, affordability-rejected, quality-rejected, and incumbent positions without conflating their populations.
- [ ] Re-evaluate the earlier allocation-underperformance hypothesis using the enlarged sample; do not assume an old finding remains true.
- [ ] Reassess legacy research ranking, shadow ranking, two-stage shortlist selection, and simpler alternatives using equal opportunity sets and selection counts.
- [ ] Measure incremental value after direction/date controls. Test component ablations, redundant inputs, interactions, and stable pairwise profiles before extensive higher-order searches.
- [ ] Replay portfolio constraints, capital use, turnover, incumbent advantages, and rejected opportunities. Separate ranking misses from unaffordability.
- [ ] Compare the observed $15,000 experiment base with alternative-NAV/notional shadow cases. Do not silently change the deployment problem or claim fractional contracts are executable.

### C. Option expression, execution, and events

- [ ] Explain directionally correct but financially losing option trades using actual option outcomes, DTE, Greeks, IV changes, theta, spread, and fills where measurable.
- [ ] Compare delta/moneyness, IV, theta drag, vega per premium, DTE, holding horizon, and liquidity profiles within comparable date/direction contexts.
- [ ] Retest low-theta, moderate-delta/IV, and other previously interesting profiles on the expanded sample. Do not treat exploratory bands as established rules.
- [ ] Resolve earnings-status completeness. NOT_CHECKED is not confirmed absence of earnings; preserve what was known at the decision time.
- [ ] Establish whether conventional IV Rank/Percentile has a valid underlying benchmark and sufficient history. Exact-contract IV is not a substitute for constant-maturity IV history.
- [ ] Measure entry-limit ask touches, fill latency, actual slippage, exit execution, spread costs, partial fills, and adverse selection. Quote touches are not guaranteed fills.
- [ ] Audit quantity-aware exit/OCO behavior, including oversells and accidental shorts, separately from strategy profitability.

### D. Confidence- and path-conditioned dynamic exits

The objective is an explainable algorithm, not finding one globally best percentage. Review both the formula and its assumptions, including whether 20% is an appropriate cap at all.

- [ ] Use the full collected option archive and broker fills. Audit per-contract entry-to-exit/thesis coverage, freshness, missing sessions, endpoint maturity, and timezone alignment.
- [ ] Measure adverse/favorable excursions, actual stop executions, subsequent recovery, target achievement, time to recovery, and outcomes after different exit decisions.
- [ ] Distinguish eventual recovery from survival under an alternative stop: a trade may hit a wider stop before recovering.
- [ ] Estimate conditional distributions of recoverable drawdown, upside, time-to-target, and terminal option return by calibrated confidence, volatility, Greeks, spread, horizon, direction, and regime where samples support it.
- [ ] Compare dynamic stop distances, targets, time exits, and profit-protection rules with the frozen baseline on identical observations. Include thesis invalidation and portfolio CLOSE/REDUCE actions as distinct exit causes.
- [ ] Evaluate alternatives above and below 20% in research; record the implications for tail risk and full-premium loss. The current cap is neither a proven optimum nor permission to widen production stops now.
- [ ] Determine whether stops may widen after entry, under what evidence and risk checks, or whether adaptation should occur only at entry with later tightening. Make this an explicit design decision.
- [ ] Couple sizing to the estimated exit risk so more breathing room does not automatically mean more portfolio risk. Evaluate capital, liquidity, gap/slippage risk, and contract indivisibility.
- [ ] Test target changes separately from entry-limit feasibility. Include target overshoot, reversal after target, premature profit-taking, and net expectancy.
- [ ] Compare algorithms across dates and horizons, with cost and gap sensitivity, rather than selecting the best in-sample grid point. Retain uncertainty-aware fallback behavior when data is insufficient.

Do not infer fills at stop triggers, continuous first-event order, or missing overnight prices. Do not automatically promote gapped sampled paths into a calibrated production exit dataset.

### E. Portfolio correlation, regime, and narrower specialization

- [ ] Audit the prospective 60-session, direction-adjusted correlation evidence and its coverage for candidates and holdings. Compare it with sector/theme proxies and incremental concentration.
- [ ] Test diversification value and whether apparent ticker variety represents essentially the same market exposure. Review classification completeness.
- [ ] Decompose regime controls into trend, breadth, volatility, risk mode, and ticker/sector-relative context. Compare ablations and simpler continuous alternatives.
- [ ] Test whether a handful of stocks show repeatable, economically useful predictability after costs, rather than selecting names that happened to win retrospectively.
- [ ] Select any specialized universe using training data only, then freeze it for holdout/forward evaluation. Compare broad versus narrow policies on both performance and number of independent opportunities.
- [ ] Evaluate loss of diversification, trade frequency, market sensitivity, liquidity, and sample concentration. A small universe is a legitimate architectural outcome, not a predetermined answer.

### F. Explainability, market adaptation, and operational integrity

- [ ] Produce explanations at both the individual-trade and portfolio level. Show component evidence, forecast uncertainty, selection/rejection reasons, sizing, exit logic, and realized outcome attribution.
- [ ] Define how to detect deterioration: forecast calibration drift, net expectancy changes, altered score relationships, regime dependence, execution degradation, and concentration changes.
- [ ] Separate data/operational failure from model failure and expected statistical variation. Do not retune automatically after a short losing streak.
- [ ] Define an evidence-based response ladder: investigate, reduce reliance or exposure, fall back, pause, or propose a new version. Establish and validate monitoring thresholds rather than inventing them from one observed downturn.
- [ ] Review the daily scan and minute collector as separate operational systems. Record missed sessions and delayed runs; identify how stale or incomplete evidence should affect reporting and decision eligibility.
- [ ] Document what remains unknown and what specific future observations would resolve it.

## 6. Existing evidence to carry into the review

These are dated observations and hypotheses—not final calibration results.

### October 22 directional refresh

- Current-policy seven-day population: 625 matured executable episodes; 54.9% directional win rate, approximately +0.48% average underlying directional return, 1.23 profit factor.
- Post-fix bullish: 96 episodes, 65.6% wins, approximately +1.45% average directional return. Post-fix bearish: 160 episodes, 42.5% wins, approximately -0.56%. Combined post-fix win rate is 51.2%; do not substitute the pooled 54.9% headline for corrected-model performance.
- Allocated outcomes improved to 16/31 wins and approximately +0.56% average directional return, weakening the earlier blanket allocation-underperformance finding. Nine newly matured allocated winners materially influenced this change.
- These are underlying directional outcomes, not option/account returns. Dependence on market/date cohorts remains relevant.

### October 22 option-path audit

- All available September 18-October 21 intraday bundles were examined: 8,298 bundles across 23 dates, 11,867,127 quote records, and 9,697,361 usable quotes. Missing expected sessions were assessed through October 22.
- September 22 had files but no usable quotes; October 14 and October 22 had no intraday artifacts. Three compressed bundles were corrupt/interrupted and retained.
- The study linked 129 broker long opening lots and separately examined 138 allocated recommendation/date references. These populations overlap and must not be added together.
- The stronger complete-thesis subset has 31 calls across seven entry dates, with at least 90% minute coverage and additional entry/endpoint/gap requirements. It cannot establish a put-specific rule.
- Among 14 actual losing-stop lot exits in that subset, ten later showed break-even bids and three later showed the original target. Those recoveries do not by themselves justify wider stops.
- A uniform 20% stop improved two of the same 31 simulated paths, worsened 18, and left 11 unchanged; the small mean improvement was outlier-sensitive. Shorter-window checks extended coverage to 97 entries across 17 dates without finding consistent benefit from a uniform 20% stop.
- These are sampled static-plan comparisons, not a replay of the complete production exit policy or a calibrated dynamic challenger.
- Existing adaptive exits receive OpportunityScore as their confidence argument. Of 138 allocated references, 136 have confidence 90 and two have 75. Confidence >=90 adds 0.25R to the target; stop width uses other inputs. This is a known frozen-baseline limitation, not a newly introduced defect.

Reference artifacts: `SIX_WEEK_CHECKPOINT_PREP.md`, `EXTERNAL_REVIEW_2026-10-07.md`, `RESEARCH_RANKING_RETRO_2026-10-10.md`, the October 22 hindsight outputs, and `outputs/option-path-review-2026-10-22/Review.md` in the originating chat workspace. Refresh numerical findings when the checkpoint evidence is frozen; do not overwrite historical reports.

### October 29 price-basis finding to resolve before calibration

The new refresh identified revised CTVA history inconsistent with recorded
pre-separation entry prices. A favorable separation-crossing outcome is also
unreconciled. Review-only comparisons exclude all pre-October-1 CTVA
observations from both dates, removing two mature current-policy episodes.
Raw sources remain preserved and unfiltered. Resolve corporate-action and
entitlement handling, test for similar mismatches across the universe, and
publish a lineage-aware measurement view before relying on final calibration.
Do not mistake a price-basis artifact for an investment loss or a data-quality
exclusion for a broker-performance adjustment. See PROJECT_STATUS.md for the
October 29 review findings and quality-view locations.

## 7. Validation and experiment design

- [ ] Establish simple benchmarks and evaluate net expectancy, payoff ratio, profit factor, median return, average/worst loss, tail frequency, drawdown, turnover, costs, utilization, and uncertainty—not win rate alone.
- [ ] Use chronological training/validation/holdout splits grouped by recommendation date. Prevent overlapping episode/contract leakage and test calendar-time generalization.
- [ ] Report sample counts and effective concentration by dates, tickers, directions, and regimes. Avoid false precision from repeated observations or multiple contracts.
- [ ] Run ablations, nearby-parameter sensitivity, equal-date weighting, winsorization, best/worst-outlier removal, and leave-date/ticker-out checks as appropriate.
- [ ] Maintain a record of all tested hypotheses and comparisons to make selection and multiple-testing risk visible. Do not promote whichever narrow slice looks best.
- [ ] Freeze model inputs, formulas, training cutoff, parameters, uncertainty/fallback behavior, version, success criteria, and failure/rollback criteria before forward evaluation.
- [ ] Review every architectural component, but keep each confirmatory comparison attributable. Existing governance favors one bounded challenger; reconsider the experiment structure explicitly if a coherent architectural replacement requires more than one component. Do not silently bundle unrelated changes.
- [ ] Preserve baseline and challenger decisions on the same prospective opportunity set during weeks 7-12 where feasible. Label reconstructed historical tests separately from prospective observations.
- [ ] Existing promotion requirements include at least 100 matched shadow observations, positive expectancy/profit factor above 1, improved baseline-relative results, acceptable tail risk, cohort stability, and reproducibility. Review sufficiency and outcome definitions for the chosen challenger; a numerical count alone is not proof.
- [ ] If evidence is insufficient by week 12, report that and extend validation rather than force a favorable conclusion. A material replacement must have explicit lineage and a justified comparison clock; historical progress is never silently erased.

## 8. Required checkpoint deliverables

| Deliverable | Must answer |
|---|---|
| Frozen evidence manifest and quality audit | What data actually supports each analysis, as of when, and with what gaps? |
| Broker/account reconciliation | What did we actually earn or lose, on which capital, after which costs? |
| Signal-to-P/L explanation ledger | Which decisions and measurable effects explain each representative outcome? |
| Forecast and probability calibration report | Which scores predict what, how reliably, and in which contexts? |
| Architecture decision matrix | What is retained, changed in shadow, replaced, retired, or deferred—and why? |
| Dynamic-exit study | Does conditional confidence/path logic improve exits, and is 20% justified anywhere? |
| Portfolio/universe comparison | Does broad coverage or specialization best capture the measurable edge? |
| Market adaptation and monitoring playbook | How do we recognize a broken relationship and respond without reactive overfitting? |
| Challenger specification and validation package | What exact hypothesis will be tested prospectively, against which baseline, with which criteria? |
| User-facing checkpoint summary | What have we learned, what remains unknown, and what concrete decisions need review? |

## 9. Execution order and completion tracking

1. Freeze sources, verify coverage, and reconcile broker/account truth.
2. Build the explanation ledger and refresh directional/option outcome attribution.
3. Calibrate forecasts and evaluate every architectural layer against evidence.
4. Complete dynamic-exit, ranking, contract, portfolio, regime, and specialization comparisons.
5. Review the architecture decision matrix; choose a coherent challenger or document why none is ready.
6. Freeze and test the challenger, monitoring, fallback and rollback specifications.
7. Begin the approved prospective matched comparison; report results and limitations through week 12.

Track each work item as **not started / in progress / complete / deferred**, with artifact location, source cutoff, evidence, limitations, and next decision. Creating this plan does not mark its analyses complete. Only the explicitly dated existing studies above have been performed.

Production scoring, allocation, strategy, exits, risk limits, and universe remain unchanged by this document. Research alternatives may challenge every architectural assumption, including the 20% cap and broad-universe mandate. Promotion requires the resulting evidence and a recorded review of the concrete change.


## October 29 execution record — early checkpoint

Brian requested the review tonight and selected **shadow comparison first** for
Sunday. The prepared review is `SIX_WEEK_CALIBRATION_REVIEW_2026-10-29.md`.
The original checklist above is retained as the scope ledger; this dated table
supersedes the earlier blanket statement that analyses are pending.

| Deliverable | Status and result |
|---|---|
| Frozen evidence / coverage / provenance | Complete for available sources; code/data/artifact manifests and 97-setting audit prepared. |
| Broker reconciliation | Complete through October 29 statement; raw NAV and research adjustments remain distinct. |
| Explanation ledger | Complete initial long-lot bridge: 213 lots, 205 inferred exact-contract prior matches; confirmed order linkage and lot fee attribution deferred. |
| Probability calibration | Complete chronological diagnostic: 158 test episodes / seven dates; challenger fails base-rate comparison. Forward verification remains pending. |
| Architecture matrix | Complete review decisions across 19 layers; deferred replacements name their missing evidence. |
| Dynamic exits / 20% hypothesis | Complete expanded sampled-path audit including 25/30/40%; conditional feasibility assessed. Validated confidence-conditioned replacement deferred: insufficient comparable qualified paths and validated forecast. |
| Ranking / portfolio / specialization | Expanded same-date ranking and train-only narrow-universe tests complete. Exact portfolio replay deferred for missing order/holdings/reserve states; alternate-chain and strategy replay deferred for missing decision-time alternatives. |
| Market adaptation | Initial monitoring / response / fallback playbook complete; thresholds and unseen-regime robustness remain unvalidated. |
| Challenger specification / validation | Frozen diagnostic model, opt-in gate, quality rule, tests and rollback prepared. No deployment or promotion. |
| Forward matched comparison | Pending Sunday activation; no historical observations count as prospective evidence for this new version. |

Artifacts reside in the originating chat's outputs/six-week-calibration-2026-10-29
and outputs/option-path-review-2026-10-29 directories. Missing measurements are
not implied available by this status table. The master scope remains open for
the explicitly deferred comparisons.


## Option-return comparison implementation completion

The persistent baseline/challenger ledger and quote-trigger workflow are now
implemented and fixture-tested; see SHADOW_OPTION_COMPARISON.md. This supersedes
the earlier pending-ledger status. The proposed moderate-delta/IV configuration
remains an exploratory forward challenger, not a validated profitability claim.
Daily/minute integration, independent account state, costs, exits, atomic input
processing, equity history, data-quality records and rollback are prepared.
Activation remains disabled until the planned Sunday deployment and live job
preflight. Historical observations are not counted as prospective shadow trades.
