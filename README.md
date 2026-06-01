# Aurix AI Service

Python FastAPI microservice providing the full AI intelligence layer for the Aurix/HOPn fintech platform covering fraud detection, portfolio optimization, credit scoring, market forecasting, vault management, regulatory compliance, and API orchestration.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Aurix Platform                                   │
│                                                                         │
│   Frontend (React / Flutter / Mobile)                                   │
│              ↓                                                          │
│   Node.js Backend (Auth, Business Logic, Routing)                       │
│              ↓  HTTP/REST                                               │
│   ┌──────────────────────────────────────────────────────────────┐      │
│   │               Aurix AI Service  (FastAPI · Port 8001)        │      │
│   │                                                              │      │
│   │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │      │
│   │  │  Module 1      │  │  Module 2      │  │  Module 3     │  │      │
│   │  │  Core AI /     │  │  Risk &        │  │  Investment & │  │      │
│   │  │  Fraud Engine  │  │  Compliance    │  │  Market AI    │  │      │
│   │  └────────────────┘  └────────────────┘  └───────────────┘  │      │
│   │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │      │
│   │  │  Module 4      │  │  Module 5      │  │  Module 6     │  │      │
│   │  │  Lending &     │  │  Vault &       │  │  Personali-   │  │      │
│   │  │  Credit AI     │  │  Supply Chain  │  │  zation AI    │  │      │
│   │  └────────────────┘  └────────────────┘  └───────────────┘  │      │
│   │  ┌────────────────┐                                          │      │
│   │  │  Module 7      │                                          │      │
│   │  │  Orchestration │                                          │      │
│   │  │  AI            │                                          │      │
│   │  └────────────────┘                                          │      │
│   └──────────────────────────────────────────────────────────────┘      │
│              ↓                                                          │
│   PostgreSQL (fraud_logs, portfolio_logs)                               │
└─────────────────────────────────────────────────────────────────────────┘
```
## Current Fraud Architecture Summary

The current Aurix fraud service supports a stable MVP fraud-scoring flow with rule-based fraud checks, configurable thresholds, velocity monitoring, and persistent fraud logging. The codebase also includes future-ready XGBoost support with optional shadow mode to prepare for later supervised fraud model rollout.
---

## Project Structure

```
ai-service/
├── main.py                              # App entry point — all routers, middleware, lifespan
├── requirements.txt
├── .env.example
│
└── app/
    ├── api/
    │   └── v1/
    │       ├── health.py                # GET  /v1/health
    │       ├── fraud.py                 # POST /v1/fraud-score
    │       ├── portfolio.py             # POST /v1/recommend-portfolio
    │       └── ai/
    │           ├── risk.py              # POST /v1/ai/analyze-risk
    │           │                        # POST /v1/ai/compliance-report
    │           ├── investment.py        # POST /v1/ai/optimize-portfolio
    │           │                        # POST /v1/ai/rebalance-portfolio
    │           │                        # POST /v1/ai/score-project
    │           ├── credit.py            # POST /v1/ai/credit-score
    │           │                        # POST /v1/ai/snbl-check
    │           ├── personalization.py   # POST /v1/ai/user-insights
    │           │                        # POST /v1/ai/goal-optimize
    │           ├── forecast.py          # POST /v1/ai/forecast-price
    │           │                        # POST /v1/ai/forecast-price/batch
    │           ├── vault.py             # POST /v1/ai/vault-forecast
    │           │                        # POST /v1/ai/redemption-forecast
    │           │                        # POST /v1/ai/supply-chain-check
    │           └── orchestration.py     # POST /v1/ai/route-broker
    │                                    # POST /v1/ai/optimize-fees
    │                                    # POST /v1/ai/sync-portfolio
    │
    ├── services/
    │   ├── velocity_tracker.py          # Thread-safe sliding-window velocity tracker
    │   └── ai_modules/
    │       ├── core_ai/
    │       │   ├── service.py           # Multi-signal fraud scorer + ML ensemble
    │       │   └── ml_scorer.py         # IsolationForest (200 trees, 10-feature vector)
            |   |__ xgb_scorer.py        # XGBoost fraud scoring module 
    │       ├── risk_ai/
    │       │   └── service.py           # Anomaly detection, AML, compliance reports
    │       ├── investment_ai/
    │       │   └── service.py           # Portfolio optimization, rebalancing, crowdfunding
    │       ├── credit_ai/
    │       │   └── service.py           # Credit scoring, loan eligibility, SNBL
    │       ├── personalization_ai/
    │       │   └── service.py           # Spending analysis, insights, goal optimization
    │       ├── market_ai/
    │       │   └── service.py           # GBM Monte Carlo price forecasting
    │       ├── vault_ai/
    │       │   └── service.py           # Inventory forecast, redemption demand, supply chain
    │       └── orchestration_ai/
    │           └── service.py           # Broker routing, fee optimization, portfolio sync
    │
    ├── core/
    │   ├── config.py                    # Pydantic BaseSettings (DATABASE_URL, ML flags, etc.)
    │   └── logging.py                   # Structured stdout logging
    ├── db/
    │   └── database.py                  # SQLAlchemy engine + session factory
    ├── models/
    │   └── logs.py                      # FraudLog, PortfolioLog ORM tables
    └── schemas/
        └── schemas.py                   # All Pydantic request/response schemas
