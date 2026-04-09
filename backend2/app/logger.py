"""
Centralised structured logger for the entire application.
Usage:
    from app.logger import logger
    logger.info("Message", extra={"user_id": 1, "action": "upload"})
"""
import logging
import sys
from app.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_LEVEL = logging.DEBUG if settings.DEBUG else logging.INFO


def get_logger(name: str = "collegeai") -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log

    log.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    log.addHandler(handler)

    # File handler for production
    if settings.ENVIRONMENT == "production":
        fh = logging.FileHandler("logs/app.log")
        fh.setFormatter(logging.Formatter(LOG_FORMAT))
        log.addHandler(fh)

    return log


logger = get_logger()
