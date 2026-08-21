# PROJECT STATUS — Project Stonks

**Version:** v0.3.0-alpha  
**Current Milestone:** Institutional Research Platform  
**Current Sprint:** Sprint 34A – Hindsight Data Integrity & Provenance  
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

---

# Active Sprint

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
**Status:** Active — Sprint 34A

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
**Status:** Backlog

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
**Status:** Backlog

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
**Status:** Backlog

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
**Status:** Backlog

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
