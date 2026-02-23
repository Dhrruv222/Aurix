from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class FraudScoreRequest(BaseModel):
    user_id: str
    amount: float = Field(ge=0)
    currency: str = "EUR"
    device_id: Optional[str] = None
    location: Optional[str] = None  # e.g., "DE"
    timestamp: Optional[str] = None  # ISO string
    meta: Optional[Dict[str, Any]] = None

class FraudScoreResponse(BaseModel):
    risk_score: int  # 0-100
    decision: str    # "APPROVE" | "REVIEW" | "BLOCK"
    reasons: list[str]

class RecommendRequest(BaseModel):
    user_id: str
    portfolio: Dict[str, float]  # e.g. {"gold": 60, "crypto": 20, "stocks": 20}
    risk_profile: str = "medium" # "low"|"medium"|"high"
    meta: Optional[Dict[str, Any]] = None

class RecommendResponse(BaseModel):
    recommended_allocation: Dict[str, float]
    notes: list[str]
