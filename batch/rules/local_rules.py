# simplers/batch/rules/local_rules.py
import logging
from typing import List, Dict, Any
from .base import BaseLocalRule
from batch.utils.data_loader import fetch_user_portfolio, APIConnectionError, DataValidationError

# --- 레지스트리 및 데코레이터 정의 (유지) ---
LOCAL_RULE_REGISTRY = {}

def register_local_rule(rule_name):
    def decorator(rule_class):
        LOCAL_RULE_REGISTRY[rule_name] = rule_class()
        return rule_class
    return decorator

logger = logging.getLogger(__name__)

class LocalRuleError(Exception):
    """로컬 룰 관련 예외"""
    pass

# Local Rule 1: 대주제(btopic)가 '시장' 인 컨텐츠
@register_local_rule("local_market_content")
class LocalMarketContentRule(BaseLocalRule):
    rule_name = "LocalMarketContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        btopic이 '시장'인 컨텐츠를 반환합니다.
        
        Args:
            user: 사용자 정보
            context: 실행 컨텍스트
            
        Returns:
            후보 컨텐츠 ID 리스트
        """
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        
        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"[{user_id}] {self.rule_name}: No contents available in context")
            return []

        try:
            # 유효한 컨텐츠만 필터링
            candidates = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                btopic = content.get("btopic")
                content_id = content.get("_id") or content.get("id")
                
                if btopic == "시장" and content_id:
                    candidates.append(str(content_id))
            
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} market-related candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Unexpected error: {e}", exc_info=True)
            return []

# Local Rule 2: 사용자가 실제 보유한 종목에 대한 콘텐츠
@register_local_rule("local_owned_stock_content")
class LocalOwnedStockContentRule(BaseLocalRule):
    rule_name = "LocalOwnedStockContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        사용자가 실제 보유한 종목에 대한 컨텐츠를 반환합니다.
        
        Args:
            user: 사용자 정보
            context: 실행 컨텍스트
            
        Returns:
            후보 컨텐츠 ID 리스트
        """
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        
        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"[{user_id}] {self.rule_name}: No contents available in context")
            return []
        
        if not user_id or user_id == 'UNKNOWN':
            logger.warning(f"{self.rule_name}: Invalid user ID")
            return []
        
        try:
            # 사용자 포트폴리오 정보 조회 (컨텍스트에 캐시된 데이터 우선 사용)
            portfolio_data = context.get('portfolio_data')
            if portfolio_data is None:
                logger.debug(f"[{user_id}] {self.rule_name}: Fetching user portfolio...")
                portfolio_data = fetch_user_portfolio(user_id)

            if not portfolio_data:
                logger.debug(f"[{user_id}] {self.rule_name}: No portfolio data available")
                return []
            
            # 포트폴리오 데이터 검증
            portfolio_info = portfolio_data.get('portfolio_info', [])
            if not isinstance(portfolio_info, list):
                logger.warning(f"[{user_id}] {self.rule_name}: Invalid portfolio_info format")
                return []
            
            # 보유 종목 코드 추출
            owned_stock_codes = set()
            owned_stock_names = set()
            
            for item in portfolio_info:
                if not isinstance(item, dict):
                    continue
                    
                kor_name = item.get('kor_name')
                gic_code = item.get('gic_code')
                
                if kor_name and kor_name != '기타':
                    owned_stock_names.add(kor_name)
                    
                if gic_code:
                    owned_stock_codes.add(str(gic_code))
            
            if not owned_stock_codes and not owned_stock_names:
                logger.debug(f"[{user_id}] {self.rule_name}: No valid owned stocks found")
                return []
                
            logger.debug(f"[{user_id}] {self.rule_name}: Found {len(owned_stock_codes)} stock codes, "
                        f"{len(owned_stock_names)} stock names")

            # 콘텐츠 매칭
            candidates = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_id = content.get("_id") or content.get("id")
                if not content_id:
                    continue
                    
                # 여러 필드로 매칭 시도
                stk_name = content.get("stk_name")
                label = content.get("label")

                if stk_name == '기타' or label == '기타':
                    continue

                matched = False
                if label in owned_stock_codes:
                    matched = True
                elif stk_name in owned_stock_names or label in owned_stock_names:
                    matched = True

                if matched:
                    candidates.append(str(content_id))
                    
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} owned stock candidates")
            return candidates
            
        except (APIConnectionError, DataValidationError) as e:
            logger.warning(f"[{user_id}] {self.rule_name}: External API error: {e}")
            return []
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Unexpected error: {e}", exc_info=True)
            return []

