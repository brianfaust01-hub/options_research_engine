# PROJECT STATUS — Project Stonks

**Version:** v0.3.0-alpha  
**Current Milestone:** Institutional Research Platform  
**Current Sprint:** Sprint 40A complete — Greek/IV shadow evidence collection active
**Status:** ACTIVE DEVELOPMENT

---

# Vision

Project Stonks exists to maximize long-term risk-adjusted returns by continuously learning which research signals, option structures, execution techniques, portfolio decisions, and risk management practices outperform through evidence—not intuition.

Project Stonks is not an options screener.

Project Stonks is an institutional-quality decision engine that:

- Generates investment ideas
- Constructs trades
- Evaluates execution quality
- Allocates capital
- Tracks outcomes
- Learns from historical performance
- Continuously improves itself

Every recommendation must produce a permanent research artifact regardless of whether capital is allocated.

Recommendations that are never executed are still valuable because they provide counterfactual evidence that improves future research, execution, and portfolio decisions.

The system learns from every hypothesis, not just executed trades.

---

# Governance

This document is the governing document for Project Stonks.

Every development session begins by reading this document.

Architecture will evolve.

Implementation details may change.

Engineering Principles, Vision, and Architectural Decision Records (ADRs) only change after explicit discussion.

Every sprint proposal must:

- Align with the Vision
- Reference the Engineering Principles
- Include regression validation
- Explain how it improves learning, confidence, execution, returns, or risk management

The Development Backlog in this document is the authoritative inventory of identified future work.

Backlog priority does not automatically determine sprint order.

Sprint selection should consider:

- Dependencies
- Learning value
- Data integrity
- Regression risk
- Development cost
- Alignment with the current milestone
- Evidence available to justify the work

---

# Long-Term Architecture

```text
Research Engine
        │
        ▼
Market Thesis
        │
        ▼
Strategy Optimizer
        │
        ▼
Contract Optimizer
        │
        ▼
Execution Engine
        │
        ▼
Trade Scoring Engine
        │
        ▼
Portfolio Allocation Engine
        │
        ▼
Paper Portfolio
        │
        ▼
Outcome Review
        │
        ▼
Learning Engine
        │
        ▼
Research Engine
```

The Learning Engine remains the center of the product.

Every release should strengthen this feedback loop.

---

# Current Capabilities

## Research

- Full S&P 500 scan
- Market regime analysis
- Market breadth analysis
- Trend engine
- Momentum engine
- Opportunity scoring
- Research confidence scoring

## Contract Selection

- Horizon-aware contract selection
- Liquidity-aware contract ranking
- DTE optimization
- Contract scoring
- Research pricing
- Schwab Market Data integration

## Execution

- Conservative execution modeling
- Bid/Ask spread analysis
- Execution scoring
- Execution grading
- Immediate liquidation analysis
- Research price vs expected fill comparison

## Trade Scoring

- Trade Quality Engine
- Institutional Trade Score
- Institutional Trade Grade
- Research component scoring
- Contract component scoring
- Execution component scoring
- Trade Quality component scoring

## Portfolio

- Paper portfolio
- Market-aware allocation
- Portfolio Score
- Position sizing
- Automatic portfolio ranking

## Learning

- Immutable recommendation snapshots
- Trade journal
- Complete research observation capture
- Outcome review
- Weekly learning reports
- Historical validation
- Structured learning dataset
- Counterfactual recommendation preservation
- Fixed 3/5/7/14/30-trading-day research outcomes
- Raw-observation and deduplicated thesis-episode analytics
- Score, Time Edge, direction, allocation, regime, and earnings calibration
- Confidence intervals, sample-size labels, and credibility warnings

## Automation

- Daily batch execution
- Windows Task Scheduler
- Automated journal updates
- Automated portfolio updates
- Automated weekly learning
- Automatic Schwab access-token renewal

---

# Current Milestone

## Institutional Decision Engine

Current focus:

- Institutional Trade Score
- Portfolio Decision Quality
- Learning Feedback
- Data Integrity

The current milestone should establish a reliable institutional-quality decision and learning foundation before significant strategy expansion.

---

# Current Research Priorities

The following concerns require explicit evidence and should guide sprint sequencing:

1. **Hindsight data credibility**
   - Determine which records are suitable for quantitative analysis, qualitative review, broker reconciliation, or operational evidence only.
   - Preserve imperfect historical records while making their limitations explicit.

2. **Daily allocation capacity**
   - Determine why `daily_run` consistently allocates only three trades.
   - Establish whether the result comes from an intentional risk budget, a fixed cap, portfolio constraints, candidate quality, liquidity gates, or unintended allocator behavior.
   - Do not increase trade count until portfolio-level risk and expected learning value justify it.

3. **Long-call concentration**
   - Determine whether long-call dominance is supported by market conditions and subsequent outcomes or caused by asymmetric research, strategy, or contract-selection logic.

4. **Liquidity discipline**
   - Recent progress eliminating low-liquidity trades is considered valuable and must be protected by regression validation.
   - Future changes to allocation capacity or strategy diversity must not weaken execution-quality and liquidity standards merely to produce more trades or more variety.

5. **Daily-run latency**
   - The daily workflow becomes extremely slow after entering the Opportunity Engine stage.
   - Measure stage, candidate, contract-selection, and external market-data latency before changing implementation.
   - Preserve recommendation completeness, contract quality, liquidity discipline, and API reliability while improving runtime.

---

# Recent Sprint Records

## Sprint 40A — Greek & Volatility Observation Integrity

### Objective

Build trustworthy Greek and implied-volatility evidence before tuning live
configuration, while leaving contract selection, scoring, and allocation
behavior unchanged.

### Implemented

- Schwab delta, gamma, theta, vega, and rho are preserved as broker fields;
  the legacy delta/theta estimates remain separately labeled and continue to
  drive existing production behavior
- Recommendations, the trade journal, immutable observation snapshots, and
  research hindsight now carry the structured Greek and IV fields
