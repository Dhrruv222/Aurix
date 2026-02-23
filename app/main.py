from fastapi import FastAPI
from app.schemas import (
    FraudScoreRequest, FraudScoreResponse,
    RecommendRequest, RecommendResponse
)
from app.services.fraud import score_transaction
from app.services.recommend import recommend

app = FastAPI(title="Aurix AI Service", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/fraud-score", response_model=FraudScoreResponse)
def fraud_score(req: FraudScoreRequest):
    risk, decision, reasons = score_transaction(req.amount, req.currency, req.location)
    return FraudScoreResponse(risk_score=risk, decision=decision, reasons=reasons)

@app.post("/recommend-portfolio", response_model=RecommendResponse)
def recommend_portfolio(req: RecommendRequest):
    rec, notes = recommend(req.portfolio, req.risk_profile)
    return RecommendResponse(recommended_allocation=rec, notes=notes)
