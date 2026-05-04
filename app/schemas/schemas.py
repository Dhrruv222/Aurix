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
    risk_score: float = Field(..., ge=0, le=100)
    decision: Literal["APPROVE", "REVIEW", "BLOCK"]
    reasons: List[str] = Field(..., min_length=1)


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

    @field_validator("portfolio")
    @classmethod
    def validate_portfolio_values(cls, value: Dict[str, float]) -> Dict[str, float]:
        for asset, amount in value.items():
            if amount < 0:
                raise ValueError(f"portfolio value cannot be negative: {asset}")
        return value


class PortfolioResponse(BaseModel):
    recommended_allocation: Dict[str, float] = Field(..., min_length=1)
    notes: List[str] = Field(..., min_length=1)


# ─── Risk AI ──────────────────────────────────────────────────────────────────

class TransactionData(BaseModel):
    amount: float = Field(..., ge=0, example=9500.0)
    location: Optional[str] = Field(default=None, min_length=2, max_length=2, example="NG")
    hour_of_day: int = Field(default=12, ge=0, le=23, example=2)
    recent_tx_count: int = Field(default=1, ge=0, example=7)
    currencies_used: List[str] = Field(default_factory=list, example=["EUR", "USD", "BTC"])

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class AnalyzeRiskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    transaction: TransactionData


class AnomalyResult(BaseModel):
    anomaly_detected: bool
    anomaly_score: float = Field(..., ge=0, le=100)
    flags: List[str]


class AMLResult(BaseModel):
    aml_flag: bool
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    patterns: List[str]


class AnalyzeRiskResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict  # contains anomaly + aml sub-results
    metadata: Dict


# ─── Investment AI (optimize-portfolio) ──────────────────────────────────────

class OptimizePortfolioRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    portfolio: Dict[str, float] = Field(..., example={"gold": 40, "stocks": 40, "crypto": 20})
    risk_profile: str = Field(..., example="high")
    investment_horizon_months: Optional[int] = Field(default=None, ge=1, example=24)
    target_return_pct: Optional[float] = Field(default=None, ge=0, example=12.0)

    @field_validator("risk_profile")
    @classmethod
    def normalize_risk_profile(cls, value: str) -> str:
        normalized = value.lower().strip()
        valid_profiles = {"low", "medium", "high", "aggressive"}
        if normalized not in valid_profiles:
            raise ValueError(f"Unknown risk_profile: '{value}'. Valid: {sorted(valid_profiles)}")
        return normalized

    @field_validator("portfolio")
    @classmethod
    def validate_portfolio_values(cls, value: Dict[str, float]) -> Dict[str, float]:
        for asset, amount in value.items():
            if amount < 0:
                raise ValueError(f"portfolio value cannot be negative: {asset}")
        return value


class OptimizePortfolioResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Credit AI ────────────────────────────────────────────────────────────────

class CreditScoreRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    savings_rate: float = Field(..., ge=0.0, le=1.0, example=0.25,
                                description="Monthly savings as a fraction of income (0.0–1.0)")
    gold_value_usd: float = Field(..., ge=0, example=8000.0)
    repayment_rate: float = Field(..., ge=0.0, le=1.0, example=0.95,
                                  description="Fraction of past repayments made on time (0.0–1.0)")
    tenure_months: int = Field(..., ge=0, example=18)
    requested_loan_amount: Optional[float] = Field(default=None, ge=0, example=5000.0)


class CreditScoreResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Personalization AI ───────────────────────────────────────────────────────

class TransactionHistoryItem(BaseModel):
    description: str = Field(..., example="Grocery store purchase")
    amount: float = Field(..., ge=0, example=85.50)
    type: Literal["debit", "credit"] = Field(..., example="debit")


class UserInsightsRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    savings_rate: float = Field(default=0.0, ge=0.0, le=1.0, example=0.12)
    investment_allocation_pct: float = Field(default=0.0, ge=0.0, example=8.0)
    gold_value_usd: float = Field(default=0.0, ge=0, example=3500.0)
    top_spending_category: Optional[str] = Field(default=None, example="food")
    monthly_income: float = Field(default=0.0, ge=0, example=4000.0)
    transaction_history: List[TransactionHistoryItem] = Field(default_factory=list)


class UserInsightsResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Market AI (price forecasting) ───────────────────────────────────────────

class PriceForecastRequest(BaseModel):
    asset: str = Field(
        ...,
        description="Asset symbol: gold, silver, btc, eth, spy, xau",
        example="gold",
    )
    horizon_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Forecast horizon in calendar days (1–365)",
        example=30,
    )
    current_price: Optional[float] = Field(
        default=None,
        gt=0,
        description="Live price override in USD. Uses calibrated baseline if omitted.",
        example=2300.0,
    )

    @field_validator("asset")
    @classmethod
    def normalize_asset(cls, value: str) -> str:
        return value.lower().strip()


class PriceForecastResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


