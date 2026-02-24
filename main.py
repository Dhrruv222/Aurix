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
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import Base, engine

# Setup structured logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Aurix AI Service",
    description="AI microservice for fraud detection and portfolio recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid4())
    start_time = perf_counter()

    logger.info(
        f"[REQUEST] id={request_id} method={request.method} path={request.url.path}"
    )

    try:
        response = await asyncio.wait_for(call_next(request), timeout=settings.SCORING_TIMEOUT)
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/v1", tags=["Health"])
app.include_router(fraud.router, prefix="/v1", tags=["Fraud Detection"])
app.include_router(portfolio.router, prefix="/v1", tags=["Portfolio"])
