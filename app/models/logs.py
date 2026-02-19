from sqlalchemy import Column, String, Float, DateTime, JSON, Integer
from sqlalchemy.sql import func
from app.db.database import Base


class FraudLog(Base):
    """Persistent log of every fraud scoring decision."""
    __tablename__ = "fraud_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(String, nullable=False, index=True)
    amount      = Column(Float, nullable=False)
    currency    = Column(String(10), nullable=False)
    device_id   = Column(String, nullable=True)
    location    = Column(String(10), nullable=True)
    risk_score  = Column(Float, nullable=False)
    decision    = Column(String(20), nullable=False)   # APPROVE / REVIEW / BLOCK
    reasons     = Column(JSON, nullable=False)          # list of reason strings
    timestamp   = Column(String, nullable=False)        # original request timestamp
    logged_at   = Column(DateTime(timezone=True), server_default=func.now())


class PortfolioLog(Base):
    """Persistent log of every portfolio recommendation."""
    __tablename__ = "portfolio_logs"

    id                     = Column(Integer, primary_key=True, index=True)
    user_id                = Column(String, nullable=False, index=True)
    input_portfolio        = Column(JSON, nullable=False)
    risk_profile           = Column(String(20), nullable=False)
    recommended_allocation = Column(JSON, nullable=False)
    notes                  = Column(JSON, nullable=False)
    logged_at              = Column(DateTime(timezone=True), server_default=func.now())
