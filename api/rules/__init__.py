import logging

from .pre_filter_rules import ExcludeSeenItemsRule
from .post_reorder_rules import (
    MarketCapRecencyRandomRule,
    BoostUserStocksRule,
    BoostTopReturnStockRule,
    AddScoreNoiseRule,
)


logger = logging.getLogger(__name__)


PRE_RANKING_RULES = [
    ExcludeSeenItemsRule(),
]


POST_RANKING_RULES = [
    MarketCapRecencyRandomRule(),
    BoostUserStocksRule(),
    BoostTopReturnStockRule(),
    AddScoreNoiseRule(),
]


logger.info(
    "Loaded %d pre-ranking rules and %d post-ranking rules.",
    len(PRE_RANKING_RULES),
    len(POST_RANKING_RULES),
)

