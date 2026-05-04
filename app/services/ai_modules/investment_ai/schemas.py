# Re-export schemas used by investment_ai from the canonical schemas module.
# Add investment_ai-specific schemas here as the engine evolves.
from app.schemas.schemas import PortfolioRequest, PortfolioResponse

__all__ = ["PortfolioRequest", "PortfolioResponse"]
