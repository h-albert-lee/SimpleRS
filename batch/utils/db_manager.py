# simplers/batch/utils/db_manager.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError, BulkWriteError
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import ConnectionError as OSConnectionError, RequestError as OSRequestError
import oracledb # oracledb 임포트
import pandas as pd
import dask.dataframe as dd
import logging
import time
from contextlib import contextmanager
from typing import Dict, List, Any, Optional

# 배치용 설정 로더 임포트 (Oracle 설정 포함)
from batch.utils.config_loader import MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG

logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """데이터베이스 관련 예외"""
    pass

class MongoDBError(DatabaseError):
    """MongoDB 관련 예외"""
    pass

class OpenSearchError(DatabaseError):
    """OpenSearch 관련 예외"""
    pass

class DataIntegrityError(DatabaseError):
    """데이터 무결성 관련 예외"""
    pass

# --- MongoDB 클라이언트 관리 ---
mongo_client: MongoClient = None
mongo_db = None

@contextmanager
def mongodb_connection_context():
    """MongoDB 연결을 안전하게 관리하는 컨텍스트 매니저"""
    client = None
    try:
        uri = MONGO_CONFIG.get("uri")
        db_name = MONGO_CONFIG.get("db_name")
        
        if not uri or not db_name:
            raise MongoDBError("MongoDB URI or DB Name not configured in config.yaml")
        
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,  # 5초 타임아웃
            connectTimeoutMS=10000,         # 10초 연결 타임아웃
            socketTimeoutMS=30000,          # 30초 소켓 타임아웃
            maxPoolSize=10,                 # 최대 연결 풀 크기
            retryWrites=True                # 쓰기 재시도 활성화
        )
        
        # 연결 테스트
        client.admin.command('ping')
        db = client[db_name]
        
        yield db
        
    except ServerSelectionTimeoutError:
        logger.error("MongoDB server selection timeout - check if MongoDB is running")
        raise MongoDBError("MongoDB server not available")
    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failure: {e}")
        raise MongoDBError(f"Failed to connect to MongoDB: {e}")
    except Exception as e:
        logger.error(f"Unexpected MongoDB error: {e}")
        raise MongoDBError(f"MongoDB error: {e}")
    finally:
        if client:
            client.close()

