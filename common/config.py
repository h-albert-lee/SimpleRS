import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "config.yaml"


def load_config() -> Dict[str, Any]:
    """Load YAML configuration file."""
    if not CONFIG_PATH.is_file():
        logger.error(f"Config file not found at {CONFIG_PATH}")
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}
            logger.info(f"Config file loaded successfully from {CONFIG_PATH}")
            return config
    except Exception as e:
        logger.error(f"Error loading config file from {CONFIG_PATH}: {e}", exc_info=True)
        raise


config = load_config()

MONGO_CONFIG = config.get("mongodb", {})
OPENSEARCH_CONFIG = config.get("opensearch", {})
ORACLE_CONFIG = config.get("oracledb", {})

# Apply MongoDB URI options if present
if MONGO_CONFIG.get("options"):
    options_str = "&".join(f"{k}={v}" for k, v in MONGO_CONFIG["options"].items())
    sep = "?" if "?" not in MONGO_CONFIG.get("uri", "") else "&"
    MONGO_CONFIG["uri"] = f"{MONGO_CONFIG.get('uri', '')}{sep}{options_str}"
    logger.info(f"MongoDB URI updated with options: {MONGO_CONFIG['uri']}")
