# Aurix AI Service

Python FastAPI microservice providing the full AI intelligence layer for the Aurix/HOPn fintech platform covering fraud detection, portfolio optimization, credit scoring, market forecasting, vault management, regulatory compliance, API orchestration, and user-level risk scoring with recommendations.

---

## Architecture Overview

```text
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
│   PostgreSQL (fraud_logs, portfolio_logs, user_risk_logs)              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Current Summary

The Aurix AI backend now includes:
- fraud detection and fraud-scoring support,
- transaction anomaly and AML/compliance checks,
- and a fully integrated user-level risk score and recommendation engine built on a pre-trained Random Forest model with payload-based inference, logging, and database persistence.

## Current Fraud Architecture Summary

The current Aurix fraud service supports a stable MVP fraud-scoring flow with rule-based fraud checks, configurable thresholds, velocity monitoring, and persistent fraud logging. The codebase also includes future-ready XGBoost support with optional shadow mode to prepare for later supervised fraud model rollout.

---

## Project Structure

```text
ai-service/
├── main.py                              # App entry point — all routers, middleware, lifespan
├── requirements.txt
├── .env.example
├── data/
│   └── risk_engine/
│       ├── risk_model.joblib            # Pre-trained Random Forest model for user risk scoring
│       └── metrics.json                 # Model metrics + feature order metadata
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
    │           │                        # POST /v1/ai/user-risk-score
    │           │                        # POST /v1/ai/user-recommendations
    │           │                        # POST /v1/ai/user-risk-assessment
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
    │       │   ├── ml_scorer.py         # Isolation Forest fraud scoring module
    │       │   └── xgb_scorer.py        # XGBoost fraud scoring module
    │       ├── risk_ai/
    │       │   ├── service.py           # Anomaly detection, AML, compliance reports
    │       │   └── recommendation_engine.py   # User risk score + recommendation engine
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
    │   └── logs.py                      # FraudLog, PortfolioLog, UserRiskLog ORM tables
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
# Required:
# DATABASE_URL=postgresql://user:pass@host:5432/dbname
#
# Optional fraud-scoring flags:
# USE_ML_MODEL=true
# USE_XGBOOST_MODEL=false
# USE_XGBOOST_SHADOW=false
# MEDIUM_RISK_AMOUNT=5000.0
# HIGH_RISK_AMOUNT=20000.0

# 4. Run the service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Recommended fraud-scoring environment values

```env
USE_ML_MODEL=False
USE_XGBOOST_MODEL=False
USE_XGBOOST_SHADOW=False
MEDIUM_RISK_AMOUNT=5000.0
HIGH_RISK_AMOUNT=20000.0
```

### Fraud model flags
- `USE_ML_MODEL` — enables the current ML fraud-scoring path.
- `USE_XGBOOST_MODEL` — reserved for future active XGBoost fraud scoring.
- `USE_XGBOOST_SHADOW` — runs the XGBoost fraud scorer in shadow mode for evaluation only, without affecting live fraud decisions.

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

---

### Module 1 · Core AI / Fraud Engine

The current fraud engine combines MVP fraud controls with future-ready ML support.

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/fraud-score` | Multi-signal fraud score + APPROVE/REVIEW/BLOCK decision |

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

### Fraud Decision Bands
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
```

---

### Module 2 · Risk, Compliance & Security AI

The Risk AI module now supports two categories of functionality:

#### 1. Transaction-level risk and compliance
- anomaly detection
- AML pattern checks
- compliance reporting

#### 2. User-level risk score and recommendation engine
- payload-based user risk scoring
- explanation generation
- recommendation generation
- combined user risk assessment response

