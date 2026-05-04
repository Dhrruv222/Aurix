# Re-export schemas used by core_ai from the canonical schemas module.
# Add core_ai-specific schemas here as the engine evolves.
from app.schemas.schemas import FraudScoreRequest, FraudScoreResponse

__all__ = ["FraudScoreRequest", "FraudScoreResponse"]
