#!/usr/bin/env python3
"""
MongoDB에 테스트 데이터를 생성하는 스크립트
curation과 curation_hist 컬렉션에 샘플 데이터를 추가합니다.
"""

import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

async def create_test_data():
    # MongoDB 연결
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_database"]
    
    print("MongoDB에 테스트 데이터를 생성합니다...")
    
    # curation 컬렉션에 테스트 데이터 생성
    curation_data = []
    for i in range(1, 21):  # 20개의 curation 데이터
        curation_data.append({
            "_id": ObjectId(),
            "title": f"테스트 콘텐츠 {i}",
            "label": f"STOCK{i:03d}",  # 주식 코드
            "category": "stock_analysis" if i % 2 == 0 else "market_news",
            "created_at": datetime.utcnow() - timedelta(days=i),
            "content": f"이것은 테스트 콘텐츠 {i}의 내용입니다.",
            "author": f"작성자{i}",
            "tags": [f"tag{i}", f"category{i % 3}"]
        })
    
    # curation 컬렉션에 데이터 삽입
    result = await db.curation.insert_many(curation_data)
    print(f"curation 컬렉션에 {len(result.inserted_ids)}개의 문서를 삽입했습니다.")
    
    # curation_hist 컬렉션에 테스트 데이터 생성
    curation_hist_data = []
    for i in range(1, 16):  # 15개의 curation_hist 데이터
        curation_hist_data.append({
            "_id": ObjectId(),
            "title": f"과거 콘텐츠 {i}",
            "label": f"HIST{i:03d}",
            "category": "historical_data",
            "created_at": datetime.utcnow() - timedelta(days=30 + i),
            "archived_at": datetime.utcnow() - timedelta(days=i),
            "content": f"이것은 과거 콘텐츠 {i}의 내용입니다.",
            "reason": "archived_for_testing"
        })
    
    # curation_hist 컬렉션에 데이터 삽입
    result = await db.curation_hist.insert_many(curation_hist_data)
    print(f"curation_hist 컬렉션에 {len(result.inserted_ids)}개의 문서를 삽입했습니다.")
    
    # 테스트용 사용자 데이터 생성 (선택사항)
    user_data = {
        "_id": ObjectId(),
        "cust_no": 12345,
        "name": "테스트 사용자",
        "email": "test@example.com",
        "last_login_dt": datetime.utcnow() - timedelta(hours=2),
        "last_upd_dt": datetime.utcnow(),
        "preferences": {
            "categories": ["stock_analysis", "market_news"],
            "risk_level": "medium"
        }
    }
    
    await db.user.insert_one(user_data)
    print("user 컬렉션에 테스트 사용자를 추가했습니다.")
    
    # 비로그인 사용자용 global_data 생성
    curation_ids = [str(doc["_id"]) for doc in curation_data[:10]]  # 처음 10개만
    global_data = {
        "_id": "anonymous_recs",
        "curation_ids": curation_ids,
        "updated_at": datetime.utcnow()
    }
    
    await db.global_data.insert_one(global_data)
    print("global_data 컬렉션에 비로그인 추천 데이터를 추가했습니다.")
    
    # 데이터 확인
    curation_count = await db.curation.count_documents({})
    curation_hist_count = await db.curation_hist.count_documents({})
    user_count = await db.user.count_documents({})
    global_data_count = await db.global_data.count_documents({})
    
    print(f"\n=== 데이터 생성 완료 ===")
    print(f"curation: {curation_count}개")
    print(f"curation_hist: {curation_hist_count}개")
    print(f"user: {user_count}개")
    print(f"global_data: {global_data_count}개")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_test_data())