- Theta drag, gamma exposure, and vega exposure are normalized by contract
  premium for cross-contract comparison
- IV rank and percentile are explicitly marked `UNAVAILABLE_NO_HISTORY`
  instead of being inferred from a single quote
- Read-only hindsight analytics now calibrate broker delta, normalized theta,
  normalized gamma, normalized vega, and IV across 3, 5, 7, and 14 trading-day
  outcomes

### Guardrails and Validation

- Shadow research only: no production weights, gates, contract scores,
  position sizing, or allocation decisions changed
- Broker observations are never overwritten by estimates
- Full regression suite: 42 tests passed
- Do not tune Greek or IV configuration until approximately two weeks of new
  observations mature and sample-size/status warnings are reviewed

---

## Sprint 39B — Hindsight Analytics & Score Calibration

### Objective

Convert preliminary win-rate analysis into a reproducible, read-only learning
system that measures every directional recommendation, including unallocated
recommendations, without inflating confidence through repeated ticker theses.

### Evidence and Learning Value

- The August 7 hindsight file contained 9,019 records and 5,305 evaluable
  directional observations, but only 17 recommendation-date cohorts
- The legacy 51.3% directional win rate classified any return above zero as a
  win and did not expose fixed trading-session horizons
- Repeated recommendations for the same ticker and direction were separate
  observations even when they represented one continuing thesis
- Preliminary results suggested stronger performance around 4–7 days, but
  production scoring changes would be premature without standardized horizons
- Confidence and bearish-result samples require explicit calibration and
  minimum-sample warnings

### Implemented

- Research hindsight now records exact 3, 5, 7, 14, and 30 trading-session
  outcomes in addition to the backward-compatible current and final results
- Each fixed horizon preserves raw return, direction-adjusted return, SPY
  return, alpha, maximum favorable/adverse excursion, evaluation date, legacy
  direction result, magnitude-aware result, and first meaningful threshold hit
- Meaningful outcomes distinguish at least +1% wins, at most -1% losses,
  ±0.25% noise, and smaller directional moves while preserving the legacy
  above/below-zero classification
- Hindsight output now preserves Research Score, Time Edge, directional
  conviction, bullish/bearish scores, Institutional Trade Score, execution
  score, allocation state/rank, market regime, and earnings context when those
  fields exist in the source observation
- A new read-only analytics subsystem assigns contiguous ticker/direction
  recommendations to thesis episodes, with a new episode after a direction
  change or seven-calendar-day reset
- Reports present raw-observation and first-observation-per-episode performance
  separately, with Wilson 95% win-rate intervals and preliminary/credible
  sample labels
- Calibration tables cover direction, confidence, Research Score, Time Edge,
  Institutional Trade Score, directional conviction, allocation decision,
  market regime, and earnings status
- Daily action emails can display the latest precomputed 7-day research-health
  summary, explicitly labeled as not trading guidance; email generation never
  launches the expensive hindsight market-data workflow
- Daily research health distinguishes all directional recommendations,
  allocated recommendations, known unallocated recommendations, and
  deduplicated thesis episodes, with evaluated sample size and credibility
  status beside each win rate
- Latest-version allocated performance is displayed separately so legacy
  behavior is not silently blended with the current implementation; immature
  recommendations remain excluded until their seven-day horizon completes
- Historical option-contract counterfactuals are explicitly marked unavailable
  when option quote paths do not exist; underlying returns are never mislabeled
  as option returns

### Data Integrity

- Historical recommendations and snapshots remain immutable
- Watch, Pass, non-executable, and unallocated evidence remains preserved
- Only directional observations enter win/loss calculations
- Incomplete horizons remain in progress and are excluded from evaluated win
  rates
- Analytics do not modify scoring, allocation, portfolio, journal, or execution
  behavior
- Output generation is timestamped and read-only with respect to its sources

### Regression Risks and Controls

- Off-by-one trading-horizon risk is controlled by tests that distinguish the
  entry session from N completed sessions after entry
- Bullish/bearish sign reversal is tested directly
- Repeated-thesis inflation is controlled by deterministic episode tests
- Missing fixed-horizon fields remain backward compatible and produce an
  explicit regenerate-hindsight warning
- Email output labels research health separately from actionable guidance
- Full regression suite passed: 39 tests

### Success Criteria

- Every directional recommendation can receive reproducible fixed-horizon
  outcomes: complete
- Raw and deduplicated performance remain separate: complete
- Confidence intervals and minimum-sample warnings are visible: complete
- New Time Edge and existing scores are measurable without changing weights:
  complete
- Call/put direction is independently attributable: complete
- Missing historical option paths are explicit rather than inferred: complete
- Production behavior remains unchanged: complete
- Refreshed live hindsight and first populated fixed-horizon analytics report:
  complete; daily email comparison active

## Sprint 39A — Time Edge, Earnings Guard, and Shadow Risk Sizing

### Objective

Make speed of thesis resolution a bounded component of institutional decision
quality while retaining long calls and long puts as the defined-risk strategy
universe and separating short holding horizon from contract expiration runway.

### Implemented

- Production long-premium contract selection now enforces at least 45 DTE
- Shadow Time Edge combines momentum, trend, directional conviction,
  ATR-normalized price acceleration, volume confirmation, signal freshness,
  and fresh 20-day breakout/breakdown state
- Expected move windows are 5, 7, or 14 trading days
- Time Edge contributes 10% only to a shadow score and does not replace the
  existing institutional or portfolio assessment
- Conservative, Balanced, and Aggressive shadow contract counts use bounded
  conviction, execution quality, spread stress, risk budget, and premium caps
- Production quantity remains unchanged while shadow sizing is validated
- Live earnings dates are cached through the existing market-data dependency
- Confirmed earnings inside the thesis window blocks a new allocation and
  promotes the next-ranked eligible candidate
- Current positions receive an earnings check; earnings inside the thesis
  window produces a SELL action because earnings strategies remain disabled
