# simplers/batch/rules/global_rules.py
import logging
from typing import List, Dict, Any # 추가
from datetime import datetime # 추가 (OpenSearch 인덱스 이름용)
from .base import BaseGlobalRule

# --- 레지스트리 및 데코레이터 정의 (유지) ---
GLOBAL_RULE_REGISTRY = {}

def register_global_rule(rule_name):
    def decorator(rule_class):
        # 클래스 인스턴스가 아닌 클래스 자체를 저장할 수도 있음 (선택)
        GLOBAL_RULE_REGISTRY[rule_name] = rule_class() # 기존 방식 유지 (인스턴스 저장)
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
        stock_data = context.get('latest_stock_data') # 컨텍스트에서 미리 로드된 데이터 확인

        if not stock_data:
            # 만약 컨텍스트에 없다면, OS 클라이언트를 이용해 직접 조회 시도 (비효율적일 수 있음)
            os_client = context.get('os_client')
            if os_client:
                logger.warning(f"{self.rule_name}: 'latest_stock_data' not in context. Fetching directly (might be inefficient).")
                stock_data = self._fetch_latest_stock_data(os_client)
                # 필요시 조회된 데이터를 context에 캐싱할 수도 있음: context['latest_stock_data'] = stock_data
            else:
                logger.error(f"{self.rule_name}: 'latest_stock_data' not in context and 'os_client' is unavailable.")
                return []

        if not stock_data:
             logger.warning(f"{self.rule_name}: Stock data is empty.")
             return []

        try:
            # 한국/미국 필터
            filtered_stocks = [s for s in stock_data if s.get("country") in ["Korea", "USA"]]
            # 1d_return 필드가 없는 경우 0으로 처리하여 정렬 오류 방지
            sorted_stocks = sorted(filtered_stocks, key=lambda s: float(s.get("1d_return", 0) or 0), reverse=True)
            top_stocks = sorted_stocks[:10]
            # OpenSearch screen 인덱스의 종목 코드 필드명 확인 필요 (shrt_code 또는 gic_code 등)
            top_stock_codes = {s.get("shrt_code") for s in top_stocks if s.get("shrt_code")} # Set으로 변경
            logger.debug(f"{self.rule_name}: Top 10 stock codes by 1d_return: {top_stock_codes}")

            # 콘텐츠 중 label(큐레이션 스키마의 주식 코드 필드)이 top_stock_codes에 해당하는 컨텐츠 선택
            candidate_ids = [c.get("id") for c in contents_list if c.get("label") in top_stock_codes]
            logger.info(f"{self.rule_name}: Found {len(candidate_ids)} candidates.")
            return candidate_ids
        except Exception as e:
            logger.error(f"{self.rule_name}: Error during processing: {e}", exc_info=True)
            return []

    def _fetch_latest_stock_data(self, os_client) -> List[Dict[str, Any]]:
        """OpenSearch에서 최신 주식 데이터를 조회하는 내부 메서드 (예시)"""
        # !!! 중요: 이 부분은 실제 OpenSearch 쿼리로 구현되어야 함 !!!
        index_name = f"screen-{datetime.now().strftime('%Y%m%d')}" # 오늘 날짜 인덱스 (패턴 확인 필요)
        logger.debug(f"Fetching data from OpenSearch index: {index_name}")
        try:
            # 예시 쿼리 (상승률 상위 조회 - 실제 구현 필요)
            response = os_client.search(
                index=index_name,
                size=100, # 충분한 수의 데이터 조회
                _source=["shrt_code", "country", "1d_return"], # 필요한 필드만
                body={
                    "query": {"match_all": {}},
                    "sort": [{"1d_return": {"order": "desc", "missing": "_last"}}] # 예시 정렬
                },
                ignore=[404] # 인덱스 없을 경우 무시
            )
            return response.get('hits', {}).get('hits', [])
        except Exception as e:
            logger.error(f"Error fetching latest stock data from OpenSearch (index: {index_name}): {e}", exc_info=True)
            return []


# Rule 2: 좋아요(like_cnt)가 많은 top10 컨텐츠
@register_global_rule("global_top_like_content")
class GlobalTopLikeContentRule(BaseGlobalRule):
    rule_name = "GlobalTopLikeContentRule"

    def apply(self, context: Dict[str, Any]) -> List[str]:
        logger.debug(f"Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        if not contents_list:
            return []

        try:
            # like_cnt 필드가 없는 경우 0으로 처리
            sorted_contents = sorted(contents_list, key=lambda c: int(c.get("like_cnt", 0) or 0), reverse=True)
            top_contents = sorted_contents[:10]
            candidate_ids = [c.get("id") for c in top_contents]
            logger.info(f"{self.rule_name}: Found {len(candidate_ids)} candidates.")
            return candidate_ids
        except Exception as e:
            logger.error(f"{self.rule_name}: Error during processing: {e}", exc_info=True)
            return []