# Local Rule 3: 보유종목의 섹터에 대한 컨텐츠
@register_local_rule("local_sector_content")
class LocalSectorContentRule(BaseLocalRule):
    rule_name = "LocalSectorContentRule"

    def apply(self, user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        사용자가 보유한 종목의 섹터에 대한 컨텐츠를 반환합니다.
        
        Args:
            user: 사용자 정보
            context: 실행 컨텍스트
            
        Returns:
            후보 컨텐츠 ID 리스트
        """
        user_id = user.get('cust_no', 'UNKNOWN')
        logger.debug(f"[{user_id}] Applying rule: {self.rule_name}")
        
        # 입력 검증
        contents_list = context.get('contents_list', [])
        if not contents_list:
            logger.warning(f"[{user_id}] {self.rule_name}: No contents available in context")
            return []
        
        if not user_id or user_id == 'UNKNOWN':
            logger.warning(f"{self.rule_name}: Invalid user ID")
            return []
        
        try:
            # 사용자 포트폴리오 정보 조회 (컨텍스트에 캐시된 데이터 우선 사용)
            portfolio_data = context.get('portfolio_data')
            if portfolio_data is None:
                logger.debug(f"[{user_id}] {self.rule_name}: Fetching user portfolio for sector analysis...")
                portfolio_data = fetch_user_portfolio(user_id)

            if not portfolio_data:
                logger.debug(f"[{user_id}] {self.rule_name}: No portfolio data available")
                return []
            
            # 섹터 정보 추출
            user_sectors = set()
            
            # sector_weight에서 섹터 정보 추출
            sector_weight = portfolio_data.get('sector_weight', {})
            if isinstance(sector_weight, dict):
                user_sectors.update(sector_weight.keys())
            
            # portfolio_info에서도 섹터 정보 추출 (있다면)
            portfolio_info = portfolio_data.get('portfolio_info', [])
            if isinstance(portfolio_info, list):
                for item in portfolio_info:
                    if isinstance(item, dict):
                        sector = item.get('sector') or item.get('gics_sector')
                        if sector:
                            user_sectors.add(sector)
            
            if not user_sectors:
                logger.debug(f"[{user_id}] {self.rule_name}: No sectors found in portfolio")
                return []
                
            logger.debug(f"[{user_id}] {self.rule_name}: User sectors: {list(user_sectors)}")

            # 콘텐츠 매칭
            candidates = []
            for content in contents_list:
                if not isinstance(content, dict):
                    continue
                    
                content_id = content.get("_id") or content.get("id")
                if not content_id:
                    continue
                    
                # 여러 필드로 섹터 매칭 시도
                btopic = content.get("btopic")
                stopic = content.get("stopic")
                sector = content.get("sector")
                
                matched = False
                if btopic in user_sectors:
                    matched = True
                elif stopic in user_sectors:
                    matched = True
                elif sector in user_sectors:
                    matched = True
                    
                if matched:
                    candidates.append(str(content_id))
                    
            logger.info(f"[{user_id}] {self.rule_name}: Found {len(candidates)} sector-related candidates")
            return candidates
            
        except (APIConnectionError, DataValidationError) as e:
            logger.warning(f"[{user_id}] {self.rule_name}: External API error: {e}")
            return []
            
        except Exception as e:
            logger.error(f"[{user_id}] {self.rule_name}: Unexpected error: {e}", exc_info=True)
            return []

