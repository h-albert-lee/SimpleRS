# simplers/batch/utils/data_loader.py
import logging
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd # Timestamp 사용 시

logger = logging.getLogger(__name__)

def load_user_interactions(db: Any, user_ids: List[str], days_limit: int = 30) -> Dict[str, List[str]]:
    """
    MongoDB 등에서 특정 기간 동안의 사용자 상호작용 기록을 로드합니다.

    Args:
        db: MongoDB 데이터베이스 객체.
        user_ids: 상호작용 기록을 로드할 사용자 ID 리스트.
        days_limit: 조회할 최근 기간 (일 단위).

    Returns:
        {user_id: [item_id1, item_id2, ...]} 형태의 딕셔너리. (최신순 정렬 가정)
    """
    logger.info(f"Loading user interactions for {len(user_ids)} users (last {days_limit} days)...")
    interactions = defaultdict(list)
    start_time = pd.Timestamp.now()

    if not user_ids:
        return interactions

    try:
        # MongoDB 컬렉션 이름 확인 필요 (예: curation-logs 또는 다른 상호작용 로그 컬렉션)
        logs_collection = db['curation_logs_prod'] # 예시 컬렉션 이름
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_limit)

        # 사용자 ID 필드명, 아이템 ID 필드명, 타임스탬프 필드명 확인 필요
        # 예시 필드명: cust_no, curation_id, @timestamp
        user_id_field = "cust_no" # 실제 필드명으로 변경
        item_id_field = "curation_id" # 실제 필드명으로 변경
        timestamp_field = "@timestamp" # 실제 필드명으로 변경

        query = {
            user_id_field: {"$in": user_ids},
            timestamp_field: {"$gte": start_date, "$lt": end_date}
        }
        projection = {
            user_id_field: 1,
            item_id_field: 1,
            timestamp_field: 1,
            "_id": 0
        }

        # 효율적인 조회를 위해 인덱스 필요: (user_id_field, timestamp_field)
        cursor = logs_collection.find(query, projection).sort(timestamp_field, -1) # 최신순 정렬

        loaded_count = 0
        for log in cursor:
            user_id = log.get(user_id_field)
            item_id = log.get(item_id_field)
            # 사용자 ID 와 아이템 ID 가 유효한 경우에만 추가
            if user_id is not None and item_id:
                # 사용자 ID 타입을 문자열로 통일 (필요시)
                str_user_id = str(user_id)
                # 사용자의 상호작용 목록에 아이템 추가 (중복 제거는 CF/CB 로직에서 처리)
                interactions[str_user_id].append(item_id)
                loaded_count += 1

        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"Loaded {loaded_count} interaction logs for {len(interactions)} users in {duration:.2f} seconds.")

        # # --- 임시 더미 데이터 ---
        # logger.warning("Using dummy user interaction data for CF/CB!")
        # import numpy as np
        # content_meta_map = context.get('content_meta_map',{}) # 예시
        # items = list(content_meta_map.keys()) if content_meta_map else [f'item_{i}' for i in range(100)]
        # if items:
        #    for i, user_id in enumerate(user_ids):
        #         if i < len(user_ids) * 0.5 : # 50% 유저에게만 기록 부여
        #             interactions[str(user_id)] = np.random.choice(items, size=min(len(items), 30), replace=False).tolist()


    except Exception as e:
        logger.error(f"Error loading user interactions: {e}", exc_info=True)

    return interactions

# 다른 데이터 로더 함수들 추가 가능 (예: fetch_stock_metadata)

def fetch_user_portfolio(customer_no: str, api_base_url: str = "http://172.17.4.53:8150") -> Dict[str, Any]:
    """
    사용자 포트폴리오 정보를 외부 API에서 가져옵니다.
    
    Args:
        customer_no: 고객번호
        api_base_url: API 서버 기본 URL
        
    Returns:
        포트폴리오 정보 딕셔너리
    """
    import requests
    
    logger.debug(f"Fetching portfolio for customer: {customer_no}")
    
    try:
        url = f"{api_base_url}/api/mu800"
        payload = {
            "customer_no": customer_no,
            "target_type": ["stock", "sector"],
            "top_n": 50  # 충분한 수의 종목 정보 가져오기
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Successfully fetched portfolio for customer {customer_no}")
        return data
        
    except Exception as e:
        logger.error(f"Error fetching portfolio for customer {customer_no}: {e}")
        return {}

def fetch_latest_stock_data(os_client, days_back: int = 1) -> List[Dict[str, Any]]:
    """
    OpenSearch에서 최신 주식 시세 데이터를 가져옵니다.
    
    Args:
        os_client: OpenSearch 클라이언트
        days_back: 며칠 전까지 데이터를 조회할지
        
    Returns:
        주식 시세 데이터 리스트
    """
    logger.info("Fetching latest stock data from OpenSearch...")
    
    stock_data = []
    
    # 최근 며칠간의 인덱스에서 데이터 조회
    for i in range(days_back):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        index_name = f"screen-{date}"
        
        try:
            response = os_client.search(
                index=index_name,
                size=1000,  # 충분한 수의 데이터 조회
                _source=["shrt_code", "country", "1d_returns", "close_price", "volume"],
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "1d_returns"}},
                                {"terms": {"country": ["Korea", "USA"]}}
                            ]
                        }
                    },
                    "sort": [{"1d_returns": {"order": "desc", "missing": "_last"}}]
                },
                ignore=[404]
            )
            
            hits = response.get('hits', {}).get('hits', [])
            for hit in hits:
                source = hit.get('_source', {})
                if source.get('shrt_code') and source.get('1d_returns') is not None:
                    stock_data.append(source)
                    
            if hits:
                logger.debug(f"Found {len(hits)} stock records in index {index_name}")
                break  # 데이터를 찾으면 더 이전 날짜는 조회하지 않음
                
        except Exception as e:
            logger.warning(f"Error querying index {index_name}: {e}")
            continue
    
    logger.info(f"Fetched {len(stock_data)} stock records from OpenSearch")
    return stock_data