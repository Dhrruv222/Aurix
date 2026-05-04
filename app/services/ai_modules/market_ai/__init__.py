# Re-export for convenience
from app.services.ai_modules.market_ai.service import forecast_price, batch_forecast, SUPPORTED_ASSETS

__all__ = ["forecast_price", "batch_forecast", "SUPPORTED_ASSETS"]
