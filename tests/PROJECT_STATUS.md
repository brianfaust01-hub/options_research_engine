# Project Stonks

## Vision

Project Stonks is an adaptive investment operating system designed to generate long-term, risk-adjusted alpha versus the S&P 500 through disciplined portfolio management, evidence-based decision making, and continuous learning.

The objective is not to predict markets.

The objective is to build a system that continually improves its capital allocation decisions through measurement, experimentation, and feedback.

---

# Current Status

Version:
v0.2.0

Development Stage:
Paper Trading MVP

Current Sprint:
Sprint 25 Complete

Overall Progress:
~65% of Version 1 MVP

---

# North Star

Maximize long-term alpha versus SPY while controlling downside risk.

Every feature must improve one of:

- Expected return
- Risk management
- Decision quality
- Capital allocation
- Learning capability

---

# Core Principles

1. Evidence beats intuition.
2. Markets have regimes.
3. Breadth matters.
4. Capital is limited.
5. Cash is a position.
6. Portfolio quality matters more than trade quantity.
7. Every recommendation should be measurable.
8. The system should improve itself over time.

---

# Current Architecture

Historical Data
↓

Indicator Engine
↓

Research Engine

- Trend
- Momentum
- Market Regime

↓

Opportunity Engine

↓

Option Selection

↓

Position Sizing

↓

Trade Construction

↓

Trade Quality Scoring

↓

Portfolio Allocation

↓

Portfolio Exposure Analysis

↓

Trade Journal

↓

Outcome Review

↓

Learning Engine (future)

---

# Major Features Complete

### Market Analysis

✓ Historical price ingestion

✓ Technical indicators

✓ Trend scoring

✓ Momentum scoring

✓ Market regime analysis

✓ Market breadth analysis

---

### Trade Selection

✓ Opportunity engine

✓ Long calls

✓ Long puts framework

✓ Options chain retrieval

✓ Contract scoring

✓ Greeks evaluation

✓ Position sizing

✓ Trade construction

✓ Profit target generation

✓ Stop loss generation

✓ Time stop generation

---

### Portfolio Management

✓ Portfolio allocation ranking

✓ Allocation score

✓ Trade quality grading

✓ Sector classification

✓ Industry classification

✓ Theme classification

✓ Portfolio exposure diagnostics

---

### Learning Infrastructure

✓ Trade journal

✓ Version tracking

✓ Recommendation IDs

✓ Outcome review framework

✓ Paper trade tracking

---

# Current Folder Structure

src/

- weekly_scan.py
- config.py
- data_loader.py
- indicators.py
- research_engine.py
- opportunity_engine.py
- option_selector.py
- options_engine.py
- option_pricing.py
- greeks.py
- trade_constructor.py
- position_sizing.py
- trade_quality.py
- portfolio_allocator.py
- portfolio_exposure.py
- market_context.py
- market_breadth.py
- outcome_review.py
- trade_journal.py

strategies/

models/

data/

---

# Development Workflow

Development Mode

- TEST_MODE=True
- 12 representative stocks
- Fast iteration

Validation Mode

- Full S&P 500

Git

- Complete file replacement
- Commit after every successful sprint

---

# Remaining Major Milestones

## Phase 1 (Current)

Paper Trading MVP

Remaining work:

- Dynamic exits
- Portfolio exposure limits
- Better bearish regime support

---

## Phase 2

Adaptive Learning

- Measure recommendation performance
- Compare against SPY
- Measure alpha
- Learn from historical trades
- Recommend configuration changes

---

## Phase 3

Portfolio Intelligence

- Correlation analysis
- Exposure limits
- Cash optimization
- Multi-position management
- Capital rotation

---

## Phase 4

Configuration Evolution

The system begins improving itself.

Instead of hard-coded settings like:

RSI > 60

the engine will eventually learn:

"RSI 56-62 has historically produced 14% higher alpha."

Configuration becomes evidence-driven.

---

## Phase 5

Production

- Dashboard
- Daily reports
- Notifications
- Multiple portfolios
- Broker integration

---

# Current Technical Debt

High

- Dynamic exit engine
- Full bearish strategy implementation
- Outcome review automation
- Learning engine

Medium

- Portfolio correlation
- Exposure limits
- Adaptive configs
- Portfolio analytics

Low

- UI
- Broker APIs
- Mobile dashboard

---

# Long-Term Vision

Every morning Project Stonks should answer:

1. What should I buy?
2. What should I sell?
3. What should I continue holding?
4. Where should new capital be allocated?
5. How diversified is my portfolio?
6. How did yesterday's decisions perform?
7. Am I outperforming SPY?
8. What has the system learned?
9. Should my strategy change?

Project Stonks is evolving into an adaptive investment operating system that continuously improves through evidence rather than assumptions.