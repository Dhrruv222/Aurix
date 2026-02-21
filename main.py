from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models.logs  # noqa: F401
from app.api.v1 import fraud, health, portfolio
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import Base, engine

# Setup structured logging
setup_logging()


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
