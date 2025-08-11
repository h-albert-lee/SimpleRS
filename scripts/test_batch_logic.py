#!/usr/bin/env python3
"""
배치 로직을 테스트하는 스크립트 (실제 DB 연결 없이)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
import random

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_rules():
    """규칙들을 개별적으로 테스트"""
    
    # 더미 컨텍스트 생성
    dummy_contents = []
    for i in range(50):
        content = {
            "_id": f"content_{i}",
            "btopic": random.choice(["시장", "기업분석", "투자전략"]),
            "stopic": "주가분석",
            "label": random.choice(["005930", "000660", "AAPL", "MSFT"]),
            "gic_code": f"UBSTLSA_{random.choice(['005930', '000660', 'AAPL'])}",
            "title": f"테스트 컨텐츠 {i+1}",
            "liked_users": [f"100000{j:03d}" for j in random.sample(range(10), random.randint(0, 5))],
            "create_dt": datetime.now() - timedelta(days=random.randint(1, 30))
        }
        dummy_contents.append(content)

    dummy_portfolio = {
        'portfolio_info': [
            {'kor_name': '삼성전자', 'gic_code': '005930', 'sector': 'IT'},
            {'kor_name': 'SK하이닉스', 'gic_code': '000660', 'sector': 'IT'}
        ],
        'sector_weight': {'IT': 1.0}
    }

    dummy_context = {
        'contents_list': dummy_contents,
        'content_meta_map': {c['_id']: c for c in dummy_contents},
        'max_candidates_per_user': 100,
        'portfolio_data': dummy_portfolio,
    }
    
    # 더미 사용자
    dummy_user = {
        "cust_no": "1000001",
        "cust_nm": "테스트사용자1",
        "concerns": [
            {"gic_code": "005930", "stk_name": "삼성전자"},
            {"gic_code": "000660", "stk_name": "SK하이닉스"}
        ]
    }
    
    logger.info("Testing Global Rules...")
    try:
        from batch.rules.global_rules import GlobalStockTopReturnRule, GlobalTopLikedContentRule
        
        # Global Stock Top Return Rule 테스트
        global_stock_rule = GlobalStockTopReturnRule()
        logger.info(f"Testing {global_stock_rule.rule_name}...")
        # 실제 OpenSearch 없이는 빈 리스트 반환될 것
        global_candidates = global_stock_rule.apply(dummy_context)
        logger.info(f"Global stock candidates: {len(global_candidates)}")
        
        # Global Top Liked Content Rule 테스트
        liked_rule = GlobalTopLikedContentRule()
        logger.info(f"Testing {liked_rule.rule_name}...")
        other_candidates = liked_rule.apply(dummy_context)
        logger.info(f"Other candidates (liked): {len(other_candidates)}")
        
    except Exception as e:
        logger.error(f"Error testing global rules: {e}")
    
    logger.info("Testing Local Rules...")
    try:
        from batch.rules.local_rules import LocalMarketContentRule, LocalOwnedStockContentRule, LocalSectorContentRule
        
        # Local Market Content Rule 테스트
        market_rule = LocalMarketContentRule()
        logger.info(f"Testing {market_rule.rule_name}...")
        market_candidates = market_rule.apply(dummy_user, dummy_context)
        logger.info(f"Market candidates: {len(market_candidates)}")
        
        # Local Owned Stock Content Rule 테스트
        owned_rule = LocalOwnedStockContentRule()
        logger.info(f"Testing {owned_rule.rule_name}...")
        owned_candidates = owned_rule.apply(dummy_user, dummy_context)
        logger.info(f"Owned stock candidates: {len(owned_candidates)}")
        
        # Local Sector Content Rule 테스트
        sector_rule = LocalSectorContentRule()
        logger.info(f"Testing {sector_rule.rule_name}...")
        sector_candidates = sector_rule.apply(dummy_user, dummy_context)
        logger.info(f"Sector candidates: {len(sector_candidates)}")
        
    except Exception as e:
        logger.error(f"Error testing local rules: {e}")
    
    logger.info("Testing Final Candidate Generation with CF...")
    try:
        from batch.pipeline.final_candidate import generate_candidate_for_user
        from batch.utils.cf_utils import CFModel
        from batch.utils.config_loader import SOURCE_WEIGHTS, CF_WEIGHT

        user_interactions = {
            dummy_user['cust_no']: ['item_A'],
            'u2': ['item_A', 'item_B'],
            'u3': ['item_A', 'item_B'],
        }

        cf_model = CFModel()
        cf_model.build(user_interactions)

        cf_context = dict(dummy_context)
        cf_context['cf_model'] = cf_model
        cf_context['user_interactions'] = user_interactions
        cf_context['contents_list'] = []  # 로컬 후보 비활성화를 위해
        cf_context['content_meta_map'] = {}
        cf_context['portfolio_data'] = {}

        global_candidates = []
        other_candidates = ['item_B']

        result = generate_candidate_for_user(
            dummy_user,
            global_candidates,
            other_candidates,
            cf_context
        )

        logger.info(f"Final result with CF: {result}")
        expected_score = SOURCE_WEIGHTS.get('other', 0.0) + CF_WEIGHT * (2/3)
        actual_score = result['curation_list'][0]['score'] if result else None
        assert abs(actual_score - expected_score) < 1e-6
        logger.info(
            f"Expected score {expected_score:.4f}, Actual score {actual_score:.4f}"
        )

    except Exception as e:
        logger.error(f"Error testing final candidate generation: {e}")

if __name__ == "__main__":
    test_rules()