def connect_mongo():
    """설정 파일을 사용하여 MongoDB에 연결하고 DB 객체를 반환합니다."""
    global mongo_client, mongo_db
    if mongo_db:
        return mongo_db
        
    uri = MONGO_CONFIG.get("uri")
    db_name = MONGO_CONFIG.get("db_name")
    
    if not uri or not db_name:
        logger.error("MongoDB URI or DB Name not configured in config.yaml")
        raise MongoDBError("MongoDB URI or DB Name not configured.")
        
    try:
        logger.info(f"Connecting to MongoDB: {uri} (DB: {db_name})")
        
        mongo_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            maxPoolSize=10,
            retryWrites=True
        )
        
        # 연결 테스트
        start_time = time.time()
        mongo_client.admin.command('ping')
        elapsed_time = time.time() - start_time
        
        mongo_db = mongo_client[db_name]
        logger.info(f"MongoDB connected successfully in {elapsed_time:.2f}s")
        return mongo_db
        
    except ServerSelectionTimeoutError:
        logger.error("MongoDB server selection timeout - check if MongoDB is running")
        raise MongoDBError("MongoDB server not available")
    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failure: {e}")
        raise MongoDBError(f"Failed to connect to MongoDB: {e}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        raise MongoDBError(f"Could not connect to MongoDB: {e}")

def get_mongo_db():
    """연결된 MongoDB 데이터베이스 객체를 반환합니다."""
    return mongo_db if mongo_db else connect_mongo()

def close_mongo():
    """MongoDB 연결을 닫습니다."""
    global mongo_client, mongo_db
    if mongo_client:
        mongo_client.close()
        mongo_client = None
        mongo_db = None
        logger.info("MongoDB connection closed.")

# --- OpenSearch 클라이언트 관리 ---
os_client: OpenSearch = None

def connect_opensearch():
    """설정 파일을 사용하여 OpenSearch에 연결하고 클라이언트 객체를 반환합니다."""
    global os_client
    if os_client:
        return os_client
    hosts = OPENSEARCH_CONFIG.get("hosts")
    http_auth_config = OPENSEARCH_CONFIG.get("http_auth")
    if not hosts:
        logger.error("OpenSearch hosts not configured in config.yaml")
        raise ValueError("OpenSearch hosts not configured.")
    client_args = {
        "hosts": hosts,
        "use_ssl": True,
        "verify_certs": False,
        "ssl_assert_hostname": False,
        "ssl_show_warn": False,
        "connection_class": RequestsHttpConnection
    }
    # (OpenSearch 인증 로직 동일)
    if http_auth_config:
        if isinstance(http_auth_config, dict):
            user = http_auth_config.get('user')
            password = http_auth_config.get('password') or http_auth_config.get('pass')
            if user is not None and password is not None:
                 client_args["http_auth"] = (user, password)
            else:
                 logger.warning("OpenSearch http_auth user or password missing in config.")
        elif isinstance(http_auth_config, (list, tuple)) and len(http_auth_config) == 2:
             client_args["http_auth"] = tuple(http_auth_config)
        else:
            logger.warning("http_auth format not recognized.")
    try:
        logger.info(f"Connecting to OpenSearch: {hosts}")
        os_client = OpenSearch(**client_args)
        if os_client.ping():
            logger.info("OpenSearch connected successfully.")
        else:
            logger.warning("Failed to ping OpenSearch.")
        return os_client
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch: {e}", exc_info=True)
        raise RuntimeError(f"Could not connect to OpenSearch: {e}")

def get_os_client():
    """연결된 OpenSearch 클라이언트 객체를 반환합니다."""
    return os_client if os_client else connect_opensearch()

def close_opensearch():
    """OpenSearch 연결을 닫습니다."""
    global os_client
    if os_client:
        os_client = None # 동기 클라이언트는 명시적 close 없음
        logger.info("OpenSearch client object cleared.")

# --- Oracle DB 연결 풀 관리 추가 (동기) ---
oracle_pool = None

# --- Oracle Client 초기화 (API와 동일하게 배치 시작 시 필요할 수 있음) ---
# client_lib_dir = ORACLE_CONFIG.get("client_lib_dir")
# if client_lib_dir:
#     try:
#         logger.info(f"Initializing Oracle Client library for batch: {client_lib_dir}")
#         oracledb.init_oracle_client(lib_dir=client_lib_dir)
#     except Exception as e:
#         logger.error(f"Failed to initialize Oracle Client library for batch: {e}", exc_info=True)
#         raise RuntimeError("Oracle Client initialization failed for batch.")


def connect_oracle():
    """Oracle DB 동기 연결 풀을 생성하고 반환합니다."""
    global oracle_pool
    if oracle_pool:
        return oracle_pool

    logger.info("Connecting to Oracle DB and creating connection pool (sync)...")
    user = ORACLE_CONFIG.get("user")
    password = ORACLE_CONFIG.get("password")
    dsn = ORACLE_CONFIG.get("dsn")
    encoding = ORACLE_CONFIG.get("encoding", "UTF-8")
    pool_min = ORACLE_CONFIG.get("pool_min", 1)
    pool_max = ORACLE_CONFIG.get("pool_max", 4)
    pool_increment = ORACLE_CONFIG.get("pool_increment", 1)
    pool_timeout = ORACLE_CONFIG.get("pool_timeout", 60)

    if not user or not password or not dsn:
        logger.error("Oracle DB connection info (user, password, dsn) is missing in config.")
        raise ValueError("Oracle DB connection info is missing.")

    try:
        # 동기 연결 풀 생성
        oracle_pool = oracledb.create_pool(
            user=user,
            password=password,
            dsn=dsn,
            min=pool_min,
            max=pool_max,
            increment=pool_increment,
            getmode=oracledb.POOL_GETMODE_WAIT,
            timeout=pool_timeout,
            encoding=encoding
        )
        # 간단한 테스트 쿼리
        with oracle_pool.acquire() as conn:
             with conn.cursor() as cursor:
                 cursor.execute("SELECT 1 FROM DUAL")
                 cursor.fetchone()
        logger.info(f"Oracle DB sync connection pool created successfully (min={pool_min}, max={pool_max}). Ping successful.")
        return oracle_pool
    except Exception as e:
        logger.error(f"Failed to create Oracle DB sync connection pool: {e}", exc_info=True)
        oracle_pool = None
        raise RuntimeError(f"Could not connect to Oracle DB: {e}")

def get_oracle_pool():
    """생성된 Oracle DB 동기 연결 풀을 반환합니다."""
    return oracle_pool if oracle_pool else connect_oracle()

def close_oracle():
    """Oracle DB 동기 연결 풀을 닫습니다."""
    global oracle_pool
    if oracle_pool:
        try:
            oracle_pool.close()
            logger.info("Oracle DB sync connection pool closed.")
        except Exception as e:
            logger.error(f"Error closing Oracle DB sync connection pool: {e}", exc_info=True)
        finally:
            oracle_pool = None


# --- 데이터 로딩 함수 (수정 없음) ---
# load_contents, load_users, load_user_port 함수는 그대로 유지
def load_contents(db) -> dd.DataFrame:
    """
    MongoDB의 'curation' 컬렉션에서 콘텐츠 데이터를 불러와 Dask DataFrame으로 변환.
    """
    logger.info("Loading contents from MongoDB 'curation' collection...")
    start_time = pd.Timestamp.now()
    try:
        curation_coll = db['curation']
        contents_cursor = curation_coll.find()
        contents_list = list(contents_cursor) # 커서를 리스트로 변환
        for content in contents_list:
            content['id'] = str(content.get('_id'))
        contents_pd = pd.DataFrame(contents_list)
        mem_usage = contents_pd.memory_usage(deep=True).sum() / (1024**2)
        logger.info(f"Loaded {len(contents_pd)} contents into Pandas DataFrame ({mem_usage:.2f} MB). Converting to Dask DataFrame.")
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"Contents loading took {duration:.2f} seconds.")
        return dd.from_pandas(contents_pd, npartitions=4)
    except Exception as e:
        logger.error(f"Error loading contents: {e}", exc_info=True)
        raise

