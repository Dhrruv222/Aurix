# Aurix AI Service — Integration Test Suite

Base URL: `http://127.0.0.1:8001`  
API Version Prefix: `/v1`

PowerShell note: in Windows PowerShell, `curl` maps to `Invoke-WebRequest`. Use `curl.exe` (shown below) or `Invoke-RestMethod`.

---

## 1) cURL Commands

## 1.1 Health Check

```bash
curl.exe -i -X GET "http://127.0.0.1:8001/v1/health"
```

PowerShell alternative:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8001/v1/health"
```

Expected:
- HTTP `200 OK`
- JSON response indicating service health

## 1.2 Fraud Score (BLOCK scenario)

Condition for BLOCK in current MVP logic: `amount > 10000`.

```bash
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u123",
    "amount": 15000,
    "currency": "EUR",
    "device_id": "dev-1",
    "location": "DE",
    "timestamp": "2026-02-19T10:00:00Z"
  }'
```

Expected:
- HTTP `200 OK`
- JSON contains:
  - `risk_score`
  - `decision` = `"BLOCK"`
  - `reasons` (array)

## 1.3 Portfolio Recommendation (medium risk profile)

```bash
curl.exe -i -X POST "http://127.0.0.1:8001/v1/recommend-portfolio" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u123",
    "portfolio": {
      "gold": 50,
      "stocks": 30,
      "crypto": 20
    },
    "risk_profile": "medium"
  }'
```

Expected:
- HTTP `200 OK`
- JSON contains:
  - `recommended_allocation` (object)
  - `notes` (array)

---

## 2) Postman Raw JSON Payloads

Use **Body → raw → JSON** in Postman.

## 2.1 `POST /v1/fraud-score` payload

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

Schema alignment:
- `user_id`: string
- `amount`: number
- `currency`: 3-letter string
- `device_id`: optional string
- `location`: optional 2-letter string
- `timestamp`: ISO datetime string

## 2.2 `POST /v1/recommend-portfolio` payload

```json
{
  "user_id": "u123",
  "portfolio": {
    "gold": 50,
    "stocks": 30,
    "crypto": 20
  },
  "risk_profile": "medium"
}
```

Schema alignment:
- `user_id`: string
- `portfolio`: object of numeric asset values
- `risk_profile`: one of `low | medium | high | aggressive`

---

## 3) Validation Test (422 Unprocessable Entity)

Deliberately send invalid `amount` type (`string` instead of `number`) to test validation and global 422 error shaping.

```bash
curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u-invalid",
    "amount": "not-a-number",
    "currency": "EUR",
    "device_id": "dev-x",
    "location": "DE",
    "timestamp": "2026-02-19T10:00:00Z"
  }'
```

Expected:
- HTTP `422 Unprocessable Entity`
- Error wrapper from `main.py` validation handler, including:
  - `error.code = "VALIDATION_ERROR"`
  - `error.message = "Invalid request payload."`
  - `error.details` with field-level validation info

---

## 4) Required Headers for POST Requests

All POST tests above include:
- `Content-Type: application/json`

---

## 5) Windows PowerShell Copy/Paste Commands (One-Line)

Use these directly in PowerShell:

```powershell
curl.exe -i -X GET "http://127.0.0.1:8001/v1/health"

curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" -H "Content-Type: application/json" -d '{"user_id":"u123","amount":15000,"currency":"EUR","device_id":"dev-1","location":"DE","timestamp":"2026-02-19T10:00:00Z"}'

curl.exe -i -X POST "http://127.0.0.1:8001/v1/recommend-portfolio" -H "Content-Type: application/json" -d '{"user_id":"u123","portfolio":{"gold":50,"stocks":30,"crypto":20},"risk_profile":"medium"}'

curl.exe -i -X POST "http://127.0.0.1:8001/v1/fraud-score" -H "Content-Type: application/json" -d '{"user_id":"u-invalid","amount":"not-a-number","currency":"EUR","device_id":"dev-x","location":"DE","timestamp":"2026-02-19T10:00:00Z"}'
```
