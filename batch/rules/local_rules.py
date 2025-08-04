# simplers/batch/rules/local_rules.py
import logging
from typing import List, Dict, Any # 추가
from .base import BaseLocalRule
# 외부 API 호출 함수 임포트 (db_manager에 정의된 것 사용)
from batch.utils.db_manager import call_external_api

# --- 레지스트리 및 데코레이터 정의 (유지) ---
LOCAL_RULE_REGISTRY = {}

def register_local_rule(rule_name):
    def decorator(rule_class):
        LOCAL_RULE_REGISTRY[rule_name] = rule_class()
        return rule_class
    return decorator

logger = logging.getLogger(__name__)

# Local Rule 1: 대주제(btopic)가 '시장' 인 컨텐츠
@register_local_rule("local_market_content")
class LocalMarketContentRule(BaseLocalRule):
    rule_name = "LocalMarketContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('id', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        if not contents_list:
            return []

        try:
            # 'btopic' 필드가 있는 콘텐츠만 필터링
            candidates = [c.get("id") for c in contents_list if c.get("btopic") == "시장"]
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

# Local Rule 2: 컨텐츠의 label이 사용자의 보유종목(owned_stocks)에 있는 컨텐츠
@register_local_rule("local_owned_stock_label")
class LocalOwnedStockLabelRule(BaseLocalRule):
    rule_name = "LocalOwnedStockLabelRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('id', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        # 사용자 정보에서 보유 종목 목록 가져오기 (user 객체에 미리 로드되어 있어야 함)
        owned_stocks = user.get("owned_stocks", []) # user_port 데이터가 user 객체에 병합되었다고 가정

        if not contents_list or not owned_stocks:
            if not owned_stocks: logger.debug(f"[{user_id}] {self.rule_name}: User has no owned stocks.")
            return []

        owned_stocks_set = set(owned_stocks) # 빠른 조회를 위해 Set 사용
        logger.debug(f"[{user_id}] {self.rule_name}: User owned stocks: {owned_stocks_set}")

        try:
            # 콘텐츠의 'label' 필드가 보유 종목 목록에 있는지 확인
            candidates = [c.get("id") for c in contents_list if c.get("label") in owned_stocks_set]
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

# Local Rule 3: 보유종목의 섹터/테마와 동일한 종목의 컨텐츠
@register_local_rule("local_sector_theme_content")
class LocalSectorThemeContentRule(BaseLocalRule):
    rule_name = "LocalSectorThemeContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('id', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        owned_stocks = user.get("owned_stocks", [])
        # 컨텍스트에서 주식 메타데이터 가져오기 (파이프라인에서 미리 로드)
        stock_meta_map = context.get('stock_meta_map', {}) # 예: {'KR123': {'sector': 'IT', ...}}

        if not contents_list or not owned_stocks or not stock_meta_map:
            if not owned_stocks: logger.debug(f"[{user_id}] {self.rule_name}: User has no owned stocks.")
            if not stock_meta_map: logger.debug(f"[{user_id}] {self.rule_name}: Stock metadata not available in context.")
            return []

        user_sectors = set()
        user_themes = set()
        try:
            # 사용자의 보유 종목 섹터/테마 집계
            for stock_code in owned_stocks:
                info = stock_meta_map.get(stock_code)
                if info:
                    if info.get("sector"): user_sectors.add(info.get("sector"))
                    # 테마 필드명 확인 필요 (theme_1, theme_2 등)
                    for theme_key in ["theme_1", "theme_2", "theme_3"]:
                         if info.get(theme_key): user_themes.add(info.get(theme_key))

            if not user_sectors and not user_themes:
                logger.debug(f"[{user_id}] {self.rule_name}: Could not determine sectors/themes for owned stocks.")
                return []

            logger.debug(f"[{user_id}] {self.rule_name}: User sectors: {user_sectors}, themes: {user_themes}")

            candidate_ids = []
            # 전체 콘텐츠의 종목(label)에 대해 섹터/테마 비교
            for c in contents_list:
                content_stock_code = c.get("label")
                if not content_stock_code: continue # 콘텐츠에 종목 코드가 없으면 스킵

                content_stock_info = stock_meta_map.get(content_stock_code)
                if content_stock_info:
                    match = False
                    if content_stock_info.get("sector") in user_sectors:
                        match = True
                    else:
                        # 테마 매칭 확인
                        for theme_key in ["theme_1", "theme_2", "theme_3"]:
                            if content_stock_info.get(theme_key) in user_themes:
                                match = True
                                break
                    if match:
                        candidate_ids.append(c.get("id"))

            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidate_ids)} candidates.")
            return candidate_ids
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

    # 주식 정보 조회 로직은 파이프라인 시작 시 한 번 수행하여 context에 넣는 것이 효율적
    # def get_stock_info(self, stock_code, context):
    #     # 예: context 내의 os_client나 캐시에서 조회
    #     pass