def load_users(db) -> dd.DataFrame:
    """
    MongoDB의 'user' 컬렉션에서 사용자 데이터를 불러와 Dask DataFrame으로 변환.
    """
    logger.info("Loading users from MongoDB 'user' collection...")
    start_time = pd.Timestamp.now()
    try:
        user_coll = db['user']
        users_cursor = user_coll.find()
        users_list = list(users_cursor)
        for user in users_list:
             user['id'] = str(user.get('_id')) # 예시: _id를 문자열 ID로 사용
             user.setdefault("owned_stocks", [])
        users_pd = pd.DataFrame(users_list)
        mem_usage = users_pd.memory_usage(deep=True).sum() / (1024**2)
        logger.info(f"Loaded {len(users_pd)} users into Pandas DataFrame ({mem_usage:.2f} MB). Converting to Dask DataFrame.")
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"Users loading took {duration:.2f} seconds.")
        return dd.from_pandas(users_pd, npartitions=4)
    except Exception as e:
        logger.error(f"Error loading users: {e}", exc_info=True)
        raise

def load_user_port(db) -> dd.DataFrame:
    """
    MongoDB의 'user_port' 컬렉션에서 사용자 보유 종목 정보를 불러옴.
    """
    logger.info("Loading user portfolio data from MongoDB 'user_port' collection...")
    start_time = pd.Timestamp.now()
    try:
        port_coll = db['user_port']
        ports_cursor = port_coll.find()
        ports_list = list(ports_cursor)
        ports_pd = pd.DataFrame(ports_list)
        mem_usage = ports_pd.memory_usage(deep=True).sum() / (1024**2)
        logger.info(f"Loaded {len(ports_pd)} portfolio records into Pandas DataFrame ({mem_usage:.2f} MB). Converting to Dask DataFrame.")
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"User portfolio loading took {duration:.2f} seconds.")
        return dd.from_pandas(ports_pd, npartitions=1)
    except Exception as e:
        logger.error(f"Error loading user portfolio data: {e}", exc_info=True)
        raise

