# simplers/batch/rules/global_rules.py
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .base import BaseGlobalRule
from batch.utils.data_loader import fetch_latest_stock_data

# --- 레지스트리 및 데코레이터 정의 (유지) ---
GLOBAL_RULE_REGISTRY = {}

def register_global_rule(rule_name):
    def decorator(rule_class):
        GLOBAL_RULE_REGISTRY[rule_name] = rule_class()
        return rule_class
    return decorator

logger = logging.getLogger(__name__)

# Rule 1: 실시간 시세 상승률 top10 (한국/미국 주식) 기반 컨텐츠 후보
@register_global_rule("global_stock_top_return")
class GlobalStockTopReturnRule(BaseGlobalRule):
    rule_name = "GlobalStockTopReturnRule"

    def apply(self, context: Dict[str, Any]) -> List[str]:
        logger.debug(f"Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        
        # OpenSearch에서 최신 주식 데이터 조회
        os_client = context.get('os_client')
        if not os_client:
            logger.error(f"{self.rule_name}: OpenSearch client not available in context.")
            return []

        try:
            # 최신 주식 데이터 조회
            stock_data = fetch_latest_stock_data(os_client, days_back=3)
            
            if not stock_data:
                logger.warning(f"{self.rule_name}: No stock data available.")
                return []

            # 한국/미국 필터 및 상승률 기준 정렬
            filtered_stocks = [s for s in stock_data if s.get("country") in ["Korea", "USA"]]
            sorted_stocks = sorted(filtered_stocks, key=lambda s: float(s.get("1d_returns", 0) or 0), reverse=True)
            top_stocks = sorted_stocks[:10]
            
            top_stock_codes = {s.get("shrt_code") for s in top_stocks if s.get("shrt_code")}
            logger.info(f"{self.rule_name}: Top 10 stock codes by 1d_returns: {list(top_stock_codes)}")

            # 콘텐츠 중 label이 top_stock_codes에 해당하는 컨텐츠 선택
            candidate_ids = [c.get("_id") or c.get("id") for c in contents_list if c.get("label") in top_stock_codes]
            logger.info(f"{self.rule_name}: Found {len(candidate_ids)} candidates.")
            return candidate_ids
            
        except Exception as e:
            logger.error(f"{self.rule_name}: Error during processing: {e}", exc_info=True)
            return []


# Rule 2: liked_users가 많은 컨텐츠 (기타 pool)
@register_global_rule("global_top_liked_content")
class GlobalTopLikedContentRule(BaseGlobalRule):
    rule_name = "GlobalTopLikedContentRule"

    def apply(self, context: Dict[str, Any]) -> List[str]:
        logger.debug(f"Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        if not contents_list:
            return []

        try:
            # liked_users 배열의 길이로 정렬
            sorted_contents = sorted(
                contents_list, 
                key=lambda c: len(c.get("liked_users", [])), 
                reverse=True
            )
            top_contents = sorted_contents[:50]  # 상위 50개 선택
            candidate_ids = [c.get("_id") or c.get("id") for c in top_contents]
            logger.info(f"{self.rule_name}: Found {len(candidate_ids)} candidates.")
            return candidate_ids
        except Exception as e:
            logger.error(f"{self.rule_name}: Error during processing: {e}", exc_info=True)
            return []