# simplers/batch/utils/data_loader.py
import logging
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd  # Timestamp 사용 시
import requests
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from opensearchpy.helpers import scan  # [추가] 대용량 데이터 처리를 위한 scan 헬퍼

logger = logging.getLogger(__name__)

class DataLoaderError(Exception):
    """데이터 로더 관련 예외"""
    pass

class APIConnectionError(DataLoaderError):
    """API 연결 관련 예외"""
    pass

class DataValidationError(DataLoaderError):
    """데이터 검증 관련 예외"""
    pass

class RateLimitError(DataLoaderError):
    """API 호출 제한 관련 예외"""
    pass


def validate_customer_id(customer_no: str, max_length: int = 20) -> bool:
    """간단한 고객번호 형식 검증 함수.

    고객번호가 숫자로만 이루어져 있고 지정된 최대 길이를 넘지 않는지 확인한다.

    Args:
        customer_no: 검증할 고객번호
        max_length: 허용할 최대 길이 (기본 20)

    Returns:
        고객번호가 유효한 형식이면 True, 그렇지 않으면 False
    """

    if customer_no is None:
        return False

    # 문자열이 아니면 문자열로 변환 후 검사
    if not isinstance(customer_no, str):
        customer_no = str(customer_no)

    if not customer_no.isdigit():
        return False

    if len(customer_no) == 0 or len(customer_no) > max_length:
        return False

    return True


