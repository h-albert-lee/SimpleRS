# simplers/batch/rules/local_rules.py
import logging
from typing import List, Dict, Any
from .base import BaseLocalRule
from batch.utils.data_loader import fetch_user_portfolio

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
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        if not contents_list:
            return []

        try:
            # 'btopic' 필드가 '시장'인 콘텐츠만 필터링
            candidates = [c.get("_id") or c.get("id") for c in contents_list if c.get("btopic") == "시장"]
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

# Local Rule 2: 사용자가 실제 보유한 종목에 대한 콘텐츠
@register_local_rule("local_owned_stock_content")
class LocalOwnedStockContentRule(BaseLocalRule):
    rule_name = "LocalOwnedStockContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        
        # 사용자 포트폴리오 정보 조회
        try:
            portfolio_data = fetch_user_portfolio(user_id)
            if not portfolio_data or not portfolio_data.get('portfolio_info'):
                logger.debug(f"[{user_id}] {self.rule_name}: No portfolio data available.")
                return []
            
            # 보유 종목 코드 추출 (gic_code에서 종목 코드 부분만 추출)
            owned_stock_codes = set()
            for item in portfolio_data['portfolio_info']:
                if item.get('kor_name') and item.get('kor_name') != '기타':
                    # 종목명을 기반으로 매칭하거나, 별도 매핑 테이블 필요
                    # 여기서는 간단히 종목명으로 매칭한다고 가정
                    owned_stock_codes.add(item.get('kor_name'))
            
            if not owned_stock_codes:
                logger.debug(f"[{user_id}] {self.rule_name}: No owned stocks found.")
                return []
                
            logger.debug(f"[{user_id}] {self.rule_name}: User owned stocks: {owned_stock_codes}")

            # 콘텐츠의 'stk_name' 또는 'label' 필드가 보유 종목에 있는지 확인
            candidates = []
            for c in contents_list:
                if (c.get("stk_name") in owned_stock_codes or 
                    c.get("label") in owned_stock_codes):
                    candidates.append(c.get("_id") or c.get("id"))
                    
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

# Local Rule 3: 보유종목의 섹터에 대한 컨텐츠
@register_local_rule("local_sector_content")
class LocalSectorContentRule(BaseLocalRule):
    rule_name = "LocalSectorContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        contents_list = context.get('contents_list', [])
        
        # 사용자 포트폴리오 정보 조회
        try:
            portfolio_data = fetch_user_portfolio(user_id)
            if not portfolio_data or not portfolio_data.get('sector_weight'):
                logger.debug(f"[{user_id}] {self.rule_name}: No sector weight data available.")
                return []
            
            # 사용자가 보유한 섹터 정보 추출
            user_sectors = set(portfolio_data['sector_weight'].keys())
            if not user_sectors:
                logger.debug(f"[{user_id}] {self.rule_name}: No sectors found in portfolio.")
                return []
                
            logger.debug(f"[{user_id}] {self.rule_name}: User sectors: {user_sectors}")

            # 콘텐츠의 btopic이나 stopic이 사용자 섹터와 매칭되는 컨텐츠 찾기
            candidates = []
            for c in contents_list:
                if (c.get("btopic") in user_sectors or 
                    c.get("stopic") in user_sectors):
                    candidates.append(c.get("_id") or c.get("id"))
                    
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} candidates.")
            return candidates
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Error: {e}", exc_info=True)
            return []