- Position review now reports Day N of M, thesis deadline, and earnings date
- The action email displays Time Edge, expected holding window, earnings date,
  and all three shadow sizes with an explicit research-only label
- One-, three-, and five-day returns plus all Time Edge inputs flow into the
  journal and immutable observation snapshots

### Safety and Data Integrity

- Enabled strategies remain Long Call and Long Put; short option selling is not
  introduced
- Missing earnings data is shown as UNKNOWN and requires manual confirmation
  rather than being silently treated as safe
- Shadow sizing cannot change executable production quantity
- Historical observations and recommendation snapshots are not rewritten
- Earnings is an event-risk guard, not an earnings-event trading strategy

### Initial Operational Evidence

- Live earnings lookup returned October 22 for PCG and F
- Live earnings lookup returned August 26 for NVDA, confirming the need for
  current-position event guidance before tomorrow's report

### Validation

- Fast-thesis, earnings-block, unknown-date, replacement-allocation,
  45-DTE-floor, position-deadline, and current-position earnings fixtures pass
- Full regression suite passes without a production research run
- First live shadow output remains pending tomorrow's scheduled run

## Sprint 38A — Flat-Portfolio Email Reliability

### Finding

The August 24 scheduled scan completed, but report generation failed before
email delivery because a flat portfolio produced an empty position-actions
CSV and pandas raised `EmptyDataError`.

### Implementation

- Empty position-action CSVs are handled as a valid zero-position result
- A present empty file no longer produces a false "position analysis
  unavailable" warning
- Missing position-analysis files still retain the operational warning
- The latest completed recommendations can be rebuilt and sent without
  rerunning research or creating duplicate recommendations

### Validation

- Controlled empty-file/flat-portfolio regression passed
- Existing allocated-trade and position-action email regression passed
- Full suite of 26 tests passed
- Today's completed recommendation file rebuilt successfully
- Production research and portfolio state were not rerun or modified

## Sprint 37B — Reviewed Trade Attribution

### Objective

Separate broker P/L from its reviewed causal attribution so hindsight can
distinguish strategy evidence from known execution/process failures.

### Reviewed Rule

The account owner classified any realized option-premium loss worse than 20%
as an execution/process error. This label adds context; it does not remove or
alter the loss in broker or account performance.

### Evidence

- All 28 broker round trips retain their actual fills and gross P/L
- 26 trades have confirmed Project Stonks allocation evidence
- One additional C trade matches a Project Stonks recommendation but lacks
  preserved allocation evidence
- WRB remains source-unclassified rather than being guessed
- Eight trades breached the reviewed execution-error threshold and lost
  $3,021 gross
- The other 20 trades produced $1,220 gross
- Combined gross P/L remains exactly -$1,801 before fees

### Data-Integrity Decision

Trade source and outcome attribution are separate fields. A trade not labeled
as an execution error is not automatically declared a valid strategy outcome.
Attribution is stored in a new v2 artifact; the v1 broker reconciliation and
original statement remain unchanged.

### Validation

- Controlled attribution fixture preserves the original loss
- Threshold and reviewed source labels are explicit in the artifact
- Full regression suite passed without writing journal or snapshot history

## Sprint 37A — Thinkorswim Broker Reconciliation

### Objective

Establish broker execution truth as a separate, non-destructive evidence layer
for hindsight analysis and portfolio-state review.

### Implemented

- Read-only Thinkorswim Account Trade History schema detection and normalization
- FIFO pairing of option opening and closing executions by exact contract
- Broker entry, exit, date, quantity, order type, and gross P/L preservation
- Exact-contract comparison with the Project Stonks paper portfolio
- Explicit stale-open detection without modifying portfolio or journal records
- Preservation of unmatched broker round trips for manual attribution review
- Optional versioned JSON output that refuses to overwrite an existing report

### Initial Reconciliation Evidence

- 56 broker executions normalized into 28 completed round trips
- Zero broker-open option positions in the supplied statement
- All six Project Stonks positions still marked OPEN matched completed broker trades
- Matched gross P/L for those six round trips was -$118 before fees
- 22 additional broker round trips remain deliberately unmatched pending attribution

### Data-Integrity Decision

Broker records do not overwrite recommendation history, modeled execution, or
portfolio state. Strategy-versus-execution attribution remains explicitly
`REQUIRES_USER_REVIEW`; the importer does not infer causality from P/L alone.

### Validation

- Controlled FIFO P/L and stop-order fixture passed
- Controlled stale-open detection confirmed the input portfolio is unchanged
- Eight existing hindsight-integrity regressions passed
- Real export produced the expected 56 executions, 28 round trips, and six
  stale-open matches
- Production portfolio, journal, logs, and historical snapshots were not written

### Remaining

- Review attribution of the 22 unmatched broker round trips
- Extend the append-only reconciliation artifact with reviewed attribution

### Approved State Application

- The reviewed reconciliation artifact was stored before portfolio correction
- A, IR, NVDA, PCG, TFC, and TSN were changed from OPEN to CLOSED using their
  broker-reported exit timestamps and fill prices
- Exit reason is explicitly `BROKER_RECONCILED_CLOSE`
- The paper portfolio now contains zero open positions

## Sprint 36A — Execution-Oriented Daily Email

### Objective

Turn the daily report into a concise call to action that supports manual order
entry without confusing watchlist research with allocated recommendations.

### Implemented

- HTML action brief with a plain-text fallback
- Current-position HOLD, REVIEW, and SELL analysis with reason, current price,
  P/L, target, stop, and DTE
- New-order section restricted to trades explicitly marked `Allocate`
- Contract direction, expiration, strike, quantity, entry limit, profit-target
  exit, stop-loss exit, time stop, maximum risk, and quality grades
- Run-health warnings when recommendations, position analysis, or live option
  pricing are unavailable
- Detailed recommendation and position-action CSV attachments
- Persisted the enriched position-action output separately from the outcome
  review snapshot
