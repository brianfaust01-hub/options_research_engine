# Project Stonks

## Vision

Project Stonks is an adaptive investment operating system designed to generate long-term, risk-adjusted alpha versus the S&P 500 through evidence-based capital allocation.

The goal is **not** to predict markets.

The goal is to build a repeatable decision-making system that continuously improves through measurement, testing, and learning.

---

# Current Status

Current Version:
v0.2.0

Development Stage:
Active Development

Current Milestone:
Paper Trading MVP

---

# North Star

Maximize long-term alpha versus SPY while maintaining disciplined risk management.

The system should optimize:

- Capital allocation
- Risk-adjusted returns
- Decision quality
- Continuous learning

NOT:

- Trade frequency
- Prediction accuracy
- Number of indicators
- Complexity for its own sake

---

# Core Design Principles

1. Evidence beats intuition.
2. Every feature must improve expected returns or reduce risk.
3. Optimize portfolios, not individual trades.
4. Cash is a valid investment decision.
5. Let winners run while protecting capital.
6. Continuously re-underwrite every open position.
7. Measure everything.
8. Alpha versus SPY is the primary performance metric.

---

# Architecture

Current modules:

Data Loader
↓

Indicator Engine
↓

Research Engine
↓

Opportunity Engine
↓

Option Selection Engine
↓

Trade Constructor
↓

Trade Journal
↓

Learning Engine (future)

---

# Current Folder Structure

src/

- config.py
- weekly_scan.py
- data_loader.py
- indicators.py
- research_engine.py
- opportunity_engine.py
- option_selector.py
- options_engine.py
- option_pricing.py
- greeks.py
- trade_constructor.py
- trade_journal.py
- strategies/
- models/

data/

- raw/
- processed/
- trade_journal.csv

---

# Development Workflow

Development Mode

- TEST_MODE = True
- 12 representative stocks
- Fast iteration

Validation Mode

- TEST_MODE = False
- Full S&P 500
- End-to-end validation

Entire files are replaced rather than editing individual lines.

Git commits are made after successful milestones.

---

# Completed Features

✓ Historical data ingestion

✓ Indicator calculations

✓ Modular research engine

✓ Opportunity engine

✓ Options chain retrieval

✓ Contract scoring

✓ Greeks calculations

✓ Trade construction

✓ Trade journal

✓ Versioned journal entries

✓ Development mode

✓ Virtual environment

---

# Investment Philosophy

Project Stonks is not attempting to identify "the next stock."

Instead it seeks to determine:

Given today's information...

Where should the next dollar of capital be allocated?

The system will eventually support multiple portfolios.

Core Portfolio
- Stable compounding

Opportunity Portfolio
- Higher-conviction opportunities

Experimental Portfolio
- Strategy research

---

# Future Architecture

Recommendation Engine

↓

Portfolio Allocation Engine

↓

Dynamic Position Management

↓

Learning Engine

↓

Configuration Optimization

↓

Portfolio Analytics

↓

Mobile Dashboard

---

# Roadmap

## Phase 1
Infrastructure

Status:
Nearly Complete

Includes:

- Research engine
- Opportunity engine
- Option engine
- Journaling

---

## Phase 2
Paper Trading

Goals:

- Record recommendations
- Track entries/exits
- Compare against SPY
- Measure alpha

---

## Phase 3
Learning Engine

Goals:

- Evaluate historical recommendations
- Compare configuration versions
- Promote successful strategies
- Retire unsuccessful strategies

---

## Phase 4
Portfolio Engine

Goals:

- Dynamic capital allocation
- Position sizing
- Cash management
- Multiple portfolios

---

## Phase 5
User Experience

Goals:

- Daily report
- Dashboard
- Mobile-friendly interface
- Notifications

---

# Current Technical Debt

High Priority

- Opportunity engine directional logic
- Dynamic exit engine
- Trade outcome tracking
- requirements.txt
- README.md

Medium Priority

- Portfolio analytics
- Position sizing
- Configuration optimization

Low Priority

- UI
- Notifications
- Broker integration

---

# Current Sprint

Sprint 15

Objective

Correct directional opportunity scoring.

Bullish research should never produce bearish recommendations unless bearish evidence genuinely dominates.

---

# Long-Term Vision

Every morning Project Stonks should answer:

1. What should I buy?
2. What should I sell?
3. What should I continue holding?
4. How should capital be allocated?
5. How did yesterday's decisions perform?
6. What has the system learned?
7. Am I outperforming SPY?

The system should become an adaptive investment operating system that improves continuously through evidence rather than assumptions.