```

---

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Required: DATABASE_URL=postgresql://user:pass@host:5432/dbname
# Optional: USE_ML_MODEL=true  (enables IsolationForest fraud scoring)

```env
USE_XGBOOST_MODEL=False
USE_XGBOOST_SHADOW=False
MEDIUM_RISK_AMOUNT=5000.0
HIGH_RISK_AMOUNT=20000.0

# 4. Run the service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Swagger UI: http://127.0.0.1:8001/docs  
ReDoc: http://127.0.0.1:8001/redoc

---

## API Reference

### Core Endpoints

| Method | URL | Module | Description |
|--------|-----|--------|-------------|
| GET | `/v1/health` | — | Health check |
| POST | `/v1/fraud-score` | Core AI | Real-time transaction fraud scoring |
| POST | `/v1/recommend-portfolio` | Investment AI | Rule-based portfolio recommendation |

### Module 1 · Core AI / Fraud Engine
The current fraud engine combines MVP fraud controls with future-ready ML support.

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/fraud-score` | Multi-signal fraud score + APPROVE/REVIEW/BLOCK decision |

**Signals evaluated:** amount risk, currency risk, location risk (OFAC/FATF), device fingerprint, velocity (1h/24h sliding window)  
**ML mode** (`USE_ML_MODEL=true`): IsolationForest ensemble (60% ML + 40% rule signals), 10-feature vector, 200 trees, trained on 5,000 synthetic transactions at startup.

### Active MVP fraud controls
- Transaction threshold rules
- Velocity-based fraud rules
- Device and location risk checks
- Fraud risk scoring
- Anomaly logging
- Explainable fraud reasons
- PostgreSQL-backed fraud logging

### Implemented fraud rules
- Medium-risk transfer threshold: `5,000`
- High-risk transfer threshold: `20,000`
- `5` transfers in `1 minute`
- `6` transactions in `1 hour`
- Repeated large transfers in short time windows
- Device/session anonymity checks
- High-risk and medium-risk jurisdiction checks

### ML support
- Isolation Forest is available as the current fraud ML scoring path when ML is enabled.
- XGBoost is integrated as a future-ready supervised fraud scorer.
- XGBoost shadow mode can run in parallel for evaluation without affecting the live fraud decision.

## Fraud Decision Bands
The current fraud decision mapping is:

- `0–30` → `APPROVE`
- `31–80` → `REVIEW`
- `>80` → `BLOCK`
These bands support the MVP fraud workflow while preserving a stable API response contract.


### Example Fraud Response

```json
{
  "risk_score": 64.5,
  "decision": "REVIEW",
  "reasons": [
    "Medium-risk transfer: 9500.00 EUR exceeds the medium-risk threshold (5000.00).",
    "Transaction originates from high-risk jurisdiction: IR.",
    "No device ID — transaction is from an anonymous session."
  ]
}

---