# --- 결과 저장 함수 (수정 없음) ---
def validate_candidate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    후보 결과 데이터의 유효성을 검증하고 정제합니다.
    
    Args:
        results: 검증할 결과 리스트
        
    Returns:
        검증된 결과 리스트
        
    Raises:
        DataIntegrityError: 데이터 무결성 오류
    """
    if not isinstance(results, list):
        raise DataIntegrityError(f"Results must be a list, got {type(results)}")
    
    validated_results = []
    invalid_count = 0
    
    for i, result in enumerate(results):
        if not isinstance(result, dict):
            logger.warning(f"Result {i} is not a dictionary: {type(result)}")
            invalid_count += 1
            continue
            
        cust_no = result.get('cust_no')
        if not cust_no or not isinstance(cust_no, str):
            logger.warning(f"Result {i} has invalid cust_no: {cust_no}")
            invalid_count += 1
            continue
            
        curation_list = result.get('curation_list', [])
        if not isinstance(curation_list, list):
            logger.warning(f"Result {i} has invalid curation_list: {type(curation_list)}")
            invalid_count += 1
            continue
            
        # curation_list 내부 검증
        valid_curations = []
        for curation in curation_list:
            if not isinstance(curation, dict):
                continue
            if 'curation_id' not in curation or 'score' not in curation:
                continue
            try:
                score = float(curation['score'])
                valid_curations.append({
                    'curation_id': str(curation['curation_id']),
                    'score': score
                })
            except (ValueError, TypeError):
                continue
        
        if valid_curations:
            validated_results.append({
                'cust_no': cust_no,
                'curation_list': valid_curations
            })
        else:
            invalid_count += 1
    
    if invalid_count > 0:
        logger.warning(f"Filtered out {invalid_count} invalid results")
    
    return validated_results

def save_results(results: List[Dict[str, Any]], db, collection_name: str = "user_candidate", 
                batch_size: int = 1000, max_retries: int = 3) -> bool:
    """
    최종 candidate generation 결과를 MongoDB user_candidate 컬렉션에 저장.
    
    Args:
        results: 저장할 결과 리스트
        db: MongoDB 데이터베이스 객체
        collection_name: 저장할 컬렉션 이름
        batch_size: 배치 처리 크기
        max_retries: 최대 재시도 횟수
        
    Returns:
        저장 성공 여부
        
    Raises:
        MongoDBError: MongoDB 저장 실패
        DataIntegrityError: 데이터 무결성 오류
    """
    if not results:
        logger.info("No results to save.")
        return True
    
    # 데이터 검증
    try:
        validated_results = validate_candidate_results(results)
    except DataIntegrityError as e:
        logger.error(f"Data validation failed: {e}")
        raise
    
    if not validated_results:
        logger.warning("No valid results after validation")
        return False
    
    logger.info(f"Saving {len(validated_results)} validated user candidate results to MongoDB collection '{collection_name}'...")
    
    try:
        target_collection = db[collection_name]
        from pymongo import UpdateOne
        
        total_saved = 0
        total_batches = (len(validated_results) + batch_size - 1) // batch_size
        
        # 배치 단위로 처리
        for batch_idx in range(0, len(validated_results), batch_size):
            batch_results = validated_results[batch_idx:batch_idx + batch_size]
            current_batch = (batch_idx // batch_size) + 1
            
            operations = []
            for res in batch_results:
                cust_no = res['cust_no']
                curation_list = res['curation_list']
                
                filter_query = {'cust_no': cust_no}
                update_doc = {
                    '$set': {
                        'curation_list': curation_list,
                        'modi_dt': pd.Timestamp.now()
                    },
                    '$setOnInsert': {
                        'create_dt': pd.Timestamp.now()
                    }
                }
                operations.append(UpdateOne(filter_query, update_doc, upsert=True))
            
            # 재시도 로직
            for retry in range(max_retries):
                try:
                    start_time = time.time()
                    result = target_collection.bulk_write(operations, ordered=False)
                    elapsed_time = time.time() - start_time
                    
                    batch_saved = result.matched_count + result.upserted_count
                    total_saved += batch_saved
                    
                    logger.info(f"Batch {current_batch}/{total_batches}: {batch_saved} records saved "
                              f"(Matched: {result.matched_count}, Upserted: {result.upserted_count}, "
                              f"Modified: {result.modified_count}) in {elapsed_time:.2f}s")
                    break
                    
                except BulkWriteError as e:
                    logger.error(f"Bulk write error in batch {current_batch}, retry {retry + 1}: {e}")
                    if retry == max_retries - 1:
                        raise MongoDBError(f"Failed to save batch {current_batch} after {max_retries} retries")
                    time.sleep(2 ** retry)  # 지수 백오프
                    
                except Exception as e:
                    logger.error(f"Unexpected error in batch {current_batch}, retry {retry + 1}: {e}")
                    if retry == max_retries - 1:
                        raise MongoDBError(f"Failed to save batch {current_batch}: {e}")
                    time.sleep(2 ** retry)
        
        logger.info(f"Successfully saved {total_saved} user candidate results to MongoDB")
        return True
        
    except (MongoDBError, DataIntegrityError):
        # 이미 처리된 예외는 다시 발생
        raise
        
    except Exception as e:
        logger.error(f"Error saving results to MongoDB collection '{collection_name}': {e}", exc_info=True)
        
        # 폴백: 로컬 파일로 저장
        logger.info("Attempting to save results to local file as fallback...")
        try:
            import json
            fallback_file = f"candidate_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(fallback_file, 'w', encoding='utf-8') as f:
                json.dump(validated_results, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Successfully saved results to fallback file: {fallback_file}")
            return False  # MongoDB 저장은 실패했지만 폴백은 성공
            
        except Exception as backup_e:
            logger.error(f"Failed to save results to fallback file: {backup_e}")
            raise MongoDBError(f"Failed to save results to both MongoDB and fallback file: {e}")

# --- 외부 API 호출 함수 (수정 없음) ---
def call_external_api(api_url, params):
    """외부 API를 호출하는 함수 (예시)"""
    logger.debug(f"Calling external API: {api_url} with params: {params}")
    try:
        # import requests
        # response = requests.get(api_url, params=params, timeout=5)
        # response.raise_for_status()
        # return response.json()
        return {"dummy_key": "dummy_value_from_api"}
    except Exception as e:
        logger.error(f"Error calling external API {api_url}: {e}", exc_info=True)
        return None