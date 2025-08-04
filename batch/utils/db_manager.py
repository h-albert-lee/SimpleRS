# simplers/batch/utils/db_manager.py
from pymongo import MongoClient
from opensearchpy import OpenSearch, RequestsHttpConnection
import oracledb # oracledb 임포트
import pandas as pd
import dask.dataframe as dd
import logging

# 배치용 설정 로더 임포트 (Oracle 설정 포함)
from batch.utils.config_loader import MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG

logger = logging.getLogger(__name__)

# --- MongoDB 클라이언트 관리 ---
mongo_client: MongoClient = None
mongo_db = None

def connect_mongo():
    """설정 파일을 사용하여 MongoDB에 연결하고 DB 객체를 반환합니다."""
    global mongo_client, mongo_db
    if mongo_db:
        return mongo_db
    uri = MONGO_CONFIG.get("uri")
    db_name = MONGO_CONFIG.get("db_name")
    if not uri or not db_name:
        logger.error("MongoDB URI or DB Name not configured in config.yaml")
        raise ValueError("MongoDB URI or DB Name not configured.")
    try:
        logger.info(f"Connecting to MongoDB: {uri} (DB: {db_name})")
        mongo_client = MongoClient(uri)
        mongo_client.admin.command('ping')
        mongo_db = mongo_client[db_name]
        logger.info("MongoDB connected successfully.")
        return mongo_db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        raise RuntimeError(f"Could not connect to MongoDB: {e}")

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
def save_results(results, db, collection_name="user_candidate_test"):
    """
    최종 candidate generation 결과를 MongoDB에 저장.
    """
    logger.info(f"Saving {len(results)} user candidate results to MongoDB collection '{collection_name}'...")
    start_time = pd.Timestamp.now()
    try:
        target_collection = db[collection_name]
        from pymongo import UpdateOne
        operations = []
        for res in results:
            user_id = res.get('user_id')
            candidates = res.get('candidates', [])
            filter_query = {'user_id': user_id}
            # user_candidate 스키마에 맞게 저장 필요
            # 예: update_doc = {'$set': {'cust_no': int(user_id), 'curation_list': {cand: 1.0 for cand in candidates}, 'last_updated': pd.Timestamp.now()}}
            update_doc = {'$set': {'candidates': candidates, 'last_updated': pd.Timestamp.now()}} # 단순 저장 예시
            operations.append(UpdateOne(filter_query, update_doc, upsert=True))
        if operations:
            result = target_collection.bulk_write(operations)
            duration = (pd.Timestamp.now() - start_time).total_seconds()
            logger.info(f"Saved results to MongoDB. Matched: {result.matched_count}, Upserted: {result.upserted_count}, Modified: {result.modified_count}. Took {duration:.2f} seconds.")
        else:
             logger.info("No results to save.")
    except Exception as e:
        logger.error(f"Error saving results to MongoDB collection '{collection_name}': {e}", exc_info=True)
        logger.info("Attempting to save results to local file as fallback...")
        try:
            import json
            fallback_file = f"candidate_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(fallback_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Successfully saved results to fallback file: {fallback_file}")
        except Exception as backup_e:
            logger.error(f"Failed to save results to fallback file: {backup_e}")

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