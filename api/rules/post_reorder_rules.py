import logging
import math
import random
import statistics
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .base import BasePostRankReorderRule


logger = logging.getLogger(__name__)


class MarketCapRecencyRandomRule(BasePostRankReorderRule):
    """시가총액·신규성·랜덤 점수를 종합해 기본 점수를 계산하는 규칙"""

    rule_name = "MarketCapRecencyRandom"
    ORIGINAL_SCORE_WEIGHT = 1.0
    MARKET_CAP_WEIGHT = 1.0
    RECENCY_WEIGHT = 1.0
    RANDOM_WEIGHT = 1.0

    async def apply(
        self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        content_meta = user_context.get("content_meta", {})
        now = datetime.utcnow()

        market_caps: List[float] = []
        recencies: List[float] = []

        for item_id, _ in ranked_items:
            meta = content_meta.get(item_id, {})
            market_caps.append(float(meta.get("market_cap", 0.0) or 0.0))

            created_at = meta.get("created_at") or meta.get("created_dt")
            created_dt = None
            if isinstance(created_at, str):
                try:
                    created_dt = datetime.fromisoformat(created_at)
                except ValueError:
                    created_dt = None
            elif isinstance(created_at, datetime):
                created_dt = created_at

            if created_dt is None:
                recencies.append(float("inf"))
            else:
                recencies.append((now - created_dt).total_seconds())

        def _normalize(values: List[float], higher_better: bool = True) -> List[float]:
            if not values:
                return []

            finite = [v for v in values if math.isfinite(v)] or [0.0]
            max_finite = max(finite)
            processed = [v if math.isfinite(v) else max_finite + 86400 for v in values]

            mean = statistics.mean(processed)
            stdev = statistics.pstdev(processed) or 1.0
            z_scores = [(v - mean) / stdev for v in processed]
            if not higher_better:
                z_scores = [-z for z in z_scores]
            return [0.5 * (1 + math.erf(z / math.sqrt(2))) for z in z_scores]

        norm_market = _normalize(market_caps, higher_better=True)
        norm_recency = _normalize(recencies, higher_better=False)
        rand_scores = [random.random() for _ in ranked_items]
        norm_random = _normalize(rand_scores, higher_better=True)

        new_ranked: List[Tuple[str, float]] = []
        for (item_id, orig_score), m, r, rnd in zip(
            ranked_items, norm_market, norm_recency, norm_random
        ):
            score = (
                self.ORIGINAL_SCORE_WEIGHT * orig_score
                + self.MARKET_CAP_WEIGHT * m
                + self.RECENCY_WEIGHT * r
                + self.RANDOM_WEIGHT * rnd
            )
            new_ranked.append((item_id, score))

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "[MarketCapRecencyRandom] Scored %d items in %.2fms.",
            len(new_ranked),
            duration_ms,
        )

        new_ranked.sort(key=lambda x: x[1], reverse=True)
        return new_ranked


class BoostUserStocksRule(BasePostRankReorderRule):
    """사용자 관련 주식(보유·최근·관심·온보딩) 콘텐츠 점수를 보강"""

    rule_name = "BoostUserStocks"
    WEIGHTS = {"owned": 1.5, "recent": 1.3, "group1": 1.2, "onboarding": 1.1}

    async def apply(
        self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        owned = user_context.get("owned_stocks_set", set())
        recent = user_context.get("recent_stocks_set", set())
        group1 = user_context.get("group1_stocks_set", set())
        onboarding = user_context.get("onboarding_stocks_set", set())
        meta = user_context.get("content_meta", {})

        if not any([owned, recent, group1, onboarding]):
            logger.debug(f"{log_prefix} No user stock lists found. Skipping.")
            return ranked_items

        boosted: List[Tuple[str, float]] = []
        count = 0
        for item_id, score in ranked_items:
            stock_code = meta.get(item_id, {}).get("label")
            boost = 1.0
            if stock_code in owned:
                boost = max(boost, self.WEIGHTS["owned"])
            if stock_code in recent:
                boost = max(boost, self.WEIGHTS["recent"])
            if stock_code in group1:
                boost = max(boost, self.WEIGHTS["group1"])
            if stock_code in onboarding:
                boost = max(boost, self.WEIGHTS["onboarding"])

            if boost > 1.0:
                count += 1
                boosted.append((item_id, score * boost))
            else:
                boosted.append((item_id, score))

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"{log_prefix} Boosted scores for {count} items in {duration_ms:.2f}ms."
        )
        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted


class BoostTopReturnStockRule(BasePostRankReorderRule):
    """보유 종목 중 수익률 상위 종목 콘텐츠 점수를 강화"""

    rule_name = "BoostTopReturnStock"
    BOOST_FACTOR = 2.0

    async def apply(
        self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        owned = user_context.get("owned_stocks_set", set())
        returns = user_context.get("owned_stock_returns", {})
        meta = user_context.get("content_meta", {})

        top_stock = None
        max_ret = -float("inf")
        for stock in owned:
            r = returns.get(stock, {})
            val = r.get("1m_returns")
            if val is None:
                val = r.get("1d_returns")
            if val is not None and val > max_ret:
                max_ret = val
                top_stock = stock

        if top_stock is None:
            logger.debug(f"{log_prefix} Could not determine top returning stock.")
            return ranked_items

        boosted: List[Tuple[str, float]] = []
        count = 0
        for item_id, score in ranked_items:
            code = meta.get(item_id, {}).get("label")
            if code == top_stock:
                boosted.append((item_id, score * self.BOOST_FACTOR))
                count += 1
            else:
                boosted.append((item_id, score))

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"{log_prefix} Boosted scores for {count} items in {duration_ms:.2f}ms."
        )
        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted


class AddScoreNoiseRule(BasePostRankReorderRule):
    """점수에 작은 랜덤 노이즈를 추가하여 다양성 확보"""

    rule_name = "AddScoreNoise"
    NOISE_LEVEL = 0.01

    async def apply(
        self, user_context: Dict[str, Any], ranked_items: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        start_time = time.perf_counter()
        cust_no = user_context.get("cust_no", "UNKNOWN")
        log_prefix = f"[{self.rule_name}][cust_no={cust_no}]"

        new_ranked = [
            (item_id, score + random.uniform(0, self.NOISE_LEVEL))
            for item_id, score in ranked_items
        ]

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"{log_prefix} Added noise to {len(new_ranked)} items in {duration_ms:.2f}ms."
        )
        new_ranked.sort(key=lambda x: x[1], reverse=True)
        return new_ranked

