"""
pipeline/config.py

Reads all required environment variables at import time.
Logs a descriptive error naming any missing variable and exits with code 1.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_REQUIRED_ENV_VARS = [
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "SAPS_DATA_URL",
    "QLFS_URL",
    "OPEN_METEO_URL",
]


def _load_config() -> dict:
    """Load and validate all required environment variables.

    Returns a dict mapping variable name to value.
    Logs an error and calls sys.exit(1) for any missing variable.
    """
    config: dict = {}
    for var in _REQUIRED_ENV_VARS:
        value = os.environ.get(var)
        if value is None:
            logger.error(
                "Required environment variable '%s' is not set. "
                "Please define it before starting the pipeline.",
                var,
            )
            sys.exit(1)
        config[var] = value
    return config


# Module-level config dict — populated when this module is first imported.
CONFIG = _load_config()

# Convenience accessors
DB_HOST: str = CONFIG["DB_HOST"]
DB_PORT: str = CONFIG["DB_PORT"]
DB_NAME: str = CONFIG["DB_NAME"]
DB_USER: str = CONFIG["DB_USER"]
DB_PASSWORD: str = CONFIG["DB_PASSWORD"]
SAPS_DATA_URL: str = CONFIG["SAPS_DATA_URL"]
QLFS_URL: str = CONFIG["QLFS_URL"]
OPEN_METEO_URL: str = CONFIG["OPEN_METEO_URL"]