def create_robust_session(max_retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    """재시도 로직이 포함된 requests 세션을 생성합니다.

    Args:
        max_retries: 최대 재시도 횟수
        backoff_factor: 재시도 간 대기 시간 배율

    Returns:
        재시도 설정이 적용된 requests.Session 객체
    """

    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def load_user_interactions(os_client: Any, days_limit: int) -> Dict[str, List[str]]:
    """OpenSearch에서 최근 사용자 상호작용 로그를 로드합니다."""

    log_prefix = "[DataLoader-UserInteractions]"
    logger.info(
        f"{log_prefix} Loading user interactions from OpenSearch (last {days_limit} days)..."
    )
    interactions: Dict[str, List[str]] = defaultdict(list)
    start_time = pd.Timestamp.now()

    if not validate_opensearch_client(os_client):
        logger.error(f"{log_prefix} OpenSearch client is not available.")
        return dict(interactions)

    index_pattern = (
        f"curation-logs-{(datetime.utcnow() - timedelta(days=days_limit)).strftime('%Y%m')}*"
    )

    query = {
        "query": {
            "range": {
                "@timestamp": {
                    "gte": f"now-{days_limit}d/d",
                    "lt": "now/d",
                }
            }
        },
        "_source": ["cust_no", "curation_id"],
    }

    try:
        response = scan(
            client=os_client,
            index=index_pattern,
            query=query,
            scroll="5m",
            raise_on_error=True,
            preserve_order=False,
            clear_scroll=True,
        )

        processed_logs = 0
        for hit in response:
            source = hit.get("_source", {})
            user_id = source.get("cust_no")
            item_id = source.get("curation_id")
            if user_id and item_id:
                interactions[str(user_id)].append(str(item_id))
                processed_logs += 1

        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(
            f"{log_prefix} Loaded {processed_logs} interaction logs for {len(interactions)} users in {duration:.2f} seconds."
        )

    except Exception as e:
        logger.error(
            f"{log_prefix} Failed to load user interactions using scan: {e}",
            exc_info=True,
        )
        return {}

    return dict(interactions)

# 다른 데이터 로더 함수들 추가 가능 (예: fetch_stock_metadata)

def fetch_user_portfolio(customer_no: str, api_base_url: str = "http://172.17.4.53:8150", 
                        max_retries: int = 3, timeout: int = 15) -> Dict[str, Any]:
    """
    사용자 포트폴리오 정보를 외부 API에서 가져옵니다.
    
    Args:
        customer_no: 고객번호
        api_base_url: API 서버 기본 URL
        max_retries: 최대 재시도 횟수
        timeout: 요청 타임아웃 (초)
        
    Returns:
        포트폴리오 정보 딕셔너리
        
    Raises:
        APIConnectionError: API 연결 실패
        DataValidationError: 데이터 검증 실패
        RateLimitError: API 호출 제한 초과
    """
    # 입력 검증
    if not validate_customer_id(customer_no):
        logger.warning(f"Invalid customer ID format: {customer_no}, returning empty portfolio")
        return {}
    
    if not api_base_url or not isinstance(api_base_url, str):
        raise DataValidationError(f"Invalid API base URL: {api_base_url}")
    
    session = create_robust_session(max_retries)
    
    try:
        url = f"{api_base_url}/api/mu800"
        payload = {
            "customer_no": customer_no,
            "target_type": ["stock", "sector"],
            "top_n": 50  # 충분한 수의 종목 정보 가져오기
        }
        
        logger.debug(f"Fetching portfolio for customer: {customer_no} from {url}")
        
        start_time = time.time()
        response = session.post(url, json=payload, timeout=timeout)
        elapsed_time = time.time() - start_time
        
        logger.info(f"Portfolio API response time: {elapsed_time:.2f}s, status: {response.status_code}")
        
        # HTTP 상태 코드 체크
        if response.status_code == 429:
            logger.warning(f"API rate limit exceeded for customer {customer_no}, returning empty portfolio")
            return {}
        elif response.status_code == 404:
            logger.warning(f"Customer {customer_no} not found in portfolio API")
            return {}
        elif response.status_code >= 500:
            logger.error(f"Server error (status {response.status_code}) for customer {customer_no}")
            return {}
        
        response.raise_for_status()
        
        # JSON 파싱
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for customer {customer_no}: {e}")
            return {}
        
        # 응답 데이터 검증
        if not isinstance(data, dict):
            logger.warning(f"Unexpected response format for customer {customer_no}: {type(data)}")
            return {}
        
        logger.debug(f"Successfully fetched portfolio for customer {customer_no}")
        return data
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ({timeout}s) fetching portfolio for customer {customer_no}")
        return {}
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error fetching portfolio for customer {customer_no}: {e}")
        return {}
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching portfolio for customer {customer_no}: {e}")
        return {}
        
    except Exception as e:
        logger.error(f"Unexpected error fetching portfolio for customer {customer_no}: {e}")
        return {}
    
    finally:
        session.close()

def validate_opensearch_client(os_client) -> bool:
    """
    OpenSearch 클라이언트의 유효성을 검증합니다.
    
    Args:
        os_client: OpenSearch 클라이언트
        
    Returns:
        유효하면 True, 아니면 False
    """
    if not os_client:
        return False
        
    try:
        # 간단한 ping 테스트
        response = os_client.ping()
        return response
    except Exception as e:
        logger.warning(f"OpenSearch client validation failed: {e}")
        return False

def fetch_latest_stock_data(os_client, days_back: int = 3, max_records: int = 1000) -> List[Dict[str, Any]]:
    """
    OpenSearch에서 최신 주식 시세 데이터를 가져옵니다.
    
    Args:
        os_client: OpenSearch 클라이언트
        days_back: 며칠 전까지 데이터를 조회할지
        max_records: 최대 조회할 레코드 수
        
    Returns:
        주식 시세 데이터 리스트
        
    Raises:
        APIConnectionError: OpenSearch 연결 실패
        DataValidationError: 데이터 검증 실패
    """
    if not validate_opensearch_client(os_client):
        logger.error("OpenSearch client is not available or not responding")
        return []
    
    if days_back <= 0 or days_back > 30:
        raise DataValidationError(f"Invalid days_back value: {days_back}. Must be between 1 and 30.")
    
    if max_records <= 0 or max_records > 10000:
        raise DataValidationError(f"Invalid max_records value: {max_records}. Must be between 1 and 10000.")
    
    logger.info(f"Fetching latest stock data from OpenSearch (last {days_back} days, max {max_records} records)...")
    
    stock_data = []
    successful_queries = 0
    
    # 최근 며칠간의 인덱스에서 데이터 조회
    for i in range(days_back):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        index_name = f"screen-{date}"
        
        try:
            logger.debug(f"Querying index: {index_name}")
            
            start_time = time.time()
            response = os_client.search(
                index=index_name,
                size=max_records,
                _source=["shrt_code", "country", "1d_returns", "close_price", "volume", "market_cap"],
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"exists": {"field": "1d_returns"}},
                                {"terms": {"country": ["Korea", "USA"]}},
                                {"range": {"1d_returns": {"gte": -50, "lte": 50}}}  # 비현실적인 수익률 제외
                            ],
                            "must_not": [
                                {"term": {"shrt_code": ""}},  # 빈 종목코드 제외
                                {"range": {"1d_returns": {"gte": "null"}}}  # null 값 제외
                            ]
                        }
                    },
                    "sort": [{"1d_returns": {"order": "desc", "missing": "_last"}}]
                },
                ignore=[404]
            )
            elapsed_time = time.time() - start_time
            
            if 'hits' not in response:
                logger.warning(f"No hits field in response for index {index_name}")
                continue
                
            hits = response.get('hits', {}).get('hits', [])
            valid_records = 0
            
            for hit in hits:
                source = hit.get('_source', {})
                
                # 데이터 검증
                if not source.get('shrt_code'):
                    continue
                    
                if source.get('1d_returns') is None:
                    continue
                    
                try:
                    # 수익률이 숫자인지 확인
                    returns = float(source.get('1d_returns', 0))
                    if abs(returns) > 50:  # 50% 이상 변동은 비현실적
                        continue
                        
                    source['1d_returns'] = returns
                    stock_data.append(source)
                    valid_records += 1
                    
                except (ValueError, TypeError):
                    logger.debug(f"Invalid 1d_returns value for {source.get('shrt_code')}: {source.get('1d_returns')}")
                    continue
                    
            logger.info(f"Index {index_name}: {valid_records} valid records in {elapsed_time:.2f}s")
            successful_queries += 1
            
            # 충분한 데이터를 얻었으면 중단
            if len(stock_data) >= max_records // 2:
                break
                
        except Exception as e:
            logger.warning(f"Error querying index {index_name}: {e}")
            continue
    
    if successful_queries == 0:
        logger.error("Failed to query any OpenSearch indexes")
        return []
    
    # 중복 제거 (같은 종목코드)
    seen_codes = set()
    unique_stock_data = []
    for stock in stock_data:
        code = stock.get('shrt_code')
        if code not in seen_codes:
            seen_codes.add(code)
            unique_stock_data.append(stock)
    
    logger.info(
        f"Fetched {len(unique_stock_data)} unique stock records from OpenSearch "
        f"({successful_queries}/{days_back} indexes successful)"
    )
    return unique_stock_data
