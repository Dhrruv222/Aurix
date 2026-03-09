# Aurix AI Service — MVP Implementation & Test Guide

Date: 2026-03-01

## 1) What changed

### Core API behavior
- Implemented strict rule-based fraud decisions in `POST /v1/fraud-score`:
  - `BLOCK` if `amount > HIGH_RISK_AMOUNT`
  - `REVIEW` if `amount > MEDIUM_RISK_AMOUNT`
  - `APPROVE` otherwise
- Fraud response is stable and lean: `risk_score`, `decision`, `reasons`.
- Portfolio recommendation (`POST /v1/recommend-portfolio`) now uses `risk_profile` + current allocation:
  - Normalizes input allocation
  - Blends target profile weights (70%) + current allocation (30%)
  - Returns `recommended_allocation` + `notes`

### Request correlation & structured logging
- Middleware now stores request id in request context:
  - `request.state.request_id = request_id`
- Fraud endpoint logs include `request_id` and `decision`.

### Database persistence
- Fraud requests persist to `fraud_logs` with:
  - `request_id`, `risk_score`, `decision`, `timestamp`, and payload fields
- `FraudLog` model updated:
  - Added `request_id` column
  - `timestamp` changed to `DateTime(timezone=True)`

### Schema hardening
- `FraudScoreResponse`:
  - `risk_score` constrained to `0..100`
  - `reasons` requires at least 1 item
- `PortfolioRequest`:
  - validates non-negative values in `portfolio`
  - enforces valid `risk_profile` values: `low|medium|high|aggressive`
- `PortfolioResponse`:
  - ensures non-empty `recommended_allocation` and `notes`

### Migrations added
- `scripts/migrations/20260301_fraud_logs_request_id_and_timestamp.sql`
  - Adds `request_id`
  - Adds `timestamp_raw` backup column
  - Safely converts legacy `timestamp` text to `TIMESTAMPTZ`
  - Creates index on `request_id`
- `scripts/migrations/20260301_fraud_logs_timestamp_backfill.sql`
  - Backfills `timestamp` from `timestamp_raw` for common formats
  - Safe to re-run

---

## 2) Files changed

- `main.py`
- `app/api/v1/fraud.py`
- `app/api/v1/portfolio.py`
- `app/schemas/schemas.py`
- `app/models/logs.py`
- `scripts/migrations/20260301_fraud_logs_request_id_and_timestamp.sql`
- `scripts/migrations/20260301_fraud_logs_timestamp_backfill.sql`

---

## 3) How to test (PowerShell)

## 3.1 Pre-checks

1. Activate venv and install deps:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Ensure `.env` has at least:
```dotenv
DATABASE_URL=postgresql+psycopg2://<user>:<pass>@<host>:5432/<db>
SCORING_TIMEOUT=2.0
HIGH_RISK_AMOUNT=10000.0
MEDIUM_RISK_AMOUNT=5000.0
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ALLOW_CREDENTIALS=False
```

## 3.2 Run DB migrations

```powershell
psql "$env:DATABASE_URL" -f "scripts/migrations/20260301_fraud_logs_request_id_and_timestamp.sql"
psql "$env:DATABASE_URL" -f "scripts/migrations/20260301_fraud_logs_timestamp_backfill.sql"
```

Migration verification:
```powershell
psql "$env:DATABASE_URL" -c "\d+ fraud_logs"
psql "$env:DATABASE_URL" -c "SELECT COUNT(*) AS remaining_null_timestamps FROM fraud_logs WHERE timestamp IS NULL AND timestamp_raw IS NOT NULL;"
```

## 3.3 Start service

```powershell
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Health check:
```powershell
curl.exe -i http://127.0.0.1:8001/v1/health
```

Expected: HTTP 200 and body with service health status.

## 3.4 Fraud scoring endpoint tests

### A) APPROVE case (amount <= 5000)
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-approve\",\"amount\":1000,\"currency\":\"EUR\",\"device_id\":\"dev-1\",\"location\":\"DE\",\"timestamp\":\"2026-03-01T10:00:00Z\"}"
```
Expected:
- `decision = APPROVE`
- response contains `risk_score`, `decision`, `reasons`
- response header contains `X-Request-ID`

### B) REVIEW case (5000 < amount <= 10000)
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-review\",\"amount\":7000,\"currency\":\"EUR\",\"device_id\":\"dev-2\",\"location\":\"DE\",\"timestamp\":\"2026-03-01T10:05:00Z\"}"
```
Expected: `decision = REVIEW`.

### C) BLOCK case (amount > 10000)
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-block\",\"amount\":15000,\"currency\":\"EUR\",\"device_id\":\"dev-3\",\"location\":\"DE\",\"timestamp\":\"2026-03-01T10:10:00Z\"}"
```
Expected: `decision = BLOCK`.

## 3.5 Portfolio endpoint tests

### D) Aggressive profile (crypto should be relatively higher)
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/recommend-portfolio" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-port-1\",\"portfolio\":{\"gold\":50,\"stocks\":30,\"crypto\":20},\"risk_profile\":\"aggressive\"}"
```
Expected:
- `recommended_allocation` exists with `gold|stocks|crypto`
- `notes` is non-empty
- crypto is higher vs low-risk output

### E) Low profile (gold should be relatively higher)
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/recommend-portfolio" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-port-2\",\"portfolio\":{\"gold\":10,\"stocks\":60,\"crypto\":30},\"risk_profile\":\"low\"}"
```
Expected: recommended gold allocation trends higher than aggressive profile output.

## 3.6 Validation/error tests

### F) Invalid risk profile
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/recommend-portfolio" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-bad\",\"portfolio\":{\"gold\":50,\"stocks\":30,\"crypto\":20},\"risk_profile\":\"extreme\"}"
```
Expected: HTTP 422 with validation error payload.

### G) Missing required field in fraud payload
```powershell
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u-missing\",\"amount\":1000,\"currency\":\"EUR\"}"
```
Expected: HTTP 422 with standardized validation error body.

## 3.7 CORS test

```powershell
curl.exe -i -X OPTIONS "http://127.0.0.1:8001/v1/fraud-score" ^
  -H "Origin: http://localhost:3000" ^
  -H "Access-Control-Request-Method: POST"
```
Expected: CORS headers present (e.g., `access-control-allow-origin`).

## 3.8 DB logging verification

After running fraud requests:
```powershell
psql "$env:DATABASE_URL" -c "SELECT id, request_id, user_id, amount, risk_score, decision, timestamp, logged_at FROM fraud_logs ORDER BY id DESC LIMIT 10;"
```

Expected:
- New row per fraud request
- `request_id` populated
- `decision` matches API response
- `timestamp` populated in timestamptz

---

## 4) Notes for integration testing

- Fraud decision logic is intentionally rule-only (no ML) for MVP stability.
- Request timeout remains controlled by `SCORING_TIMEOUT` (default 2.0s).
- DB logging failures do not break API response (rollback + warning log).
- CORS remains enabled via environment-driven settings.
