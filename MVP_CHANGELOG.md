# Aurix AI Service — MVP Change Log

## Overview
This document summarizes all backend changes completed to align the AI service with MVP requirements for stable demo and integration.

Target flow:
**Frontend -> Node.js -> /v1/fraud-score -> decision response -> UI display**

---

## 1) API Versioning
- Confirmed all endpoints are mounted under `/v1`.
- Routing is configured centrally in `main.py`.

Implemented endpoints:
- `GET /v1/health`
- `POST /v1/fraud-score`
- `POST /v1/recommend-portfolio`

---

## 2) Fraud Scoring Contract
- Request schema is validated with Pydantic.
- Response contract is stable and includes:
  - `risk_score` (number)
  - `decision` (`APPROVE | REVIEW | BLOCK`)
  - `reasons` (array of strings)
- Decision type was tightened to explicit allowed values.

---

## 3) Logging Improvements
- Structured logging enabled for:
  - Incoming HTTP requests
  - Outgoing HTTP responses (including status and duration)
  - Fraud/portfolio endpoint request and response events
- Error paths now log stack traces using exception logging.
- Logging setup was made idempotent to avoid duplicate handlers during reloads.

---

## 4) Database Logging
Fraud decisions are persisted to PostgreSQL with required fields:
- `risk_score`
- `decision`
- `timestamp`

Additional persisted context includes user/transaction metadata and reasons.

---

## 5) Configuration Hardening
- Environment-based settings are centralized in `app/core/config.py`.
- `DATABASE_URL` is now required from environment variables (no hardcoded runtime default).
- `.env.example` was updated to template-only values:
  - blank required DB URL
  - comma-separated CORS origins format
  - timeout default aligned to MVP target

---

## 6) Reliability & Stability
- Added global HTTP middleware to provide:
  - request/response structured logging
  - request timeout protection
  - crash-safe fallback JSON response on unexpected failures
- Added global exception handlers for:
  - `HTTPException`
  - request validation errors
- Timeout default aligned to MVP latency target (`SCORING_TIMEOUT=2.0`).

---

## 7) CORS / Integration Readiness
- CORS middleware enabled and controlled by environment settings.
- Origins are configurable via `ALLOWED_ORIGINS`.
- Credentials behavior is explicit via `ALLOW_CREDENTIALS`.

---

## 8) Code Quality & Refactor Highlights
- Replaced older executor pattern with `asyncio.to_thread(...)` for cleaner async handling.
- Moved DB table creation to FastAPI lifespan startup phase.
- Updated SQLAlchemy declarative import to modern path.
- Normalized formatting and consistency across core modules.
- Added `.gitignore` to prevent cache/env artifacts from polluting commits.

---

## 9) Current MVP Scope (Intentionally Limited)
Included:
- Stable APIs
- Rule-based fraud scoring
- Portfolio recommendation mapping
- Structured logs
- DB persistence
- Timeout/error handling

Not included (by design):
- Advanced ML models
- Anomaly detection
- AML/loan modules
- Rate limiting
- Advanced monitoring stack

---

## 10) Validation Status
- Python compile checks pass after refactor.
- API contract remains consistent for Node.js integration.
- Health endpoint returns OK structure for status checks.

Note: Editor import warnings for `fastapi` depend on local interpreter/environment setup and are not code syntax failures.

---

## 11) Files Updated in Recent MVP Alignment
- `main.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/db/database.py`
- `app/schemas/schemas.py`
- `app/api/v1/fraud.py`
- `app/api/v1/portfolio.py`
- `app/models/logs.py`
- `.env.example`
- `README.md`
- `.gitignore`

---

## 12) Next Step Recommendation
For Phase 2, keep the API contract unchanged and swap only the fraud scoring internals (`compute_fraud_score`) with model inference to avoid breaking frontend/Node integration.
