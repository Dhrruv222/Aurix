from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import fraud, portfolio, health
from app.db.database import engine, Base

# Setup structured logging
setup_logging()

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Aurix AI Service",
    description="AI microservice for fraud detection and portfolio recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/v1", tags=["Health"])
app.include_router(fraud.router,     prefix="/v1", tags=["Fraud Detection"])
app.include_router(portfolio.router, prefix="/v1", tags=["Portfolio"])
