from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Health Check")
def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.ENV,
        "version": "1.0.0",
    }
