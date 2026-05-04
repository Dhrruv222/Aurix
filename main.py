from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

import app.models.logs  # noqa: F401
from app.api.v1 import fraud, health, portfolio
from app.api.v1.ai import risk as ai_risk
from app.api.v1.ai import investment as ai_investment
from app.api.v1.ai import credit as ai_credit
from app.api.v1.ai import personalization as ai_personalization
from app.api.v1.ai import forecast as ai_forecast
from app.api.v1.ai import vault as ai_vault
from app.api.v1.ai import orchestration as ai_orchestration
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import Base, engine

# Setup structured logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Pre-warm ML scorer so first request is not delayed by model training
    from app.services.ai_modules.core_ai.ml_scorer import warmup
    await asyncio.to_thread(warmup)
    yield

app = FastAPI(
    title="Aurix AI Service",
    description=(
        "Full-stack AI microservice for the Aurix fintech platform — "
        "fraud detection, portfolio optimization, credit scoring, market forecasting, "
        "vault management, regulatory compliance, and API orchestration."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    start_time = perf_counter()

    logger.info(
        f"[REQUEST] id={request_id} method={request.method} path={request.url.path}"
    )

    # Use a generous hard cap for the middleware so per-endpoint timeouts
    # (e.g. the dynamic compliance-report timeout) are not silently overridden.
    _REQUEST_HARD_TIMEOUT = 60.0
    try:
        response = await asyncio.wait_for(call_next(request), timeout=_REQUEST_HARD_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error(
            f"[RESPONSE] id={request_id} status=504 path={request.url.path} reason=timeout"
        )
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "code": "TIMEOUT",
                    "message": "Request timed out.",
                }
            },
        )
    except Exception:
        logger.exception(
            f"[RESPONSE] id={request_id} status=500 path={request.url.path} reason=unhandled_error"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                }
            },
        )

    duration_ms = (perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        f"[RESPONSE] id={request_id} status={response.status_code} path={request.url.path} "
        f"duration_ms={duration_ms:.2f}"
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    logger.error(f"[HTTP-ERROR] status={exc.status_code} detail={exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    logger.error(f"[VALIDATION-ERROR] errors={exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request payload.",
                "details": exc.errors(),
            }
        },
    )

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/v1", tags=["Health"])
app.include_router(fraud.router, prefix="/v1", tags=["Fraud Detection"])
app.include_router(portfolio.router, prefix="/v1", tags=["Portfolio"])

# ─── AI Module Routers (Phase 3) ──────────────────────────────────────────────
app.include_router(ai_risk.router, prefix="/v1/ai", tags=["Risk AI"])
app.include_router(ai_investment.router, prefix="/v1/ai", tags=["Investment AI"])
app.include_router(ai_credit.router, prefix="/v1/ai", tags=["Credit AI"])
app.include_router(ai_personalization.router, prefix="/v1/ai", tags=["Personalization AI"])
app.include_router(ai_forecast.router, prefix="/v1/ai", tags=["Market AI"])
app.include_router(ai_vault.router, prefix="/v1/ai", tags=["Vault AI"])
app.include_router(ai_orchestration.router, prefix="/v1/ai", tags=["Orchestration AI"])