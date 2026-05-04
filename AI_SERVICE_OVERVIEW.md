# Aurix AI Service — Overview

> **Last updated:** Phase 2 complete — multi-signal fraud scoring, modular AI service layer.

---

## Folder Structure

```
ai-service/
├── main.py                          # App entry point (FastAPI + middleware)
├── requirements.txt
├── .env / .env.example
├── aurix_ai.db                      # SQLite DB (dev)
│
└── app/
    ├── main.py                      # Legacy simple app (superseded by root main.py)
    ├── config.py / schemas.py       # Legacy files (superseded)
    │
    ├── core/
    │   ├── config.py                # Settings (+ USE_ML_MODEL toggle added Phase 2)
    │   └── logging.py               # Structured stdout logging
    │
    ├── db/
    │   └── database.py              # SQLAlchemy engine + session + Base
    │
    ├── models/
    │   └── logs.py                  # FraudLog, PortfolioLog ORM models
    │
    ├── schemas/
    │   └── schemas.py               # Pydantic request/response models
    │
    ├── services/
    │   ├── fraud.py                 # (legacy — kept, not used by routes)
    │   ├── recommend.py             # (legacy — kept, not used by routes)
    │   │
    │   └── ai_modules/              # ★ NEW — modular AI service layer (Phase 1)
    │       ├── __init__.py
    │       │
    │       ├── core_ai/             # Fraud detection & transaction risk engine
    │       │   ├── __init__.py
    │       │   ├── schemas.py       # Re-exports FraudScoreRequest/Response
    │       │   └── service.py       # ★ Multi-signal scorer (Phase 2)
    │       │
    │       ├── investment_ai/       # Portfolio optimization engine
    │       │   ├── __init__.py
    │       │   ├── schemas.py       # Re-exports PortfolioRequest/Response
    │       │   └── service.py       # compute_recommendation + ML hook
    │       │
    │       ├── risk_ai/             # Anomaly detection & AML (stub — Phase 3)
    │       │   ├── __init__.py
    │       │   ├── schemas.py
    │       │   └── service.py       # detect_anomaly, check_aml_patterns
    │       │
    │       ├── credit_ai/           # Credit scoring & loan eligibility (stub — Phase 3)
    │       │   ├── __init__.py
    │       │   ├── schemas.py
    │       │   └── service.py       # compute_credit_score, assess_loan_eligibility
    │       │
    │       └── personalization_ai/  # User insights & behaviour (stub — Phase 3)
    │           ├── __init__.py
    │           ├── schemas.py
    │           └── service.py       # generate_user_insights, analyze_spending_patterns
    │
    └── api/v1/
        ├── health.py                # GET /v1/health
        ├── fraud.py                 # POST /v1/fraud-score → delegates to core_ai
        └── portfolio.py             # POST /v1/recommend-portfolio → delegates to investment_ai
```

---

## Endpoints

### `GET /v1/health`

**File:** `app/api/v1/health.py`

**Sample Response:**
```json
{
  "status": "ok",
  "service": "Aurix AI Service",
  "env": "dev",
  "version": "1.0.0"
}
```

---

### `POST /v1/fraud-score`

**File:** `app/api/v1/fraud.py` → `app/services/ai_modules/core_ai/service.py`

**Request Body:**
```json
{
  "user_id": "u123",
  "amount": 12000.00,
  "currency": "EUR",
  "device_id": "dev-1",
  "location": "DE",
  "timestamp": "2026-04-20T10:00:00Z"
}
```

#### Multi-Signal Scoring (Phase 2)

Five independent signals are evaluated and aggregated into a single `risk_score`:

| Signal | Function | Max Score | Trigger condition |
|---|---|---|---|
| Amount | `analyze_amount_risk()` | 45 pts | > `HIGH_RISK_AMOUNT` (45 pts) or > `MEDIUM_RISK_AMOUNT` (25 pts) |
| Currency | `analyze_currency_risk()` | 10 pts | Not in `{EUR, USD, GBP, CHF, SGD}` |
| Location | `analyze_location_risk()` | 30 pts | Missing (12 pts) / medium-risk country (15 pts) / high-risk country (30 pts) |
| Device | `analyze_device_risk()` | 10 pts | No `device_id` present |
| Velocity | `analyze_velocity_risk()` | 0 pts | Stub — implemented in Phase 3 |

**Decision thresholds:**

| `risk_score` | `decision` |
|---|---|
| < 50 | `APPROVE` |
| 50 – 79 | `REVIEW` |
| ≥ 80 | `BLOCK` |

**Sample Response — APPROVE** (normal transaction, `DE`, known device):
```json
{
  "risk_score": 0.0,
  "decision": "APPROVE",
  "reasons": ["Amount 150.00 EUR — no risk signals detected across all checks."]
}
```

**Sample Response — REVIEW** (high amount, no device):
```json
{
  "risk_score": 55.0,
  "decision": "REVIEW",
  "reasons": [
    "Amount 12000.00 EUR exceeds high-risk threshold (10000.00).",
    "No device ID — transaction is from an anonymous session."
  ]
}
```