- The standard batch entry point now runs the complete scan, action-report,
  and email workflow
- Interactive email setup stores credentials in the Windows user environment
  without printing the app password
- A test-send command rebuilds the brief from the latest completed scan and
  does not create new recommendations or portfolio records

### Safety Decision

The current bid is no longer presented as a future exit target. The action
brief distinguishes the entry limit, profit-target exit, and stop-loss exit.
Only allocated trades appear in the order-entry section; Watch and No
Allocation candidates remain research evidence outside that section.

### Validation

- Controlled fixture confirms an allocated Long Put appears with calculated
  entry, target, and stop prices
- Watch-only candidate is excluded from the order-entry section
- Position recommendation and rationale are included
- Twenty-one regression tests passed
- Tests did not modify production data

### Remaining

- Run the scheduler setup under the user's Windows account
- Confirm the first unattended run and email delivery
- Add an exchange-holiday guard before treating holiday suppression as complete

## Sprint 35D — Daily Run Opportunity Pipeline Latency

### Finding

Contract selection repeatedly downloaded the full Schwab option chain. Each
actionable ticker used one chain request to discover expirations and then up
to eight more full-chain requests while scoring those expirations.

### Implementation

- Fetch one normalized option-chain snapshot per actionable ticker and reuse
  it across expiration filtering and contract scoring.
- Preserve the existing retry behavior for the consolidated chain request.
- Add in-memory timing for the opportunity pipeline and contract selection.
- Report candidate count, average contract-selection time, and actual quote
  and option-chain request attempts at the end of the stage.
- Keep scoring weights, expiration limits, liquidity rules, contract ranking,
  and allocation behavior unchanged.

### Validation

- A controlled two-expiration fixture uses one chain request rather than
  three; the same design caps the normal eight-expiration path at one rather
  than nine chain requests per ticker.
- Retry attempts are preserved and counted.
- Partial option-chain data safely produces no selected contract.
- Twenty regression tests passed, including retry and partial-data fixtures.
- Production journal, paper portfolio, weekly log, and historical snapshots
  were not modified.

### Operational Follow-up

The next normal daily run will provide the first live timing baseline. Review
its reported totals before considering bounded concurrency or API batching.

## Sprint 35C — Directional Momentum Scoring Correction

### Decision

Correct the production defect confirmed in Sprint 35B. Strategy variety is
not forced: put candidates must clear the same score and conviction gates as
call candidates.

### Implementation

- The Research Engine now preserves `MomentumDirection` separately from the
  momentum strength score.
- The Opportunity Engine applies momentum points to the preserved direction.
- Older callers fall back to overall research direction; callers with neither
  field retain legacy compatibility.
- Existing opportunity thresholds, liquidity gates, contract selection, and
  allocation limits remain unchanged.
- `MomentumDirection` is retained in the preferred journal column order for
  future hindsight analysis.

### Validation

- Strong bearish trend plus strong bearish momentum can clear the Long Put
  candidate gate.
- Low momentum strength no longer creates artificial bearish conviction.
- Explicit component direction takes precedence over overall consensus.
- No call/put quota or minimum strategy mix was introduced.
- Production journal, paper portfolio, weekly log, and historical snapshots
  were not modified during validation.

## Sprint 35B — Long-Call Concentration Review

### Finding

Long-call dominance originates in the Opportunity Engine before contract selection or portfolio allocation.

The Research Engine produces a directional label and a momentum magnitude, but the Opportunity Engine ignores the directional label. A high MomentumScore is always awarded bullish points even when the Research Engine determined that bearish momentum produced the score.

### Historical Evidence

The read-only audit examined the 20 most recent processed recommendation files:

- 6,884 total recommendations
- 3,045 Pass recommendations
- 1,440 Watch recommendations
- 2,399 Long Call candidates
- Zero Long Put candidates
- 851 Long Calls survived contract selection
- 1,548 Long Call candidates failed contract selection
- 33 Long Calls were allocated
- Zero Long Puts reached any reviewed downstream stage

### Structural Evidence

- Changing only the Research Engine Direction between Bullish and Bearish does not change Opportunity Engine scoring
- A strong bearish fixture with TrendScore 0 and MomentumScore 80 produces BearishScore 65, below the 75 put threshold
- The same high bearish momentum magnitude contributes 35 bullish points
- A low MomentumScore of 20 can produce BearishScore 100, demonstrating that magnitude is interpreted as direction

### Decision

The current behavior requires recalibration, not strategy expansion for variety.

Do not change production thresholds or weights immediately. First preserve separate bullish and bearish research components, generate corrected decisions in shadow mode, and compare them with current recommendations and subsequent outcomes.

### Validation

- Read-only stage-attrition audit added
- Current opportunity scoring was extracted into a diagnostic function without behavior changes
- Fifteen regression tests passed
- Production journal, paper portfolio, and weekly log hashes were unchanged

### Limitations

- Legacy processed files do not preserve directional component scores
- Reviewed files include repeated intraday runs
- Market regime may legitimately influence the observed direction mix
- Outcome performance and broker execution are not reconciled

## Sprint 35A — Daily Allocation Capacity Review

### Finding

The three-trade result is an explicit allocator limit, not an emergent portfolio decision.

- `portfolio_allocator.py` defaults to three recommendations
- `config.py` declares a five-trade counterfactual capacity but the allocator does not consume it
- Production allocation behavior was not changed

### Historical Evidence

The read-only audit examined the 20 most recent processed recommendation files:

- 11 runs contained ranked executable candidates
- Every such run allocated exactly three trades
- 22 valid rank-four and rank-five counterfactual candidates were identified
- Counterfactual candidates averaged a Portfolio Score of 80.57
- Maximum counterfactual spread was 14.49%, near the existing 15% ceiling
- Minimum counterfactual open interest was 167
- All 851 ranked candidates were Long Calls
- All 22 rank-four and rank-five candidates were Long Calls
- The Opportunity Engine produced 2,399 Long Call candidates and zero Long Put candidates in the reviewed files

