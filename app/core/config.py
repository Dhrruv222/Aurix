from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

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
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    ALLOW_CREDENTIALS: bool = False

    # AI Scoring timeout (seconds)
    SCORING_TIMEOUT: float = 5.0

    # Fraud thresholds
    HIGH_RISK_AMOUNT: float = 10000.0
    MEDIUM_RISK_AMOUNT: float = 5000.0

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> List[str]:
        if isinstance(value, str):
            if value.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
