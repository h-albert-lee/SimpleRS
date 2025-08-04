# simplers/api/rules/__init__.py
import logging
# 각 규칙 파일에서 규칙 클래스들을 임포트
from .pre_filter_rules import ExcludeSeenItemsRule
from .post_reorder_rules import BoostUserStocksRule, BoostTopReturnStockRule, AddScoreNoiseRule

logger = logging.getLogger(__name__)

# 규칙 인스턴스 생성 (필요시 의존성 주입)
# redis_client = get_redis_client()
# content_repo = get_content_repository()

# 실행 순서대로 리스트 정의
PRE_RANKING_RULES = [
    ExcludeSeenItemsRule(),
    # 다른 Pre-Rank 규칙들...
]

# Post-Rank 규칙 순서 중요: Boosting 후 Noise 추가
POST_RANKING_RULES = [
    BoostUserStocksRule(),
    BoostTopReturnStockRule(),
    AddScoreNoiseRule(), # 노이즈는 보통 마지막 단계에서 추가
    # 다른 Post-Rank 규칙들...
]

logger.info(f"Loaded {len(PRE_RANKING_RULES)} pre-ranking rules and {len(POST_RANKING_RULES)} post-ranking rules.")