### Decision

Retain the production limit of three.

Increasing the limit now would add directional long-call concentration without evidence of portfolio diversification. Sector and industry data are frequently unknown, existing holdings are not incorporated into allocation, correlation is not measured, and broker execution is not reconciled.

The five-trade value remains a counterfactual research capacity, not a production instruction.

### Validation

- Read-only allocation audit added
- Allocation ineligibility reasons are explicitly attributable
- Fixtures confirm the production allocator still selects exactly three
- Fixtures identify ranks four and five without changing their decisions
- Eleven regression tests passed
- Production journal, paper portfolio, and weekly log hashes were unchanged

## Sprint 34A — Hindsight Data Integrity & Provenance

## Sprint 34A — Hindsight Data Integrity & Provenance

### Objective

Preserve complete decision context going forward while keeping imperfect historical evidence immutable, explicit, and analytically interpretable.

### Scope

- Persist ResearchScore, OpportunityScore, BullishScore, BearishScore, and DirectionalConviction
- Add observation schema generation and provenance metadata
- Classify incomplete observations instead of rejecting or rewriting them
- Keep broker execution truth separate from system recommendation and modeled execution truth
- Provide a read-only historical data-quality audit
- Add fixture-based regression validation that cannot modify production data

### Historical Record Policy

Historical records are not required to be correct or complete.

They are required to remain truthful to what the system produced or knew at the time. Corrections, broker reconciliation, and later interpretations must be stored separately with their source, reason, and confidence.

### Regression Risks

- Dropping Pass, Watch, non-executable, or unallocated recommendations
- Rewriting immutable snapshots or journal rows
- Changing production scoring while adding context fields
- Conflating modeled execution with Thinkorswim / Schwab broker execution
- Breaking older schemas or consumers through field renaming

### Validation

- Required context propagates through Research, Opportunity, Trade, Journal, and Snapshot layers
- Missing context produces an explicit PARTIAL classification rather than data loss
- Snapshot schema v4 records provenance and quality state
- Tests use temporary fixtures and do not write production data
- Historical audit remains read-only

### Validation Result

- Controlled Research → Opportunity → Trade → Journal Assembly → v4 Snapshot test passed
- ResearchScore, OpportunityScore, BullishScore, BearishScore, and DirectionalConviction were present
- Snapshot and observation quality status were COMPLETE
- Recommendation provenance and broker reconciliation state were explicit
- Eight fixture-based regression tests passed
- Source and test compilation passed
- Production journal, paper portfolio, and weekly log hashes were unchanged

---

# Product Roadmap

## Phase 1 ✅ — Build the Engine

Completed:

- Research Engine
- Options Engine
- Contract Selection
- Paper Trading
- Automation

## Phase 2 ✅ — Build the Scientist

Completed:

- Learning Pipeline
- Weekly Learning
- Immutable Research History
- Outcome Review
- Execution Analysis

## Phase 3 — Build the Institutional Portfolio Manager

**Current**

Focus:

- Institutional Trade Scoring
- Portfolio Allocation
- Execution Quality
- Portfolio Decision Quality
- Portfolio diversification
- External performance reconciliation

## Phase 4 — Adaptive Portfolio Management

Future:

- Correlation management
- Sector balancing
- Industry balancing
- Adaptive position sizing
- Strategy optimization
- Learning-driven score optimization
- Portfolio optimization

---

# Completed Sprints

## Sprint 30A

- Recommendation snapshots
- Learning validation
- Weekly learning
- Outcome review

## Sprint 31A

- Atomic journal writes
- Snapshot integration
- Journal repair utilities
- Data integrity validation

## Sprint 32A

- Execution scoring
- Bid/Ask analysis
- Execution grades
- Conservative pricing
- Execution reporting

## Sprint 33A

- Institutional Trade Score
- Institutional Trade Grade
- Component scoring
- Trade scoring engine

## Sprint 33B

- Portfolio Score
- Allocation refactor
- Market-aware portfolio ranking
- Institutional Trade Score integration

## Sprint 33C

- Single risk budget
- Simplified position sizing
- Position sizing cleanup

## Sprint 34A

- Complete hindsight context propagation
- Observation schema v4
- Data-quality classification and provenance
- Read-only historical integrity audit
- Controlled non-production observation validation
- Production-data immutability verification

## Sprint 35A

- Confirmed explicit three-trade production limit
- Added allocation-gate attribution
- Added read-only rank-four/five counterfactual audit
- Preserved liquidity and execution standards
- Retained production limit pending holdings and diversification context
- Confirmed long-call concentration originates upstream of allocation

## Sprint 35B

- Quantified recommendation and strategy mix
- Located first zero-put stage in the Opportunity Engine
- Identified directional-information loss in MomentumScore handling
- Added read-only stage-attrition and structural diagnostics
- Recommended directional score preservation and shadow evaluation
- Preserved production scoring behavior

## Sprint 35C

- Preserved momentum direction as a first-class research field
- Corrected bearish momentum attribution in production opportunity scoring
- Enabled evidence-qualified Long Put candidates without a strategy quota
- Preserved thresholds, liquidity discipline, contract gates, and allocation cap

## Sprint 35D

- Reused one option-chain snapshot across all scored expirations per ticker
- Added opportunity-stage and per-candidate latency reporting
- Added external quote and chain request-attempt counts
- Preserved retry behavior and contract-selection standards

---

# Development Backlog

This is the authoritative development backlog for Project Stonks.

Items enter the backlog when a capability, defect, technical-debt item, experiment, or architectural improvement is identified but is not part of the active sprint.

Backlog priority does not automatically determine implementation order.

An item may move ahead of a higher-priority item when dependencies, data integrity, learning value, or regression risk justify doing so.

---

# P0 — Blocking / Data Integrity

Items that threaten production operation, historical evidence, research integrity, or the learning loop.

## Complete Hindsight Observation Context

**Type:** Data Integrity / Learning  
**Status:** Completed — Sprint 34A

