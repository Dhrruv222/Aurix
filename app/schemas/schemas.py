from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic import field_validator


# ─── Fraud Score ──────────────────────────────────────────────────────────────

class FraudScoreRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    amount: float = Field(..., ge=0, example=100.0)
    currency: str = Field(..., min_length=3, max_length=3, example="EUR")
    device_id: Optional[str] = Field(default=None, example="dev-1")
    location: Optional[str] = Field(default=None, min_length=2, max_length=2, example="DE")
    timestamp: datetime = Field(..., example="2026-02-19T10:00:00Z")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.upper()


class FraudScoreResponse(BaseModel):
    risk_score: float
    decision: Literal["APPROVE", "REVIEW", "BLOCK"]
    reasons: List[str]


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    portfolio: Dict[str, float] = Field(..., example={"gold": 50, "stocks": 30, "crypto": 20})
    risk_profile: str = Field(..., example="medium")

    @field_validator("risk_profile")
    @classmethod
    def normalize_risk_profile(cls, value: str) -> str:
        normalized = value.lower().strip()
        valid_profiles = {"low", "medium", "high", "aggressive"}
        if normalized not in valid_profiles:
            raise ValueError(f"Unknown risk_profile: '{value}'. Valid: {sorted(valid_profiles)}")
        return normalized


class PortfolioResponse(BaseModel):
    recommended_allocation: Dict[str, float]
    notes: List[str]