**Sample Response — BLOCK** (high amount + high-risk location + no device):
```json
{
  "risk_score": 85.0,
  "decision": "BLOCK",
  "reasons": [
    "Amount 12000.00 EUR exceeds high-risk threshold (10000.00).",
    "Transaction originates from high-risk jurisdiction: KP.",
    "No device ID — transaction is from an anonymous session."
  ]
}
```

> Every decision is persisted to the `fraud_logs` table. Per-signal scores are emitted to structured logs with `request_id` for full traceability.

---

### `POST /v1/recommend-portfolio`

**File:** `app/api/v1/portfolio.py` → `app/services/ai_modules/investment_ai/service.py`

**Request Body:**
```json
{
  "user_id": "u123",
  "portfolio": { "gold": 50, "stocks": 30, "crypto": 20 },
  "risk_profile": "medium"
}
```

**Risk Profile Targets:**

| Profile      | Gold | Stocks | Crypto |
|--------------|------|--------|--------|
| `low`        | 70%  | 20%    | 10%    |
| `medium`     | 55%  | 30%    | 15%    |
| `high`       | 30%  | 40%    | 30%    |
| `aggressive` | 20%  | 35%    | 45%    |

> The final allocation blends **70% target profile** + **30% current portfolio** to avoid abrupt rebalancing.

**Sample Response** (`medium` profile, current `50/30/20`):
```json
{
  "recommended_allocation": {
    "gold": 53.5,
    "stocks": 30.0,
    "crypto": 16.5
  },
  "notes": [
    "Medium risk profile → balanced allocation across assets.",
    "Recommendation blends target profile weights (70%) with current allocation (30%)."
  ]
}
```

> Every recommendation is persisted to the `portfolio_logs` table.

---

## Key Infrastructure

| Component   | Detail                                                                       |
|-------------|------------------------------------------------------------------------------|
| Framework   | FastAPI 1.0.0                                                                |
| Database    | SQLAlchemy + SQLite (dev) / any DB via `DATABASE_URL` env var                |
| Middleware  | UUID `request_id` injection, global 2s timeout, structured logging           |
| Validation  | Pydantic v2 with field validators                                            |
| Thresholds  | `HIGH_RISK_AMOUNT=10000`, `MEDIUM_RISK_AMOUNT=5000` (env-configurable)       |
| ML Toggle   | `USE_ML_MODEL=false` — set `true` in `.env` to route scoring to ML hook      |
| API Docs    | Swagger UI at `/docs`, ReDoc at `/redoc`                                     |

---

## ML Integration Points

| Module | Hook Function | Status |
|---|---|---|
| `core_ai` | `compute_fraud_score_ml()` | Stub — falls back to rule-based |
| `investment_ai` | `compute_recommendation_ml()` | Stub — falls back to rule-based |
| `risk_ai` | `detect_anomaly()`, `check_aml_patterns()` | Phase 3 |
| `credit_ai` | `compute_credit_score()`, `assess_loan_eligibility()` | Phase 3 |
| `personalization_ai` | `generate_user_insights()`, `analyze_spending_patterns()` | Phase 3 |

Set `USE_ML_MODEL=true` in `.env` to activate ML routing in `core_ai`. All other modules activate automatically when their stubs are replaced with model inference.

---

## DB Tables

### `fraud_logs`
| Column       | Type        | Notes                          |
|--------------|-------------|--------------------------------|
| `id`         | Integer PK  |                                |
| `request_id` | String      | UUID from middleware           |
| `user_id`    | String      |                                |
| `amount`     | Float       |                                |
| `currency`   | String(10)  |                                |
| `device_id`  | String      | Optional                       |
| `location`   | String(10)  | 2-letter ISO country code      |
| `risk_score` | Float       | Aggregated multi-signal score  |
| `decision`   | String(20)  | `APPROVE` / `REVIEW` / `BLOCK` |
| `reasons`    | JSON        | List of active signal reasons  |
| `timestamp`  | DateTime    | From request payload           |
| `logged_at`  | DateTime    | Server-side insert time        |

### `portfolio_logs`
| Column                   | Type       | Notes                    |
|--------------------------|------------|--------------------------|
| `id`                     | Integer PK |                          |
| `user_id`                | String     |                          |
| `input_portfolio`        | JSON       | Raw user portfolio       |
| `risk_profile`           | String(20) |                          |
| `recommended_allocation` | JSON       | Final blended allocation |
| `notes`                  | JSON       | Explanation strings      |
| `logged_at`              | DateTime   | Server-side insert time  |

---

## Phase Tracker

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Modular `ai_modules/` service layer, all 5 submodules scaffolded | ✅ Complete |
| Phase 2 | Multi-signal fraud scoring, ML toggle, per-signal logging | ✅ Complete |
| Phase 3 | New endpoints (`/v1/ai/*`), risk/credit/personalization logic | 🔜 Next |
| Phase 4 | Real ML models, feature stores, model registry integration | 🔜 Planned |
