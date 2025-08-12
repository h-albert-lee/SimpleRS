import logging
import time
from typing import Dict, Any, List

from .base import BasePreRankFilterRule


logger = logging.getLogger(__name__)


class ExcludeSeenItemsRule(BasePreRankFilterRule):
    """사용자가 이미 본 콘텐츠를 후보군에서 제외하는 규칙"""

    rule_name = "ExcludeSeenItems"

    async def apply(
        self, user_context: Dict[str, Any], candidates: List[str]
    ) -> List[str]:
        start_time = time.perf_counter()

        seen_items = user_context.get("seen_items_set", set())
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        if not seen_items:
            logger.debug(f"{log_prefix} No seen items data found. Skipping.")
            return candidates

        original_count = len(candidates)
        filtered_candidates = [c for c in candidates if c not in seen_items]
        filtered_count = original_count - len(filtered_candidates)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"{log_prefix} Filtered {filtered_count} seen items from {original_count} candidates in {duration_ms:.2f}ms."
        )
        return filtered_candidates


# 필요 시 다른 Pre-Rank 규칙을 이 파일에 추가할 수 있습니다.