### Objective

Ensure every historical research observation contains the complete decision context required for future hindsight analysis.

### Known Fields to Validate

- ResearchScore
- OpportunityScore
- BullishScore
- BearishScore
- DirectionalConviction

### Why

Historical evidence cannot be reconstructed accurately if the scores responsible for a recommendation are missing.

The immutable recommendation dataset must preserve both the final decision and the information that produced it.

### Success Criteria

- All required research scores persist in historical observations
- Values are preserved in immutable snapshots where appropriate
- Pass, Watch, executable, and non-executable recommendations retain sufficient decision context
- Regression validation confirms no loss of existing journal fields

---

# P1 — Next

Highest-value work expected to be considered for upcoming sprints.

## Investment Philosophy Review

**Type:** Architecture / Research Strategy  
**Status:** Backlog

### Objective

Reassess whether Project Stonks should continue operating as a broad S&P 500 directional-options research platform or deliberately narrow its investment mandate.

### Core Question

Are we building a broadly capable institutional decision engine too early, when a narrower strategy could be learned and optimized more effectively?

### Strategies / Universes to Evaluate

- Full S&P 500 directional-options platform
- Smaller highly liquid equity universe
- Mega-cap options universe
- SPY-only systematic options strategy
- SPY plus a small ETF basket
- One highly constrained directional strategy optimized deeply before expansion

### Evaluation Criteria

- Sample size generated per strategy
- Signal consistency
- Execution quality
- Data quality
- Ability to conduct meaningful hindsight
- Risk-adjusted paper performance
- Complexity
- Overfitting risk
- Development velocity
- Statistical learning speed
- Whether breadth improves or dilutes the learning loop

### Success Criteria

- Written investment mandate for Project Stonks
- Explicit rationale for broad vs narrow scope
- Defined strategy and universe boundaries
- Identification of evidence required before future expansion
- Roadmap updated to reflect the resulting investment philosophy

---

## Schwab Greeks Integration

**Type:** Capability / Data  
**Status:** Backlog

### Objective

Ingest Schwab-provided option Greeks and preserve them throughout the contract-selection, trade-scoring, journaling, snapshot, and hindsight pipelines.

### Initial Data

At minimum evaluate ingestion of:

- Delta
- Gamma
- Theta
- Vega
- Rho
- Implied volatility

### Why

Broker-provided Greeks provide richer information about option exposure and contract behavior than simplified proxies.

The immediate objective is not necessarily to change production scoring.

The first objective is to **capture the information historically** so Project Stonks can determine whether these variables predict outcomes.

### Success Criteria

- Schwab Greeks ingested
- Fields normalized through the Market Data layer
- Greeks available to Contract Optimizer
- Greeks available to Trade Scoring Engine
- Greeks preserved in trade journal
- Greeks preserved in immutable recommendation snapshots
- Greeks available to hindsight analysis
- Existing contract-selection behavior regression-tested
- No production weighting changes until evidence supports them

---

## Paper Trading Performance CSV Import

**Type:** Capability / Data Integrity  
**Status:** Completed — Sprint 37A

### Objective

Support importing actual paper-trading execution and performance data from ThinkOrSwim / Schwab via CSV.

### Why

Project Stonks internally models paper positions, but broker-exported performance provides an external source of truth for:

- Actual fills
- Entry prices
- Exit prices
- Position quantities
- Realized P/L
- Trade dates
- Execution behavior

This provides an important reconciliation layer between Project Stonks recommendations and simulated broker activity.

### Success Criteria

- CSV schema detection and normalization
- Imported trades matched to Project Stonks recommendations where possible
- Entry prices reconciled
- Exit prices reconciled
- Dates reconciled
- Quantities reconciled
- Realized P/L captured
- Unmatched broker records preserved for review
- Import does not overwrite immutable recommendation history
- Reconciled results become available to hindsight and learning

---

## Investment Guidance / Strategy Diversity Review

**Type:** Research / Product  
**Status:** Completed — Sprint 35B

### Objective

Evaluate why Project Stonks has overwhelmingly recommended long calls and determine whether the current strategy-selection architecture is genuinely identifying the best expression of each investment thesis.

### Current Concern

Project Stonks has generated almost exclusively long-call recommendations for an extended period.

This may indicate:

1. Market conditions genuinely favor bullish positions
2. Bearish opportunity thresholds are too difficult to trigger
3. Research scoring structurally favors bullish signals
4. Put-selection logic is underdeveloped
5. Strategy-selection logic is biased toward long calls
6. Alternative option structures are not sufficiently developed to compete

### Questions to Answer

- What percentage of actionable recommendations are calls vs puts?
- How has that ratio changed across market regimes?
- Which gates prevent put recommendations?
- Are bearish opportunities becoming Pass or Watch recommendations instead?
- Are puts being identified but rejected by contract selection?
- Is long-call dominance supported by subsequent outcomes?
- Would alternative structures have improved risk-adjusted performance?
- Does the current implementation deserve to be considered a Strategy Optimizer?

### Success Criteria

- Quantitative attribution of recommendation mix
- Identification of where bearish recommendations disappear from the pipeline
- Determine whether long-call dominance is evidence-driven or architectural
- Recommendation for whether strategy logic should:
  - remain unchanged,
  - be recalibrated,
  - or be expanded
- No strategy expansion solely for the purpose of producing variety

---

## Directional Score Preservation & Shadow Evaluation

**Type:** Research Integrity / Model Validation  
**Status:** Backlog — after Daily Run Latency Review

### Objective

Preserve distinct bullish and bearish research components and evaluate a corrected directional opportunity model in shadow mode before changing production recommendations.

### Scope

- Preserve bullish and bearish trend components
- Preserve bullish and bearish momentum components
- Preserve the research direction consumed by opportunity scoring
- Produce current-model and shadow-model decisions side by side
- Capture disagreement reason, score deltas, and threshold outcomes
- Evaluate calls, puts, Watch, and Pass decisions without executing shadow recommendations