This keeps transaction anomaly/compliance logic separate from user-level behavioral risk scoring while allowing both capabilities to live inside the same `risk_ai` module.

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/v1/ai/analyze-risk` | Anomaly detection + AML pattern check (single transaction) |
| POST | `/v1/ai/compliance-report` | Batch compliance screening → regulatory report |
| POST | `/v1/ai/user-risk-score` | Predict user-level risk from behavioral features |
| POST | `/v1/ai/user-recommendations` | Generate recommendations based on user features and predicted risk |
| POST | `/v1/ai/user-risk-assessment` | Return both user risk score and recommendations in one response |

### Transaction risk and compliance behavior
**`analyze-risk` signals:** amount spike, rapid burst, high-risk jurisdiction, off-hours activity, structuring pattern (9k–10k band), round-amount, multi-currency layering.

**`compliance-report`** accepts a batch of transactions, runs each through the full risk engine, and returns:
- flagged count, HIGH/MEDIUM breakdown
- per-transaction `ESCALATE_TO_COMPLIANCE` / `MANUAL_REVIEW` actions
- per-user flag summary
- top risk patterns ranked by frequency
- deterministic SHA-256 report fingerprint for audit traceability

### User Risk Engine Design
The user risk score and recommendation engine uses a payload-based inference design.

Instead of performing runtime CSV lookups, the backend receives user-level behavioral features directly in the request body. This makes the service more suitable for real backend integration, because the main application can prepare the user feature payload and send it to the AI service for scoring.

This design supports:
- cleaner service-oriented integration,
- no runtime dependency on a local demo dataset,
- model inference using a pre-trained Random Forest classifier,
- explanation and recommendation generation directly from the provided payload.

### User Risk Model Artifacts
The user risk score engine uses a pre-trained Random Forest model and metrics metadata stored in the backend repo:

```text
data/risk_engine/risk_model.joblib
data/risk_engine/metrics.json
```

These artifacts are loaded by the dedicated service module:

```text
app/services/ai_modules/risk_ai/recommendation_engine.py
```

The model is loaded once and cached for reuse during API requests.

### User Risk Threshold Alignment
The user risk engine includes a business-rule threshold override to align with current Aurix risk expectations:

- transfer amount `>= 5000` → at least **Medium risk**
- transfer amount `>= 20000` → **High risk**

This threshold override is applied after the model prediction so that the final output remains both:
- model-informed,
- and compliant with Aurix business risk rules.

### Logging and Persistence
The user risk score and recommendation endpoints include:
- request-level logging,
- service-level prediction logging,
- recommendation generation logging,
- database persistence for stored user risk assessment results.

User risk assessment results are persisted in PostgreSQL through a dedicated log model, supporting:
- auditability,
- historical review,
- future analysis,
- operational traceability.

### Example User Risk Assessment

#### Sample request

```json
{
  "user_id": "u123",
  "buy_count": 12,
  "sell_count": 3,
  "total_transactions": 15,
  "avg_transaction_amount": 1200.0,
  "max_transaction_amount": 6000.0,
  "transaction_frequency_weekly": 8.0,
  "activity_days_per_month": 18,
  "avg_days_between_transactions": 2.5,
  "account_balance": 15000.0,
  "buy_sell_ratio": 4.0,
  "sudden_behavior_change": 1,
  "recent_large_transaction": 1,
  "failed_login_attempts": 2,
  "kyc_review_flag": 0
}
```

#### Sample response

```json
{
  "status": "success",
  "data": {
    "risk_score": {
      "user_id": "u123",
      "risk_level": "High risk",
      "confidence": 0.5008,
      "explanation": "Above-normal transaction frequency; Moderately large transaction size; Transfer amount exceeds the medium-risk threshold (5000); Sudden behavioral change detected; Recent large transaction flag raised.",
      "contributing_factors": [
        "Above-normal transaction frequency",
        "Moderately large transaction size",
        "Transfer amount exceeds the medium-risk threshold (5000)",
        "Sudden behavioral change detected",
        "Recent large transaction flag raised"
      ]
    },
    "recommendation": {
      "user_id": "u123",
      "risk_level": "High risk",
      "suggested_action": "Reduce transaction frequency | Consider smaller purchases | Review recent account activity",
      "recommendation_reason": "Transaction activity is significantly above the normal user baseline | Transfer amount exceeds the medium-risk threshold and may require closer monitoring | A sudden behavior change may indicate risky or abnormal usage"
    }
  },
  "metadata": {
    "request_id": "example-request-id",
    "user_id": "u123",
    "module": "risk_ai"
  }
}
```

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
| Fraud / Anomaly ML | scikit-learn (Isolation Forest) |
| User Risk Model | scikit-learn (Random Forest) |
| Future Supervised Fraud ML | XGBoost |
| Data Handling | pandas |
| Numerics | NumPy |
| Model Artifact Loading | joblib |
| Async | asyncio (all endpoints non-blocking via `asyncio.to_thread`) |
| Logging | Python structured logging |

XGBoost is currently integrated as a future-ready supervised fraud scorer and can be evaluated in shadow mode without affecting live fraud decisions.

---

## Complete Endpoint List (23 endpoints)

```text
GET  /v1/health
POST /v1/fraud-score
POST /v1/recommend-portfolio
POST /v1/ai/analyze-risk
POST /v1/ai/compliance-report
POST /v1/ai/user-risk-score
POST /v1/ai/user-recommendations
POST /v1/ai/user-risk-assessment
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
| 2 | Risk, Compliance & Security AI | ✅ Complete | 5 |
| 3 | Investment & Market Intelligence AI | ✅ Complete | 5 |
| 4 | Lending & Credit AI | ✅ Complete | 2 |
| 5 | Vault & Supply Chain Intelligence | ✅ Complete | 3 |
| 6 | Personalization & User AI | ✅ Complete | 2 |
| 7 | API Orchestration AI | ✅ Complete | 3 |

---

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

---

## Risk AI Module Status

### Current capabilities
- transaction anomaly detection
- AML pattern checking
- compliance reporting
- user-level risk score prediction
- explanation generation
- recommendation generation
- combined user risk assessment endpoint
- request and service-level logging
- PostgreSQL persistence for user risk assessment results

### Current model setup
- Isolation Forest supports fraud/anomaly scoring in the fraud module
- Random Forest supports the user risk score and recommendation engine
- XGBoost is integrated separately as a future-ready fraud scorer with optional shadow mode

### Current integration state
The user risk engine is fully integrated into the AI backend and works end to end through Swagger/API testing.
