# simplers/batch/rules/global_rules.py
import logging
from typing import List, Dict, Any
from .base import BaseGlobalRule
from batch.utils.data_loader import fetch_latest_stock_data, APIConnectionError, DataValidationError
from batch.utils.config_loader import (
    GLOBAL_STOCK_TOP_RETURN_CONFIG,
    GLOBAL_TOP_LIKED_CONTENT_CONFIG,
)

# --- 레지스트리 및 데코레이터 정의 (유지) ---
GLOBAL_RULE_REGISTRY = {}

def register_global_rule(rule_name):
    def decorator(rule_class):
        GLOBAL_RULE_REGISTRY[rule_name] = rule_class()
        return rule_class
    return decorator

logger = logging.getLogger(__name__)

class GlobalRuleError(Exception):
    """글로벌 룰 관련 예외"""
    pass

# Rule 1: 실시간 시세 상승률 top10 (한국/미국 주식) 기반 컨텐츠 후보
@register_global_rule("global_stock_top_return")
class GlobalStockTopReturnRule(BaseGlobalRule):
    rule_name = "GlobalStockTopReturnRule"

    def apply(self, context: Dict[str, Any]) -> List[str]:
        """
        실시간 시세 상승률 top 10 종목의 컨텐츠를 반환합니다.
        
        Args:
            context: 실행 컨텍스트
            
        Returns:
            후보 컨텐츠 ID 리스트
            
        Raises:
            GlobalRuleError: 룰 실행 중 치명적 오류
        """
        logger.debug(f"Applying rule: {self.rule_name}")

        # 설정값 로딩
        params = GLOBAL_STOCK_TOP_RETURN_CONFIG
        top_n = params.get("top_n", 10)
        allowed_countries = params.get("allowed_countries", ["Korea", "USA"])
        days_back = params.get("days_back", 3)
        max_abs_return = params.get("max_abs_return", 50)

        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"{self.rule_name}: No contents available in context")
            return []

        os_client = context.get('os_client')
        if not os_client:
            logger.warning(f"{self.rule_name}: OpenSearch client not available in context")
            return []

        try:
            # 최신 주식 데이터 조회
            logger.debug(f"{self.rule_name}: Fetching latest stock data...")
            stock_data = fetch_latest_stock_data(os_client, days_back=days_back)
            
            if not stock_data:
                logger.warning(f"{self.rule_name}: No stock data available from OpenSearch")
                return []

            # 데이터 검증 및 필터링
            valid_stocks = []
            for stock in stock_data:
                if not isinstance(stock, dict):
                    continue
                    
                country = stock.get("country")
                returns = stock.get("1d_returns")
                code = stock.get("shrt_code")

                if country not in allowed_countries:
                    continue

                if returns is None or code is None:
                    continue
                    
                try:
                    returns_float = float(returns)
                    if abs(returns_float) > max_abs_return:  # 비현실적인 수익률 제외
                        continue
                    stock['1d_returns_float'] = returns_float
                    valid_stocks.append(stock)
                except (ValueError, TypeError):
                    continue
            
            if not valid_stocks:
                logger.warning(f"{self.rule_name}: No valid stock data after filtering")
                return []

            # 상승률 기준 정렬 및 상위 종목 선택
            sorted_stocks = sorted(valid_stocks, key=lambda s: s['1d_returns_float'], reverse=True)
            top_stocks = sorted_stocks[:top_n]

            top_stock_codes = {s.get("shrt_code") for s in top_stocks if s.get("shrt_code")}
            logger.info(
                f"{self.rule_name}: Top {top_n} stock codes by 1d_returns: {list(top_stock_codes)}"
            )

            # 콘텐츠 매칭
            candidate_ids = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_label = content.get("label")
                content_id = content.get("_id") or content.get("id")
                
                if content_label in top_stock_codes and content_id:
                    candidate_ids.append(str(content_id))
            
            logger.info(f"{self.rule_name}: Found {len(candidate_ids)} matching candidates")
            return candidate_ids
            
        except (APIConnectionError, DataValidationError) as e:
            logger.warning(f"{self.rule_name}: External API error: {e}")
            return []
            
        except Exception as e:
            logger.error(f"{self.rule_name}: Unexpected error during processing: {e}", exc_info=True)
            return []


# Rule 2: liked_users가 많은 컨텐츠 (기타 pool)
@register_global_rule("global_top_liked_content")
class GlobalTopLikedContentRule(BaseGlobalRule):
    rule_name = "GlobalTopLikedContentRule"

    def apply(self, context: Dict[str, Any], top_n: int = None) -> List[str]:
        """
        liked_users가 많은 컨텐츠를 반환합니다.

        Args:
            context: 실행 컨텍스트
            top_n: 상위 몇 개까지 선택할지

        Returns:
            후보 컨텐츠 ID 리스트

        Raises:
            GlobalRuleError: 룰 실행 중 치명적 오류
        """
        logger.debug(f"Applying rule: {self.rule_name}")

        params = GLOBAL_TOP_LIKED_CONTENT_CONFIG
        default_top_n = params.get("default_top_n", 50)
        max_top_n = params.get("max_top_n", 1000)

        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"{self.rule_name}: No contents available in context")
            return []

        if top_n is None:
            top_n = default_top_n

        if top_n <= 0 or top_n > max_top_n:
            logger.warning(
                f"{self.rule_name}: Invalid top_n value: {top_n}, using default {default_top_n}"
            )
            top_n = default_top_n

        try:
            # 유효한 컨텐츠만 필터링
            valid_contents = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_id = content.get("_id") or content.get("id")
                if not content_id:
                    continue
                    
                liked_users = content.get("liked_users", [])
                if not isinstance(liked_users, list):
                    liked_users = []
                
                content['liked_count'] = len(liked_users)
                valid_contents.append(content)
            
            if not valid_contents:
                logger.warning(f"{self.rule_name}: No valid contents found")
                return []
            
            # liked_users 수로 정렬
            sorted_contents = sorted(
                valid_contents, 
                key=lambda c: c['liked_count'], 
                reverse=True
            )
            
            top_contents = sorted_contents[:top_n]
            candidate_ids = [str(c.get("_id") or c.get("id")) for c in top_contents]
            
            # 통계 로깅
            if top_contents:
                max_likes = top_contents[0]['liked_count']
                min_likes = top_contents[-1]['liked_count']
                avg_likes = sum(c['liked_count'] for c in top_contents) / len(top_contents)
                logger.info(f"{self.rule_name}: Selected {len(candidate_ids)} candidates "
                          f"(likes: max={max_likes}, min={min_likes}, avg={avg_likes:.1f})")
            
            return candidate_ids
            
        except Exception as e:
            logger.error(f"{self.rule_name}: Unexpected error during processing: {e}", exc_info=True)
            return []