### Success Criteria

- No directional magnitude is interpreted without its direction
- Current production recommendations remain unchanged during shadow evaluation
- Shadow recommendations are persisted as non-executable analytical evidence
- Recommendation disagreement is quantitatively attributable
- Liquidity and contract-selection standards remain unchanged
- Production changes require explicit evidence-based approval

---

## Institutional Trade Score Validation

**Type:** Learning / Model Validation  
**Status:** Backlog

### Objective

Determine whether Institutional Trade Score predicts subsequent trade quality and risk-adjusted performance.

### Questions

- Do higher-scored trades outperform lower-scored trades?
- Is the relationship monotonic?
- Which score components provide predictive value?
- Which components add noise?
- Does predictive performance change by market regime?
- Does execution quality modify the relationship?

### Success Criteria

- Performance grouped by score bands
- Statistical comparison across score ranges
- Component attribution
- Regime attribution
- Evidence-based recommendation before changing production weights

---

## Daily Allocation Capacity Review

**Type:** Portfolio Decision Quality / Research  
**Status:** Completed — Sprint 35A

### Objective

Explain why daily runs consistently allocate three trades and determine whether the observed limit is intentional, evidence-supported, and appropriate for the portfolio.

### Questions

- Is three an explicit configuration limit or an emergent result?
- Which candidates would be selected if the limit were higher?
- Which gates reject otherwise executable fourth and later candidates?
- Does the current risk budget support more simultaneous allocations?
- Would additional allocations increase independent learning samples or merely add correlated exposure?
- Do rejected candidates satisfy current liquidity and execution standards?
- How would existing holdings change the decision?

### Success Criteria

- Quantitative attribution of every allocation rejection
- Counterfactual ranking beyond the third allocated trade
- Portfolio-risk and concentration comparison for alternative allocation counts
- Confirmation that liquidity standards remain unchanged
- Evidence-based recommendation to retain, remove, or replace any fixed trade-count limit
- No production allocation-cap change during the review

---

## Daily Run Opportunity Pipeline Latency Review

**Type:** Performance / Reliability  
**Status:** Completed — Sprint 35D; live-run validation pending

### Objective

Identify and correct the dominant causes of daily-run latency observed after the workflow enters the Opportunity Engine stage.

### Initial Hypothesis

Opportunity scoring itself is computationally small, but each actionable candidate immediately enters trade construction, contract selection, execution analysis, and external market-data access. The visible stage boundary may therefore attribute downstream serial work to the Opportunity Engine.

This is a hypothesis to measure, not a conclusion.

### Questions

- How much time is spent in opportunity scoring versus trade construction?
- How many option-chain and quote requests occur per daily run and per candidate?
- Are external requests serialized, duplicated, retried, or rate-limited?
- Are non-actionable candidates performing unnecessary downstream work?
- Can safe caching, request reuse, batching, or bounded concurrency reduce latency?
- Does token renewal or authentication contribute material delay?
- How does candidate count affect total runtime?
- Can performance improve without weakening liquidity or contract-selection standards?

### Success Criteria

- Stage-level and per-candidate timing instrumentation
- External request counts and latency attribution
- Reproducible baseline using a controlled non-production run
- Identification of the dominant latency contributors
- Measured performance improvement with unchanged recommendations on a fixed fixture
- No reduction in liquidity, execution, or contract-quality validation
- No production scoring or allocation behavior change
- Regression validation for failures, retries, rate limits, and partial market data

---

## Sector Concentration Engine

**Type:** Portfolio Risk  
**Status:** Backlog

### Objective

Prevent the allocator from constructing portfolios with excessive exposure to one sector.

### Success Criteria

- Sector exposure calculated before allocation
- Existing holdings included
- Candidate allocations evaluated against resulting concentration
- Concentration incorporated into Portfolio Score or allocation gating
- Historical observations preserve concentration context

---

## Industry Concentration Engine

**Type:** Portfolio Risk  
**Status:** Backlog

### Objective

Identify and control concentrated exposure to companies with similar underlying economic drivers even when broad sector classifications appear diversified.

### Success Criteria

- Industry exposure tracked
- Existing holdings included
- Candidate trades evaluated for incremental concentration
- Allocation decision preserves concentration context for hindsight

---

## Portfolio Correlation Engine

**Type:** Portfolio Risk  
**Status:** Backlog

### Objective

Evaluate correlation between proposed positions and existing portfolio exposure.

### Why

Ticker diversification does not guarantee risk diversification.

Multiple securities may produce effectively identical portfolio exposure.

### Success Criteria

- Historical-return correlation calculated
- Existing holdings included
- Candidate incremental correlation measured
- Portfolio Score can incorporate correlation penalties
- Learning dataset preserves correlation context

---

## Existing Holdings Integration

**Type:** Portfolio Decision Quality  
**Status:** Backlog

### Objective

Ensure new allocation decisions fully consider existing portfolio positions rather than evaluating recommendations independently.

### Success Criteria

- Existing risk exposure incorporated before new allocation
- Existing sector exposure incorporated
- Existing industry exposure incorporated
- Existing correlation incorporated when available
- Position-level and portfolio-level risk evaluated together

---

## Broker Reconciliation

**Type:** Data Integrity / Execution  
**Status:** Completed — Sprint 37A

### Objective

Reconcile Project Stonks portfolio state with ThinkOrSwim / Schwab paper-trading state.

### Dependencies

Paper Trading Performance CSV Import may provide the initial implementation path.

### Success Criteria

- Detect missing broker positions
- Detect Project Stonks positions absent from broker
- Detect quantity mismatches
- Detect price mismatches
- Detect closed positions
- Preserve reconciliation history
- Never silently modify immutable research history

---

# P2 — Planned

Important capabilities with no immediate implementation requirement.

## Learning-Driven Score Weights

**Type:** Learning / Optimization  
**Status:** Backlog

Use accumulated historical outcomes to evaluate whether scoring weights should change.

