# simplers/batch/utils/config_loader.py
import logging
from typing import Dict, Any

from common.config import config, MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG

logger = logging.getLogger(__name__)

# Batch scoring configuration
BATCH_SCORING_CONFIG = config.get("batch_scoring", {})
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
