# Allocation architecture review — November 24, 2026

## Purpose and decision

Fine-tune a working investment process. The current engine is the benchmark:
retain its profitable research/contract-selection behavior unless an alternative
earns its place on net dollars, downside, capital use and operational reliability.
More complexity and more trading are not objectives. This document proposes an
architecture and records offline research; it does not activate a new allocator,
change risk tolerance, authorize funded trading or restart the experiment.

The question is larger than changing a ten-point deduction to five. A daily
portfolio decision must explain whether an opportunity is viable, what its
payoff evidence says, how current conditions change its risk, and whether its
incremental exposure is preferable to another holding or cash.

## Findings that motivate the review

The penalty sensitivity review reproduces all 43 recorded OPEN/ADD ticker sets
and quantities from September 25 through November 24. Removing the two-point
entry hurdle adds twelve recommendations; removing the incumbent ranking bonus
adds thirty-eight; reducing Defensive deductions to five adds nine. These are
daily selection sensitivities with actual incumbents held fixed, not alternate
cash-account profits. The Defensive classification appears only on four dates.

Actual 225 fully closed new-long groups earned $6,859.76 after allocated trading
fees; 55 groups scored 72–under 80 and earned $2,580. Win rate was 42.7%, with
average winner approximately $221 and average loser $111. Missing winners can
matter substantially. Zero allocations do not themselves create a loss; the
economic concern is forgone opportunities while incumbent exposure persists.

The offline architecture harness now separates 21,465 opportunity observations
across those 43 dates: allocated entries/adds, recorded-qualified capacity
blocks, score/operational blocks, existing-exposure/quantity limits, execution
failures, first-hour contradictions, unavailable data, event/oil guards, and
observations without a selected contract or complete evaluation. Every archived
reason remains attached. An unallocated observation is not automatically a
viable missed investment. Counts are repeated decisions, not independent trades.

## Proposed decision architecture

| Layer | Responsibility | Evidence and explanation |
|---|---|---|
| Feasibility | Establish whether this exact contract can be considered now | Correct contract, fresh valid price, executable market, data/event coverage, actual holdings and order state. Separate genuine inability from a score preference. Existing execution-score gates remain baseline controls pending direct-cost validation. |
| Opportunity | Preserve what stock and option attributes indicate | Raw research, trend/momentum, opening-hour behavior, delta/IV, premium, expiry and liquidity context. Keep quality separate from market deductions; 99 is a quality score, not a 99% success probability. |
| Payoff evidence | Estimate attainable reward/downside over the relevant horizon when supported | Actual broker returns for executed trades, exact-contract price-path diagnostics for observed alternatives, conditional support and uncertainty. Do not pool stock outcomes and actual option dollars as the same label. |
| Market and portfolio risk | Translate current conditions into incremental exposure | Continuous movement/volatility/breadth and thesis disagreement, contract sensitivities, scenario loss, direction-aware overlap, concentration, gap/full-premium risk and cash needs. Avoid counting the same market concern repeatedly without attribution. |
| Portfolio choice | Compare enter/add/retain/reduce/close/cash jointly | Whole-contract feasible quantities, available capital, incumbent replacement cost, marginal downside and opportunity cost. Evaluate an incumbent from its current price; sunk entry gains do not grant a free ranking bonus. |
| Explanation and learning | Record why the chosen feasible portfolio beat alternatives | Evidence timestamps, raw quality, uncertainty, actual dollar costs, risk budgets, binding constraints, alternatives, declined opportunities and later realized results. |

An unusually strong setup in an uncertain market may deserve a smaller position
rather than rejection. It may also deserve no position if a single contract
exceeds the risk budget, the price is not executable, or fresh evidence actually
contradicts the thesis. Those are specific explanations rather than hidden score
arithmetic. Hard capital/risk limits encode the owner's loss tolerance; they
must not be optimized upward from a short run of favorable returns.

## What changes conceptually

1. Market context becomes a risk/exposure input rather than automatically
   redefining the underlying opportunity's quality. The current three-relation
   SPY moving-average category cannot, by itself, distinguish an unusual rally
   from a calmer session. Recorded intraday return, price/VWAP behavior and
   relative volatility/breadth can describe those differences. A continuous
   mapping still needs declared assumptions and sensitivity checks; dynamism
   alone is not evidence of improvement.
2. Opening and replacing positions carry estimated dollar costs: spread,
   commissions, execution uncertainty and management/turnover effects.
   Preserve those separately from forecast quality. Review the two-point
   hurdle's hard eligibility effect and the five-point incumbent preference;
   a ranking tie-breaker should not quietly create a second admission threshold.
3. Compare current holdings and candidates on prospective remaining payoff and
   marginal risk. A higher entry score does not automatically justify closing a
   profitable incumbent or adding correlated exposure. Cash is a legitimate
   portfolio alternative, not a deployment failure.
4. A model with thin support does not silently replace the baseline with an
   all-cash policy. Unsupported research estimates remain unavailable/flagged;
   the current approved operating policy remains authoritative until an
   explicitly reviewed replacement is activated.

## Offline implementation and first model result

`src/adaptive_allocation_research.py` is an isolated research tool. No daily,
email, production allocator or frozen-shadow module imports it. It builds the
opportunity panel and tests an interpretable regularized payoff model on actual
long-option outcomes. Inputs are original research/institutional/execution
scores, delta, IV, spread, reference premium, market/breadth readings, directional
one-/three-/five-day stock moves and call/put direction. Market-score deductions
and the portfolio score are not used as predictors of payoff.

