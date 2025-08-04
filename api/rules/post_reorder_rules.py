import logging
import random
import time
from typing import List, Dict, Any, Tuple
from .base import BasePostRankReorderRule

logger = logging.getLogger(__name__)

class BoostUserStocksRule(BasePostRankReorderRule):
    """사용자 관련 주식(보유, 최근 본, 관심, 온보딩) 콘텐츠의 점수를 상승시키는 규칙"""
    rule_name = "BoostUserStocks"

    # 가중치 설정 (조정 가능)
    WEIGHTS = {
        "owned": 1.5,
        "recent": 1.3,
        "group1": 1.2,
        "onboarding": 1.1,
    }

    async def apply(self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        # user_context에서 주식 목록 및 콘텐츠 메타데이터 가져오기 (데이터 로딩 가정)
        owned_stocks = user_context.get("owned_stocks_set", set())
        recent_stocks = user_context.get("recent_stocks_set", set())
        group1_stocks = user_context.get("group1_stocks_set", set())
        onboarding_stocks = user_context.get("onboarding_stocks_set", set())
        content_meta = user_context.get("content_meta", {}) # {'item_id': {'label': 'shrt_code', ...}}

        if not any([owned_stocks, recent_stocks, group1_stocks, onboarding_stocks]):
            logger.debug(f"{log_prefix} No user stock lists found. Skipping.")
            return ranked_items

        boosted_count = 0
        new_ranked_items = []
        for item_id, score in ranked_items:
            stock_code = content_meta.get(item_id, {}).get("label") # 콘텐츠의 주식 코드
            if not stock_code:
                new_ranked_items.append((item_id, score))
                continue

            boost = 1.0
            boost_type = None
            # 가중치 적용 (중복 적용 가능, 필요시 로직 수정)
            if stock_code in owned_stocks:
                boost = max(boost, self.WEIGHTS["owned"])
                boost_type = "owned"
            if stock_code in recent_stocks:
                boost = max(boost, self.WEIGHTS["recent"])
                boost_type = boost_type or "recent"
            if stock_code in group1_stocks:
                boost = max(boost, self.WEIGHTS["group1"])
                boost_type = boost_type or "group1"
            if stock_code in onboarding_stocks:
                boost = max(boost, self.WEIGHTS["onboarding"])
                boost_type = boost_type or "onboarding"

            if boost > 1.0:
                boosted_count += 1
                new_score = score * boost
                logger.debug(f"{log_prefix} Boosting item {item_id} (stock: {stock_code}, type: {boost_type}) score from {score:.4f} to {new_score:.4f} (boost: {boost:.2f})")
                new_ranked_items.append((item_id, new_score))
            else:
                new_ranked_items.append((item_id, score))

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"{log_prefix} Boosted scores for {boosted_count} items in {duration_ms:.2f}ms.")
        # 점수 기준으로 다시 정렬
        new_ranked_items.sort(key=lambda x: x[1], reverse=True)
        return new_ranked_items


class BoostTopReturnStockRule(BasePostRankReorderRule):
    """보유 종목 중 기간 수익률 상위 종목 콘텐츠 점수 상승"""
    rule_name = "BoostTopReturnStock"
    BOOST_FACTOR = 2.0 # 상위 종목 가중치 (조정 가능)

    async def apply(self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        # user_context에서 보유 주식 목록 및 수익률 정보 가져오기 (데이터 로딩 가정)
        owned_stocks = user_context.get("owned_stocks_set", set())
        # stock_returns = {'shrt_code': {'1m_returns': 0.1, '1d_returns': 0.01}, ...}
        stock_returns = user_context.get("owned_stock_returns", {})
        content_meta = user_context.get("content_meta", {})

        if not owned_stocks or not stock_returns:
            logger.debug(f"{log_prefix} Owned stocks or return data not found. Skipping.")
            return ranked_items

        # 수익률 가장 높은 보유 종목 찾기 (여기서는 1개월 기준, 없으면 1일 기준)
        top_stock = None
        max_return = -float('inf')

        for stock_code in owned_stocks:
            returns = stock_returns.get(stock_code)
            if returns:
                # 1m_returns 우선, 없거나 None이면 1d_returns 사용
                current_return = returns.get('1m_returns')
                if current_return is None: # NoneType도 처리
                    current_return = returns.get('1d_returns')

                if current_return is not None and current_return > max_return:
                    max_return = current_return
                    top_stock = stock_code

        if not top_stock:
            logger.debug(f"{log_prefix} Could not determine top returning stock.")
            return ranked_items

        logger.debug(f"{log_prefix} Top returning stock: {top_stock} (return: {max_return:.4f})")

        boosted_count = 0
        new_ranked_items = []
        for item_id, score in ranked_items:
            item_stock_code = content_meta.get(item_id, {}).get("label")
            if item_stock_code == top_stock:
                boosted_count += 1
                new_score = score * self.BOOST_FACTOR
                logger.debug(f"{log_prefix} Boosting top return stock item {item_id} score from {score:.4f} to {new_score:.4f}")
                new_ranked_items.append((item_id, new_score))
            else:
                new_ranked_items.append((item_id, score))

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"{log_prefix} Boosted scores for {boosted_count} top return stock items in {duration_ms:.2f}ms.")
        # 점수 기준으로 다시 정렬
        new_ranked_items.sort(key=lambda x: x[1], reverse=True)
        return new_ranked_items


class AddScoreNoiseRule(BasePostRankReorderRule):
    """점수에 약간의 랜덤 노이즈를 추가하여 다양성 확보"""
    rule_name = "AddScoreNoise"
    NOISE_LEVEL = 0.01 # 노이즈 강도 (조정 가능)

    async def apply(self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        new_ranked_items = []
        for item_id, score in ranked_items:
            # 점수 범위에 비례하는 노이즈 추가 또는 고정 범위 노이즈 추가
            # 여기서는 점수와 무관하게 작은 난수 추가 (0 ~ NOISE_LEVEL 사이)
            noise = random.uniform(0, self.NOISE_LEVEL)
            new_score = score + noise
            new_ranked_items.append((item_id, new_score))
            # logger.debug(f"{log_prefix} Added noise to item {item_id}. Score: {score:.4f} -> {new_score:.4f}") # 너무 많을 수 있음

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"{log_prefix} Added noise to {len(new_ranked_items)} items in {duration_ms:.4f}ms.")
        # 노이즈 추가 후 최종 정렬
        new_ranked_items.sort(key=lambda x: x[1], reverse=True)
        return new_ranked_items