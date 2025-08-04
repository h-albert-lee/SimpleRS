import logging
from typing import List, Dict, Any
from .base import BasePreRankFilterRule
import time

logger = logging.getLogger(__name__)

class ExcludeSeenItemsRule(BasePreRankFilterRule):
    """사용자가 이미 본 콘텐츠를 후보군에서 제외하는 규칙"""
    rule_name = "ExcludeSeenItems"

    async def apply(self, user_context: Dict[str, Any], candidates: List[str]) -> List[str]:
        start_time = time.perf_counter()
        # user_context에서 미리 조회된 '봤던 콘텐츠 ID 목록(Set)'을 가져온다고 가정
        # 실제 구현 시: fetch_user_context_data 에서 OpenSearch 조회 결과를 캐싱하여 전달
        seen_items = user_context.get("seen_items_set", set())
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        if not seen_items:
            logger.debug(f"{log_prefix} No seen items data found. Skipping.")
            return candidates

        original_count = len(candidates)
        # seen_items에 없는 후보만 필터링
        filtered_candidates = [c for c in candidates if c not in seen_items]
        filtered_count = original_count - len(filtered_candidates)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"{log_prefix} Filtered {filtered_count} seen items from {original_count} candidates in {duration_ms:.2f}ms.")
        return filtered_candidates

# 필요시 다른 Pre-Rank 규칙 추가 가능