Production weights must never change automatically.

The Learning Engine proposes changes supported by evidence.

---

## Adaptive Position Sizing

**Type:** Portfolio Management  
**Status:** Backlog

Evaluate whether position size should adapt based on:

- Trade quality
- Execution quality
- Market regime
- Volatility
- Portfolio concentration
- Correlation
- Historical strategy performance

Requires sufficient historical evidence before implementation.

---

## Portfolio Optimization

**Type:** Portfolio Management  
**Status:** Backlog

Move beyond independent ranking toward portfolio-level optimization.

Potential inputs:

- Expected return
- Risk
- Correlation
- Sector concentration
- Industry concentration
- Execution quality
- Market regime
- Capital efficiency

---

## Historical Execution Analysis

**Type:** Learning / Execution  
**Status:** Backlog

Determine how execution characteristics affect realized performance.

Potential variables:

- Spread percentage
- Immediate liquidation cost
- Execution grade
- Volume
- Open interest
- Entry friction
- Contract liquidity

---

## Strategy Attribution

**Type:** Learning  
**Status:** Backlog

Track performance independently by strategy.

Examples:

- Long Call
- Long Put
- Future spread strategies
- Future volatility strategies

Strategy expansion should not occur without the ability to measure attribution.

---

## Strategy Optimizer

**Type:** Research / Strategy  
**Status:** Backlog

Expand beyond simple directional calls and puts only when historical evidence and investment philosophy justify additional complexity.

The Strategy Optimizer should determine the best expression of a thesis rather than introduce complexity for its own sake.

---

# P3 — Future / Experimental

Ideas worth preserving but not currently justified for implementation.

## Advanced Volatility Strategies

Evaluate volatility-driven strategies once sufficient IV and Greeks history exists.

---

## Multi-Leg Optimization

Evaluate debit spreads, credit spreads, calendars, diagonals, and other structures only after simpler strategies are understood and validated.

---

## Portfolio Hedging

Evaluate systematic portfolio hedging based on market regime and aggregate exposure.

---

## Dynamic Capital Allocation

Evaluate dynamically changing deployed capital based on:

- Market regime
- Breadth
- Historical strategy performance
- Portfolio risk
- Opportunity quality

---

# Backlog Governance

Backlog items should not automatically become implementation work.

Before promotion into a sprint, an item should answer:

1. What problem are we solving?
2. What evidence suggests the problem exists?
3. How does solving it strengthen the learning loop?
4. What subsystem owns the responsibility?
5. What historical data must be preserved?
6. What are the regression risks?
7. How will success be validated?
8. Does another backlog item need to happen first?

When an item becomes an active sprint:

- Define sprint scope
- Define success criteria
- Define regression tests
- Identify affected historical schemas
- Identify backward-compatibility risks

When completed:

- Remove it from the active backlog
- Record it in Completed Sprints
- Update Current Capabilities where appropriate

---

# Weekly Learning Objectives

Every weekly report should answer:

- What happened?
- Why did it happen?
- What did we learn?
- Which scores best predicted success?
- Did execution help or hurt?
- Which experiment should be prioritized next?
- Did any subsystem regress?

Where sufficient data exists, weekly learning should also examine:

- Allocated recommendations
- Rejected executable recommendations
- Non-executable recommendations
- Watchlist recommendations
- Pass recommendations

This allows Project Stonks to learn from both actual decisions and counterfactual outcomes.

The Learning Engine proposes experiments.

It never automatically changes production behavior.

---

# Engineering Principles

1. Every subsystem owns one responsibility.

2. Learning is prioritized over feature growth.

3. Historical recommendations are immutable.

4. Evidence precedes optimization.

5. Every sprint includes regression validation.

6. Every release should increase confidence.

7. Data required for future learning should be captured before optimization begins.

8. Rejected recommendations are evidence, not discarded output.

9. Complexity must justify itself through measurable improvement.

10. Production behavior never changes automatically because of a learning-system recommendation.

---

# Subsystem Ownership

**Research Engine**  
Finds opportunities.

**Strategy Optimizer**  
Determines how an investment thesis should be expressed.

**Contract Optimizer**  
Chooses contracts.

**Execution Engine**  
Evaluates tradability.

**Trade Scoring Engine**  
Produces Institutional Trade Score.

**Portfolio Allocation Engine**  
Chooses what to own.

**Paper Portfolio**  
Tracks simulated capital deployment and position state.

**Outcome Review**  
Measures what happened after recommendations were generated.

**Learning Engine**  
Uses historical evidence to improve future decisions.

---

# Success Criteria

Project Stonks succeeds when it continuously improves because of evidence generated from its own research, execution quality, portfolio decisions, and historical outcomes.

The objective is not simply to predict stock prices.

The objective is to build an institutional-quality decision engine that becomes more accurate, more disciplined, and more evidence-driven every week.

A larger feature set does not necessarily represent progress.

Progress occurs when the system becomes better at:

- Identifying opportunities
- Rejecting poor opportunities
- Selecting appropriate strategies
- Selecting appropriate contracts
- Understanding execution
- Allocating capital
- Managing portfolio risk
- Learning from outcomes

---

# Working Style

When contributing to Project Stonks:

- Read `PROJECT_STATUS.md` before proposing changes.
- Review the Development Backlog before creating a new sprint.
- Prefer architectural improvements over isolated feature additions.
- Preserve backwards compatibility whenever practical.
- Minimize technical debt.
- Prefer evidence over intuition.
- Full-file replacements are preferred over partial patches unless only a few lines change.
- Every new subsystem should have a single, well-defined responsibility.
- Every sprint should identify regression risks and define how success will be validated.
- When appropriate, propose future extensibility even if it is not implemented immediately.
- Do not change production scoring merely because a new data field becomes available.
- Preserve data today that may become valuable for hindsight tomorrow.
- Do not optimize a subsystem until sufficient evidence exists to determine whether the optimization improves outcomes.