class BatchForecastRequest(BaseModel):
    assets: List[str] = Field(
        ...,
        min_length=1,
        description="List of asset symbols to forecast",
        example=["gold", "btc", "eth"],
    )
    horizon_days: int = Field(
        default=30,
        ge=1,
        le=365,
        example=30,
    )

    @field_validator("assets")
    @classmethod
    def normalize_assets(cls, value: List[str]) -> List[str]:
        return [v.lower().strip() for v in value]


class BatchForecastResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Personalization AI — Goal Optimization ───────────────────────────────────

_VALID_RISK_PROFILES = {"low", "medium", "high", "aggressive"}


class GoalOptimizationRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    target_amount: float = Field(
        ..., gt=0, description="Goal target amount in USD", example=20000.0
    )
    current_savings: float = Field(
        default=0.0, ge=0, description="Current savings balance in USD", example=3000.0
    )
    monthly_income: float = Field(
        ..., gt=0, description="Monthly take-home income in USD", example=5000.0
    )
    monthly_expenses: float = Field(
        default=0.0, ge=0, description="Fixed monthly expenses in USD", example=2500.0
    )
    risk_profile: str = Field(
        default="medium",
        description="Investment risk profile: low / medium / high / aggressive",
        example="medium",
    )
    time_horizon_months: int = Field(
        ..., ge=1, description="Target months to reach the goal", example=24
    )

    @field_validator("risk_profile")
    @classmethod
    def normalize_risk_profile(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in _VALID_RISK_PROFILES:
            raise ValueError(
                f"Unknown risk_profile: '{value}'. Valid: {sorted(_VALID_RISK_PROFILES)}"
            )
        return normalized


class GoalOptimizationResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Investment AI — Rebalancing ──────────────────────────────────────────────

class RebalanceRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    portfolio_values_usd: Dict[str, float] = Field(
        ...,
        description="Current USD value per asset, e.g. {'gold': 5000, 'stocks': 2000}",
        example={"gold": 5000.0, "stocks": 2000.0, "crypto": 500.0},
    )
    risk_profile: str = Field(..., example="medium")

    @field_validator("risk_profile")
    @classmethod
    def normalize_risk_profile(cls, value: str) -> str:
        normalized = value.lower().strip()
        valid_profiles = {"low", "medium", "high", "aggressive"}
        if normalized not in valid_profiles:
            raise ValueError(f"Unknown risk_profile: '{value}'. Valid: {sorted(valid_profiles)}")
        return normalized

    @field_validator("portfolio_values_usd")
    @classmethod
    def validate_values(cls, value: Dict[str, float]) -> Dict[str, float]:
        for asset, v in value.items():
            if v < 0:
                raise ValueError(f"portfolio value cannot be negative: {asset}")
        return value


class RebalanceResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Investment AI — Crowdfunding Scoring ─────────────────────────────────────

class CrowdfundingScoreRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    team_experience_years: int = Field(default=0, ge=0, example=5)
    previous_exits: int = Field(default=0, ge=0, example=1)
    market_size_usd_m: float = Field(default=0.0, ge=0, example=500.0,
                                     description="Total addressable market in USD millions")
    monthly_revenue_usd: float = Field(default=0.0, ge=0, example=50000.0)
    monthly_growth_rate_pct: float = Field(default=0.0, example=8.5,
                                           description="Month-over-month revenue growth %")
    runway_months: int = Field(default=0, ge=0, example=18)
    burn_rate_usd: float = Field(default=1.0, gt=0, example=30000.0)
    num_competitors: int = Field(default=0, ge=0, example=4)
    has_regulatory_approval: bool = Field(default=False, example=True)
    sector: str = Field(default="other", example="fintech")


class CrowdfundingScoreResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Vault AI ─────────────────────────────────────────────────────────────────

class VaultForecastRequest(BaseModel):
    vault_id: str = Field(..., min_length=1, example="vault-dubai-01")
    current_stock_kg: float = Field(..., gt=0, example=500.0)
    recent_daily_outflows: List[float] = Field(
        ...,
        min_length=1,
        description="Last N days of outflow in kg, most recent last",
        example=[3.2, 2.8, 4.1, 3.5, 2.9],
    )
    horizon_days: int = Field(default=30, ge=1, le=365, example=30)
    seasonality_factor: float = Field(
        default=1.0, gt=0, example=1.1,
        description="Demand multiplier for seasonal peaks (1.0 = no adjustment)"
    )

    @field_validator("recent_daily_outflows")
    @classmethod
    def validate_outflows(cls, value: List[float]) -> List[float]:
        for v in value:
            if v < 0:
                raise ValueError("Daily outflow values cannot be negative.")
        return value


class VaultForecastResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


class RedemptionForecastRequest(BaseModel):
    asset: str = Field(..., example="gold", description="gold / silver / platinum")
    recent_daily_requests: List[float] = Field(
        ...,
        min_length=1,
        description="Past N days of redemption requests in kg",
        example=[1.1, 1.3, 0.9, 1.5, 1.2, 1.0, 0.8],
    )
    horizon_days: int = Field(default=7, ge=1, le=90, example=7)
    price_trend: str = Field(
        default="neutral",
        description="Current price trend: bullish / neutral / bearish",
        example="neutral",
    )

    @field_validator("price_trend")
    @classmethod
    def normalize_trend(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"bullish", "neutral", "bearish"}:
            raise ValueError(f"Unknown price_trend: '{value}'. Valid: bullish, neutral, bearish")
        return normalized


class RedemptionForecastResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


class SupplyChainCheckRequest(BaseModel):
    shipment_id: str = Field(..., min_length=1, example="SHP-2026-001")
    declared_weight_kg: float = Field(default=0.0, ge=0, example=100.0)
    measured_weight_kg: float = Field(default=0.0, ge=0, example=99.5)
    carrier: str = Field(default="", example="Brinks")
    origin_country: str = Field(default="", example="CH")
    destination_country: str = Field(default="", example="AE")
    asset_value_usd: float = Field(default=0.0, ge=0, example=6_000_000.0)
    vault_total_value_usd: float = Field(default=1.0, gt=0, example=30_000_000.0)
    asset_type: str = Field(default="gold", example="gold")


class SupplyChainCheckResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Orchestration AI ─────────────────────────────────────────────────────────

class BrokerRoutingRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    asset_type: str = Field(
        ...,
        description="Asset class to trade: gold, silver, crypto, stocks, etf, etc.",
        example="gold",
    )
    order_size_usd: float = Field(..., gt=0, example=10_000.0)
    priority: str = Field(
        default="cost",
        description="Routing priority: cost / speed / liquidity",
        example="cost",
    )
    required_kyc_tier: int = Field(default=1, ge=1, le=3, example=1)
    user_region: str = Field(default="EU", example="EU")

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"cost", "speed", "liquidity"}:
            raise ValueError(f"Unknown priority: '{value}'. Valid: cost, speed, liquidity")
        return normalized


class BrokerRoutingResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


class FeeOptimizationRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    current_broker: str = Field(..., example="eToro")
    planned_trades: List[Dict] = Field(
        ...,
        min_length=1,
        description="List of planned trades: [{asset_type, order_size_usd}]",
        example=[
            {"asset_type": "gold", "order_size_usd": 10000},
            {"asset_type": "stocks", "order_size_usd": 5000},
        ],
    )


class FeeOptimizationResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


class PortfolioSyncRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    portfolios_by_broker: Dict[str, Dict[str, float]] = Field(
        ...,
        description="Dict of {broker_name: {asset: usd_value}}",
        example={
            "Revolut": {"gold": 5000.0, "stocks": 2000.0},
            "Binance": {"crypto": 3000.0},
        },
    )


class PortfolioSyncResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Credit AI — Save Now, Buy Later (SNBL) ───────────────────────────────────

class SNBLRequest(BaseModel):
    user_id: str = Field(..., min_length=1, example="u123")
    item_price_usd: float = Field(..., gt=0, example=1200.0,
                                  description="Purchase price of the item in USD")
    num_instalments: int = Field(
        default=12, ge=1, le=36,
        description="Number of monthly instalments (1–36)",
        example=12,
    )
    monthly_income: float = Field(..., gt=0, example=4000.0,
                                  description="Net monthly income in USD")
    monthly_expenses: float = Field(default=0.0, ge=0, example=2200.0,
                                    description="Fixed monthly outgoings in USD")
    savings_rate: float = Field(default=0.0, ge=0.0, le=1.0, example=0.15)
    gold_value_usd: float = Field(default=0.0, ge=0, example=2000.0,
                                  description="Gold held as potential collateral")
    repayment_rate: float = Field(default=1.0, ge=0.0, le=1.0, example=0.95)
    tenure_months: int = Field(default=0, ge=0, example=12)


class SNBLResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict


# ─── Risk AI — Regulatory Compliance Report ───────────────────────────────────

class ComplianceTransactionItem(BaseModel):
    transaction_id: str = Field(..., min_length=1, example="txn-001")
    user_id: str = Field(..., min_length=1, example="u123")
    amount: float = Field(..., ge=0, example=9500.0)
    location: Optional[str] = Field(default=None, min_length=2, max_length=2, example="NG")
    hour_of_day: int = Field(default=12, ge=0, le=23, example=2)
    recent_tx_count: int = Field(default=1, ge=0, example=6)
    currencies_used: List[str] = Field(default_factory=list, example=["EUR", "USD", "BTC"])

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class ComplianceReportRequest(BaseModel):
    report_id: Optional[str] = Field(
        default=None,
        description="Optional caller-supplied report ID. Auto-generated if omitted.",
        example="RPT-2026-04",
    )
    reporting_period: Optional[str] = Field(
        default=None,
        description="Human-readable period label, e.g. '2026-04'",
        example="2026-04",
    )
    transactions: List[ComplianceTransactionItem] = Field(
        ...,
        min_length=1,
        description="Batch of transactions to screen",
    )


class ComplianceReportResponse(BaseModel):
    status: Literal["success"] = "success"
    data: Dict
    metadata: Dict
