# simplers/batch/utils/config_loader.py
import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "configs" / "config.yaml"

def load_config() -> Dict[str, Any]:
    """YAML 설정 파일을 로드합니다."""
    if not CONFIG_PATH.is_file():
        logger.error(f"Batch Config file not found at {CONFIG_PATH}")
        raise FileNotFoundError(f"Batch Config file not found at {CONFIG_PATH}")
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Batch Config file loaded successfully from {CONFIG_PATH}")
            return config if config else {}
    except Exception as e:
        logger.error(f"Error loading batch config file from {CONFIG_PATH}: {e}", exc_info=True)
        raise

config = load_config()

MONGO_CONFIG = config.get("mongodb", {})
OPENSEARCH_CONFIG = config.get("opensearch", {})
ORACLE_CONFIG = config.get("oracledb", {})
# --- 배치 스코어링 설정 로드 ---
BATCH_SCORING_CONFIG = config.get("batch_scoring", {})
# 개별 설정값 로드 (기본값 제공)
SOURCE_WEIGHTS = BATCH_SCORING_CONFIG.get("source_weights", {"global": 0.1, "cluster": 0.1, "local": 0.1})
CF_WEIGHT = BATCH_SCORING_CONFIG.get("cf_weight", 0.0)
CB_WEIGHT = BATCH_SCORING_CONFIG.get("cb_weight", 0.0)
MIN_SCORE_THRESHOLD = BATCH_SCORING_CONFIG.get("min_score_threshold", 0.0)
MAX_CANDIDATES_PER_USER = BATCH_SCORING_CONFIG.get("max_candidates_per_user", 500)
CB_TFIDF_FIELDS = BATCH_SCORING_CONFIG.get("cb_tfidf_fields", ["title"])
CB_USER_HISTORY_LIMIT = BATCH_SCORING_CONFIG.get("cb_user_history_limit", 50)
CF_ITEM_SIMILARITY_METRIC = BATCH_SCORING_CONFIG.get("cf_item_similarity_metric", "jaccard")
CF_USER_HISTORY_LIMIT = BATCH_SCORING_CONFIG.get("cf_user_history_limit", 100)
CF_MIN_CO_OCCURRENCE = BATCH_SCORING_CONFIG.get("cf_min_co_occurrence", 2)


# MongoDB URI 옵션 추가
if 'options' in MONGO_CONFIG and MONGO_CONFIG['options']:
    options_str = "&".join(f"{k}={v}" for k, v in MONGO_CONFIG['options'].items())
    sep = "?" if "?" not in MONGO_CONFIG.get('uri', '') else "&"
    MONGO_CONFIG['uri'] = f"{MONGO_CONFIG.get('uri', '')}{sep}{options_str}"
    logger.info(f"Batch MongoDB URI updated with options: {MONGO_CONFIG['uri']}")