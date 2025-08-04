# simplers/api/config_loader.py
import yaml
from pathlib import Path
from typing import Dict, Any, Optional # Optional 추가
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "config.yaml"

def load_config() -> Dict[str, Any]:
    """YAML 설정 파일을 로드합니다."""
    if not CONFIG_PATH.is_file():
        logger.error(f"Config file not found at {CONFIG_PATH}")
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Config file loaded successfully from {CONFIG_PATH}")
            return config if config else {}
    except Exception as e:
        logger.error(f"Error loading config file from {CONFIG_PATH}: {e}", exc_info=True)
        raise

config = load_config()

MONGO_CONFIG = config.get("mongodb", {})
OPENSEARCH_CONFIG = config.get("opensearch", {})

# --- API Key 로드 추가 ---
API_SECURITY_CONFIG = config.get("api_security", {})
SECRET_API_KEY: Optional[str] = API_SECURITY_CONFIG.get("api_key") # API 키 로드

if not SECRET_API_KEY:
    logger.warning("API Key ('api_security.api_key') not found in config file. API security might be disabled.")

# (MongoDB URI 옵션 추가 로직은 그대로 유지)
if 'options' in MONGO_CONFIG and MONGO_CONFIG['options']:
    options_str = "&".join(f"{k}={v}" for k, v in MONGO_CONFIG['options'].items())
    sep = "?" if "?" not in MONGO_CONFIG.get('uri', '') else "&"
    MONGO_CONFIG['uri'] = f"{MONGO_CONFIG.get('uri', '')}{sep}{options_str}"
    logger.info(f"MongoDB URI updated with options: {MONGO_CONFIG['uri']}")