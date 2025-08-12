# simplers/api/config_loader.py
import logging
from typing import Optional

from common.config import config, MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG

logger = logging.getLogger(__name__)

API_SECURITY_CONFIG = config.get("api_security", {})
SECRET_API_KEY: Optional[str] = API_SECURITY_CONFIG.get("api_key")

if not SECRET_API_KEY:
    logger.warning("API Key ('api_security.api_key') not found in config file. API security might be disabled.")
