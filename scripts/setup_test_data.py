#!/usr/bin/env python3
"""
테스트용 더미 데이터를 MongoDB에 생성하는 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
import pandas as pd
from datetime import datetime, timedelta
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_data():
    """테스트용 더미 데이터 생성"""
    
    # MongoDB 연결
    client = MongoClient("mongodb://localhost:27017")
    db = client["recommendation_db"]
    
    # 기존 데이터 삭제
    logger.info("Clearing existing test data...")
    db.user.delete_many({})
    db.curation.delete_many({})
    
    # 테스트 사용자 데이터 생성
    logger.info("Creating test users...")
    users = []
    for i in range(10):
        user = {
            "cust_no": f"100000{i:03d}",
            "cust_nm": f"테스트사용자{i+1}",
            "cyber_id": f"testuser{i+1}",
            "last_login_dt": datetime.now() - timedelta(days=random.randint(1, 30)),
            "concerns": [
                {"gic_code": "005930", "stk_name": "삼성전자"},
                {"gic_code": "000660", "stk_name": "SK하이닉스"}
            ],
            "create_dt": datetime.now(),
            "modi_dt": datetime.now()
        }
        users.append(user)
    
    db.user.insert_many(users)
    logger.info(f"Created {len(users)} test users")
    
    # 테스트 큐레이션 데이터 생성
    logger.info("Creating test curation content...")
    
    # 주식 종목 코드 리스트
    stock_codes = ["005930", "000660", "035420", "051910", "006400", "035720", "AAPL", "MSFT", "GOOGL", "TSLA"]
    sectors = ["기술", "금융", "소비재", "에너지", "헬스케어"]
    
    curations = []
    for i in range(100):
        stock_code = random.choice(stock_codes)
        sector = random.choice(sectors)
        
        curation = {
            "btopic": random.choice(["시장", "기업분석", "투자전략", "경제동향"]),
            "stopic": random.choice(["주가분석", "실적분석", "시장전망"]),
            "label": stock_code,
            "gic_code": f"UBSTLSA_{stock_code}",
            "krw_currv_sumamt": random.randint(1000000, 100000000),
            "stk_name": f"테스트종목{i%10}",
            "title": f"테스트 큐레이션 제목 {i+1}",
            "result": f"테스트 큐레이션 내용 {i+1}",
            "thumbnail": f"thumb_{i}.jpg",
            "total_click_cnt": random.randint(0, 1000),
            "recent_click_cnt": random.randint(0, 100),
            "liked_users": [f"100000{j:03d}" for j in random.sample(range(10), random.randint(0, 5))],
            "disliked_users": [],
            "live_from": datetime.now() - timedelta(days=random.randint(1, 30)),
            "entry_curation": [],
            "ext_lm_yn": "N",
            "create_dt": datetime.now(),
            "modi_dt": datetime.now()
        }
        curations.append(curation)
    
    db.curation.insert_many(curations)
    logger.info(f"Created {len(curations)} test curation content")
    
    logger.info("Test data creation completed!")
    client.close()

if __name__ == "__main__":
    create_test_data()