### Module 2 · Risk, Compliance & Security AI

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/analyze-risk` | Anomaly detection + AML pattern check (single transaction) |
| POST | `/v1/ai/compliance-report` | Batch compliance screening → regulatory report |

**`analyze-risk` signals:** amount spike, rapid burst, high-risk jurisdiction, off-hours activity, structuring pattern (9k–10k band), round-amount, multi-currency layering.

**`compliance-report`** accepts a batch of transactions, runs each through the full risk engine, and returns:
- flagged count, HIGH/MEDIUM breakdown
- per-transaction `ESCALATE_TO_COMPLIANCE` / `MANUAL_REVIEW` actions
- per-user flag summary
- top risk patterns ranked by frequency
- deterministic SHA-256 report fingerprint for audit traceability

---

### Module 3 · Investment & Market Intelligence AI

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/optimize-portfolio` | Multi-asset portfolio optimization with insights |
| POST | `/v1/ai/rebalance-portfolio` | Drift-based smart rebalancing plan with BUY/SELL instructions |
| POST | `/v1/ai/score-project` | Crowdfunding / startup project scoring (grade A–F + ROI estimate) |
| POST | `/v1/ai/forecast-price` | GBM Monte Carlo price forecast for a single asset |
| POST | `/v1/ai/forecast-price/batch` | Batch price forecast for multiple assets |

**Supported assets for forecasting:** `gold`, `silver`, `btc`, `eth`, `spy`, `xau`  
**Forecast method:** 500-path Geometric Brownian Motion simulation, per-asset calibrated drift/volatility, returns median + P10/P90 confidence bands.

**Crowdfunding scoring signals:** team experience (25 pts), market size TAM (20 pts), MRR + growth traction (20 pts), runway/burn efficiency (20 pts), competitive/regulatory risk (15 pts).

---

### Module 4 · Lending & Credit AI 

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/credit-score` | Alternative credit score (0–100, grade A–E) + loan eligibility |
| POST | `/v1/ai/snbl-check` | Save Now, Buy Later — affordability check + instalment schedule |

**Credit signals:** savings rate (30 pts), gold holdings collateral (25 pts), repayment history (25 pts), account tenure (20 pts).  
**Loan eligibility:** LTV capped at 75% of gold value. Risk-based rates: A=4.5%, B=6.5%, C=9.0%.

**SNBL engine:**
- DTI rule: monthly instalment must be ≤ 40% of disposable income
- Gold collateral waiver: fee waived if gold ≥ 50% of item price
- Sliding platform fee: 1–3% (shorter terms cost more)
- Returns full month-by-month instalment schedule

---

### Module 5 · Vault & Supply Chain Intelligence

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/vault-forecast` | Inventory depletion forecast with reorder alerts |
| POST | `/v1/ai/redemption-forecast` | Physical gold/silver redemption demand prediction |
| POST | `/v1/ai/supply-chain-check` | Shipment anomaly detection (weight mismatch, carrier, origin) |

**Vault forecast:** rolling mean + seasonality multiplier → HEALTHY / WARNING / CRITICAL status, auto-calculates reorder quantity (2× projected demand).  
**Redemption forecast:** exponential smoothing (α=0.3) + price-trend adjustment (bearish → +15% demand).  
**Supply chain signals:** weight mismatch (>2% tolerance), high-risk origin country, unknown carrier, suspiciously round weight, value concentration (>20% of vault).

---

### Module 6 · Personalization & User AI

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/user-insights` | Personalised financial insights + spending behaviour analysis |
| POST | `/v1/ai/goal-optimize` | Financial goal optimization with compound interest solver |

**User insights signals:** savings rate, investment allocation %, gold holdings, top spending category, transaction history categorisation (food/travel/investment/savings/utilities/shopping).

**Goal optimization:** compound interest annuity solver → required monthly savings, achievability flag, risk-profile–based projected months, shortfall/surplus, actionable tips.

---

### Module 7 · API Orchestration AI

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/route-broker` | Smart broker routing — best execution across Revolut/Binance/eToro/DriveWealth |
| POST | `/v1/ai/optimize-fees` | Fee comparison across brokers — compute savings on planned trades |
| POST | `/v1/ai/sync-portfolio` | Cross-platform portfolio sync + concentration/overlap analysis |

