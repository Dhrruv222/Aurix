# Aurix AI Service — Phase 1

Python FastAPI microservice for fraud detection and portfolio recommendations.

## Project Structure

```
ai-service/
├── main.py                     # App entry point
├── requirements.txt
├── .env.example                # Copy to .env and fill in values
└── app/
    ├── api/v1/
    │   ├── health.py           # GET  /v1/health
    │   ├── fraud.py            # POST /v1/fraud-score
    │   └── portfolio.py        # POST /v1/recommend-portfolio
    ├── core/
    │   ├── config.py           # Environment-based settings
    │   └── logging.py          # Structured logging setup
    ├── db/
    │   └── database.py         # PostgreSQL connection
    ├── models/
    │   └── logs.py             # SQLAlchemy DB tables
    └── schemas/
        └── schemas.py          # Pydantic request/response models
```

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and provide required DATABASE_URL and origins

# 4. Run the service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/v1/health` | Health check |
| POST | `/v1/fraud-score` | Evaluate transaction risk |
| POST | `/v1/recommend-portfolio` | Get AI portfolio recommendation |

Swagger docs: http://127.0.0.1:8001/docs

## Fraud Score — Request & Response

**Request:**
```json
{
  "user_id": "u123",
  "amount": 100,
  "currency": "EUR",
  "device_id": "dev-1",
  "location": "DE",
  "timestamp": "2026-02-19T10:00:00Z"
}
```

**Response:**
```json
{
  "risk_score": 10,
  "decision": "APPROVE",
  "reasons": ["No risk signals detected (MVP rules)"]
}
```

Decision values:
- `APPROVE` → proceed with transaction
- `REVIEW` → hold for manual review
- `BLOCK` → reject transaction

## Portfolio Recommendation — Request & Response

**Request:**
```json
{
  "user_id": "u123",
  "portfolio": {"gold": 50, "stocks": 30, "crypto": 20},
  "risk_profile": "medium"
}
```

**Response:**
```json
{
  "recommended_allocation": {"gold": 55, "stocks": 30, "crypto": 15},
  "notes": ["Medium risk profile → balanced allocation across assets."]
}
```

Risk profiles: `low`, `medium`, `high`, `aggressive`

## Architecture

```
Frontend (React / Flutter)
        ↓
Node.js Backend
        ↓
AI Service (FastAPI) ← You are here
   - /v1/fraud-score
   - /v1/recommend-portfolio
        ↓
PostgreSQL (fraud_logs, portfolio_logs)
```

## Phase 1 Checklist

- [x] CORS configuration
- [x] Environment-based config (dev/prod via .env)
- [x] Structured logging for all requests and responses
- [x] Fraud-score endpoint integrated and ready for Node.js connection
- [x] Persistent DB logging (risk_score, decision, reasons, timestamp)
- [x] Error handling and timeout protection (2s default)
- [x] API versioning (/v1/ prefix)