# Local Rule 4: 보유종목의 연관 종목 API 통해 관련 컨텐츠 도출
@register_local_rule("local_related_content")
class LocalRelatedContentRule(BaseLocalRule):
    rule_name = "LocalRelatedContentRule"
    # 외부 API 정보 (설정 파일에서 관리하는 것이 더 좋음)
    RELATED_STOCK_API_URL = "http://example.com/api/related_stocks"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('id', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        owned_stocks = user.get("owned_stocks", [])

        if not contents_list or not owned_stocks:
             if not owned_stocks: logger.debug(f"[{user_id}] {self.rule_name}: User has no owned stocks.")
             return []

        related_stocks_set = set()
        try:
            # 각 보유 종목에 대해 연관 종목 API 호출
            # !!! 중요: 사용자마다 API를 호출하면 부하가 크므로, 캐싱 또는 다른 방식 고려 필요 !!!
            for stock_code in owned_stocks:
                # 캐시 확인 (예시)
                cached_related = context.get('related_stock_cache', {}).get(stock_code)
                if cached_related:
                    logger.debug(f"[{user_id}] {self.rule_name}: Found cached related stocks for {stock_code}")
                    related_stocks_set.update(cached_related)
                    continue

                # API 호출 (db_manager의 call_external_api 사용)
                logger.debug(f"[{user_id}] {self.rule_name}: Calling related stock API for {stock_code}")
                api_result = call_external_api(self.RELATED_STOCK_API_URL, params={'code': stock_code})

                if api_result and isinstance(api_result.get('related_codes'), list):
                    related = api_result['related_codes']
                    logger.debug(f"[{user_id}] {self.rule_name}: API returned {len(related)} related stocks for {stock_code}")
                    related_stocks_set.update(related)
                    # 캐시에 저장 (예시)
                    if 'related_stock_cache' in context:
                        context['related_stock_cache'][stock_code] = related
                else:
                    logger.warning(f"[{user_id}] {self.rule_name}: Failed to get related stocks for {stock_code} from API.")

            if not related_stocks_set:
                logger.debug(f"[{user_id}] {self.rule_name}: No related stocks found.")
                return []

            logger.debug(f"[{user_id}] {self.rule_name}: Total related stocks found: {related_stocks_set}")

            # 연관 종목(label)을 가진 콘텐츠 필터링
            candidates = [c.get("id") for c in contents_list if c.get("label") in related_stocks_set]
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []


# Local Rule 5: 온보딩 과정에서 선택한 관심사(conc)에 해당하는 컨텐츠
@register_local_rule("local_onboarding_interest")
class LocalOnboardingInterestRule(BaseLocalRule):
    rule_name = "LocalOnboardingInterestRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('id', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        # 사용자 정보에서 온보딩 관심사 목록(conc) 가져오기
        user_interests = user.get("conc", []) # user 스키마의 'conc' 필드 사용

        if not contents_list or not user_interests:
            if not user_interests: logger.debug(f"[{user_id}] {self.rule_name}: User has no onboarding interests (conc).")
            return []

        # 관심사 이름(cat_nm)만 추출하여 Set으로 만듦
        interest_names = {item.get("cat_nm") for item in user_interests if item.get("cat_nm")}
        logger.debug(f"[{user_id}] {self.rule_name}: User onboarding interests: {interest_names}")

        if not interest_names:
            return []

        try:
            # 콘텐츠의 label 또는 btopic이 관심사 이름 목록에 있는지 확인
            candidates = [
                c.get("id") for c in contents_list
                if c.get("label") in interest_names or c.get("btopic") in interest_names
            ]
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []