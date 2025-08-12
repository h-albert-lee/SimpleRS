import logging
from logging.config import dictConfig
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "access": {
            "format": "%(asctime)s - %(levelname)s - %(client_addr)s - %(request_line)s - %(status_code)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO",
        },
        "app_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "default",
            "filename": str(LOG_DIR / "app.log"),
            "when": "H",
            "interval": 6,
            "backupCount": 10,
            "level": "INFO",
        },
        "error_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "default",
            "filename": str(LOG_DIR / "error.log"),
            "when": "W0",
            "interval": 1,
            "backupCount": 4,
            "level": "ERROR",
        },
        "access_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "access",
            "filename": str(LOG_DIR / "access.log"),
            "when": "D",
            "interval": 1,
            "backupCount": 7,
            "level": "INFO",
        },
    },
    "loggers": {
        "uvicorn.error": {
            "handlers": ["error_file", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access_file"],
            "level": "INFO",
            "propagate": False,
        },
        "": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
        },
    },
}

def init_logging() -> None:
    """Initialize logging configuration for the API."""
    dictConfig(LOGGING_CONFIG)