It trains only on trades whose broker exits occurred before each historical
decision. Feature imputation/scaling and regularization selection are fitted
inside that training window. Date weighting reduces domination by busy days;
inner chronological tuning is separate from outer evaluation. The initial
minimum of thirty closed groups and eight dates is a numerical research guard,
not a declaration of sufficient economic evidence. Missing/novel context is
flagged, and forecast errors are not advertised as calibrated probabilities.

Of 225 closed groups, 180 were evaluated after warmup across thirty dates.
Date-weighted mean absolute prediction error was 20.85 return percentage points,
versus 19.86 for the prior historical mean. A positive-forecast-only diagnostic
retained $-996.74 of those groups' actual net P/L versus $4,758.80 for keeping
all evaluated groups. It missed $8,483.80 of winning profits while avoiding
$2,728.26 of losses. This is a selected-trade screen with no alternative cash
propagation, not an assertion of a simulated account loss.

**Decision: reject this model as an allocation or sizing controller.** It does
not improve the benchmark and would discard too many demonstrated winners.
Do not conclude that adaptive allocation is impossible, that the working engine
has no edge, or that a larger black box is the next necessary step. This is
evidence against this particular replacement and for retaining the simple core.

## Include unallocated trades without manufacturing their profit

The actual-trade model is selection-biased: it sees outcomes of trades the
existing process allowed and Brian executed. It cannot establish expected
returns for rejected candidates. The broader panel is therefore a separate,
necessary comparison, with its own stock-outcome diagnostics and coverage.

- Link by exact source recommendation ID where recorded; older rows require a
  unique contract/date/entry/score inference. Ambiguity stays unresolved.
- Deduplicate stock outcomes chronologically into ticker/direction episodes;
  retain repeated decision records for portfolio/timing analysis. Episodes
  can appear under different decisions/cohorts and are not randomized groups.
- Keep liquidity/contract/data/event failures separate from score exclusions
  and otherwise qualified capital/concentration blocks.
- Use stock-direction outcomes to assess signal and exclusion patterns.
  Those outcomes do not measure the option's realized net return.
- Use exact-contract option observations only where coverage supports the
  stated diagnostic; retain missing paths, stale quotes and size uncertainty.
  Minute bids do not establish STD stop triggers or actual limit fills.
- Do not fit rejected-trade option-return labels from an unreliable simulator,
  proxy stock returns or trades entered later at different prices.

The opportunity panel includes scores, original reasons, raw attributes and
join/coverage status for both allocated and unallocated observations. Unmatched
or not-yet-mature rows are not wins/losses/zeros. The current stock outcomes reuse
the finalized November 19 artifact; November 20–24 decisions are not falsely
described as mature. No whole-history hindsight rebuild was required.

## Whole-portfolio comparison required for a revised policy

The following is the evaluation contract, not a claim that a complete alternate
portfolio return has already been established:

- Freeze candidate inputs, as-of holdings/cash/orders and policy lineage.
- Give each policy the same contemporaneous opportunity set, including viable
  unallocated alternatives; differences in bounded enrichment must be visible.
- Carry each policy's own inventory, quantities and cash forward. A policy that
  closes an incumbent must pay its costs and lose any later gains, not claim
  the new trade's upside while retaining the old book's outcome.
- Preserve entry ceilings, ordinary limits/STD stops, partial fills, missing
  observations and execution uncertainty; show coverage-qualified price-path
  scenarios separately from broker truth.
- Compare net dollars, payoff asymmetry, capital productivity, daily/weekly
  drawdown, tail exposure, diversification, turnover and missed-winning dollars.
  Win rate and point-forecast accuracy are supporting measures, not objectives.
- Validate chronologically by decision dates and policy version. Preserve every
  tested candidate and reserve subsequent dates for confirmation; do not search
  a large rule menu and call its retrospective winner a validated edge.

## Pre-deployment disposition

| Item | Disposition now |
|---|---|
| Profitable stock research and contract selection | Preserve as benchmark. |
| Arbitrary score deductions and anti-churn preference | Explicit policy review; exact values are not declared optimal. No automatic change. |
| Conditional learned payoff model | Implemented/tested offline; failed initial comparison; do not promote. |
| Broad allocated/unallocated evidence panel | Implemented, with cohort, source and maturity coverage. |
| Live continuous risk-based sizing / portfolio optimizer | Proposed design, not implemented or validated by these diagnostics. |
| Existing frozen shadows | Preserve unchanged as separate experiments. |
| Full alternate portfolio profit | Not established by a daily sensitivity or selected-trade screen. |
| Funded deployment | Explicit reviewed choice of strategy, sizing and operating controls; no silent new six-week delay or automatic approval. |

The practical fine-tuning path is to separate quality, costs and exposure in the
decision record, identify which overlapping adjustments actually earn their
place, and evaluate a bounded replacement against the current engine. This
preserves the existing edge as the benchmark while making the system more
explainable and responsive.

## Reproduce and verify

The dated outputs are in `reports/adaptive_allocation_research_20261124_v2/`:
`review.json` contains chronology, predictions and results; `opportunity_panel.json`
contains the full recorded opportunity population. The earlier first-pass
artifact remains preserved. Inputs are read-only and checksummed before/after.
Run the module's CLI with explicit attribution, penalty-review, journal,
hindsight and a new output directory. Ten fixtures cover leakage, missing-field
handling, date weighting, put/call orientation, cohort distinctions and dollar
accounting. No credentials, live orders or source datasets are rewritten.
All 322 repository tests, including those ten fixtures, passed. Input hashes,
225-group dollar totals, 180-group forecast accounting and chronological
training cutoffs were independently checked.
