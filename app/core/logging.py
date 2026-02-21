import logging
import sys

from app.core.config import settings


def setup_logging():
    if getattr(setup_logging, "_configured", False):
        return

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Suppress noisy third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    setup_logging._configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