**Broker scoring dimensions:** fee (30%), latency (25%), liquidity (25%), asset support (20%). Priority modes: `cost` / `speed` / `liquidity`.  
**Portfolio sync:** Herfindahl–Hirschman Index diversification score, per-broker exposure breakdown, cross-broker asset overlap detection.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `USE_ML_MODEL` | ❌ | `false` | Enable the current ML fraud-scoring path |
| `USE_XGBOOST_MODEL` | ❌ | `false` | Reserved for future active XGBoost fraud scoring |
| `USE_XGBOOST_SHADOW` | ❌ | `false` | Run XGBoost in shadow mode without affecting live fraud decisions |
| `SCORING_TIMEOUT` | ❌ | `2.0` | Per-request fraud scoring timeout in seconds |
| `HIGH_RISK_AMOUNT` | ❌ | `20000.0` | High-risk transfer threshold |
| `MEDIUM_RISK_AMOUNT` | ❌ | `5000.0` | Medium-risk transfer threshold |
| `ALLOWED_ORIGINS` | ❌ | local defaults | CORS allowed origins |
| `ALLOW_CREDENTIALS` | ❌ | `false` | CORS allow credentials |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.128.1 + Uvicorn 0.40.0 |
| Validation | Pydantic v2 + pydantic-settings |
| Database | PostgreSQL + SQLAlchemy 2.0 |
| ML | Anomaly Detection | scikit-learn 1.8.0 (IsolationForest) |
| Future Supervised ML | XGBoost |
| Numerics | NumPy 2.4.2 |
| Async | asyncio (all endpoints non-blocking via `asyncio.to_thread`) |
| Logging | Python stdlib logging — structured stdout |

---

XGBoost is currently integrated as a future-ready supervised fraud scorer and can be evaluated in shadow mode without affecting live fraud decisions.

## Complete Endpoint List (20 endpoints)

```
GET  /v1/health
POST /v1/fraud-score
POST /v1/recommend-portfolio
POST /v1/ai/analyze-risk
POST /v1/ai/compliance-report
POST /v1/ai/optimize-portfolio
POST /v1/ai/rebalance-portfolio
POST /v1/ai/score-project
POST /v1/ai/forecast-price
POST /v1/ai/forecast-price/batch
POST /v1/ai/credit-score
POST /v1/ai/snbl-check
POST /v1/ai/user-insights
POST /v1/ai/goal-optimize
POST /v1/ai/vault-forecast
POST /v1/ai/redemption-forecast
POST /v1/ai/supply-chain-check
POST /v1/ai/route-broker
POST /v1/ai/optimize-fees
POST /v1/ai/sync-portfolio
```

---

## Module Implementation Status

| # | Module | Status | Endpoints |
|---|--------|--------|-----------|
| 1 | Core AI Engine (Fraud) | ✅ Complete | 2 |
| 2 | Risk, Compliance & Security AI | ✅ Complete | 2 |
| 3 | Investment & Market Intelligence AI | ✅ Complete | 5 |
| 4 | Lending & Credit AI | ✅ Complete | 2 |
| 5 | Vault & Supply Chain Intelligence | ✅ Complete | 3 |
| 6 | Personalization & User AI | ✅ Complete | 2 |
| 7 | API Orchestration AI | ✅ Complete | 3 |



## Fraud Module Status

### Current state
- Rule-based fraud scoring is implemented for MVP fraud control.
- Fraud risk scores, decisions, and reasons are persisted to PostgreSQL.
- Threshold-based fraud rules are active.
- Short-window velocity monitoring is implemented, including:
  - 1-minute burst detection
  - 1-hour velocity detection
  - repeated large transfer detection
- Isolation Forest support exists in the fraud service.
- XGBoost has been integrated as a future-ready supervised fraud scorer.
- XGBoost shadow mode is available for parallel evaluation.

### Current MVP behavior
- The fraud service returns `risk_score`, `decision`, and `reasons`.
- Live fraud decisions remain stable and auditable.
- Future supervised ML can be activated in a controlled way through environment-based settings.

### Future direction
- Expand supervised fraud evaluation using XGBoost.
- Persist future shadow-model outputs if required.
- Add richer fraud training signals from transaction history, review outcomes, and device/session activity.


