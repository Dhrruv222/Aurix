from pydantic import BaseModel, Field
from typing import List, Dict


# ─── Fraud Score ──────────────────────────────────────────────────────────────

class FraudScoreRequest(BaseModel):
    user_id:   str   = Field(..., example="u123")
    amount:    float = Field(..., example=100.0)
    currency:  str   = Field(..., example="EUR")
    device_id: str   = Field(..., example="dev-1")
    location:  str   = Field(..., example="DE")
    timestamp: str   = Field(..., example="2026-02-19T10:00:00Z")


class FraudScoreResponse(BaseModel):
    risk_score: float
    decision:   str           # APPROVE | REVIEW | BLOCK
    reasons:    List[str]


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioRequest(BaseModel):
    user_id:      str              = Field(..., example="u123")
    portfolio:    Dict[str, float] = Field(..., example={"gold": 50, "stocks": 30, "crypto": 20})
    risk_profile: str              = Field(..., example="medium")  # low | medium | high


class PortfolioResponse(BaseModel):
    recommended_allocation: Dict[str, float]
    notes:                  List[str]
