from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    ENV: str = "dev"
    APP_NAME: str = "Aurix AI Service"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/aurix_ai"

    # CORS — in prod, replace * with your actual frontend URLs
    ALLOWED_ORIGINS: List[str] = ["*"]

    # AI Scoring timeout (seconds)
    SCORING_TIMEOUT: float = 5.0

    # Fraud thresholds
    HIGH_RISK_AMOUNT: float = 10000.0
    MEDIUM_RISK_AMOUNT: float = 5000.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
