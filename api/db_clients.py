# simplers/api/db_clients.py
from motor.motor_asyncio import AsyncIOMotorClient
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection
import oracledb # oracledb 임포트
import asyncio # asyncio 임포트
import logging # logging 임포트
from api.config_loader import MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG # ORACLE_CONFIG 임포트

logger = logging.getLogger(__name__) # 로거 설정

# MongoDB 클라이언트
mongo_client: AsyncIOMotorClient = None
mongo_db = None

# OpenSearch 클라이언트
os_client: AsyncOpenSearch = None

# --- Oracle DB 연결 풀 추가 ---
oracle_pool = None

# --- Oracle Client 초기화 (Thick 모드 사용 시) ---
# Thick 모드가 필요하고 설정 파일에 client_lib_dir이 지정된 경우에만 호출
# oracledb 라이브러리 버전에 따라 init_oracle_client 사용 방식이 다를 수 있음
# client_lib_dir = ORACLE_CONFIG.get("client_lib_dir")
# if client_lib_dir:
#     try:
#         logger.info(f"Initializing Oracle Client library from: {client_lib_dir}")
#         # 최신 oracledb 버전에서는 init_oracle_client 호출이 다를 수 있으므로 문서 확인 필요
#         oracledb.init_oracle_client(lib_dir=client_lib_dir)
#     except Exception as e:
#         logger.error(f"Failed to initialize Oracle Client library: {e}", exc_info=True)
#         # 초기화 실패 시 에러를 발생시키거나 경고 후 진행할 수 있음
#         raise RuntimeError("Oracle Client initialization failed.")

async def connect_to_mongo():
    """MongoDB에 연결합니다."""
    global mongo_client, mongo_db
    if mongo_db: # 이미 연결되어 있으면 반환
        return
    logger.info("Connecting to MongoDB...")
    try:
        mongo_client = AsyncIOMotorClient(MONGO_CONFIG.get("uri"))
        mongo_db = mongo_client[MONGO_CONFIG.get("db_name")]
        await mongo_db.command('ping')
        logger.info("MongoDB connected and ping successful.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        mongo_db = None
        raise # 연결 실패 시 에러 발생시켜 애플리케이션 시작 중단

async def close_mongo_connection():
    """MongoDB 연결을 닫습니다."""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed.")

async def connect_to_opensearch():
    """OpenSearch에 연결합니다."""
    global os_client
    if os_client: # 이미 연결되어 있으면 반환
        return
    logger.info("Connecting to OpenSearch...")
    hosts = OPENSEARCH_CONFIG.get("hosts")
    http_auth_config = OPENSEARCH_CONFIG.get("http_auth")

    if not hosts:
        logger.error("OpenSearch hosts configuration is missing.")
        raise ValueError("OpenSearch hosts configuration is missing.") # 에러 발생

    client_args = {
        "hosts": hosts,
        "use_ssl": True,
        "verify_certs": False,
        "ssl_assert_hostname": False,
        "ssl_show_warn": False,
        "connections_per_node": 100, # API 설정값 유지
        "connection_class": AsyncHttpConnection
    }
    # (이하 OpenSearch 인증 로직 동일)
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
            logger.warning("http_auth format is not recognized. Expected dict or tuple/list.")

    try:
        os_client = AsyncOpenSearch(**client_args)
        if not await os_client.ping():
            logger.warning("Failed to ping OpenSearch. Client created but connectivity issue might exist.")
            # 연결은 되었으나 ping 실패 시에도 일단 진행 (API 정책에 따라 에러 발생 가능)
        else:
             logger.info("OpenSearch connected and ping successful.")
    except Exception as e:
        logger.error(f"Failed to connect to OpenSearch or initial ping failed: {e}", exc_info=True)
        os_client = None
        raise # 연결 실패 시 에러 발생

async def close_opensearch_connection():
    """OpenSearch 연결을 닫습니다."""
    global os_client
    if os_client is not None:
        await os_client.close()
        logger.info("OpenSearch connection closed.")

# --- Oracle DB 연결 함수 추가 ---
async def connect_to_oracle():
    """Oracle DB 비동기 연결 풀을 생성합니다."""
    global oracle_pool
    if oracle_pool: # 이미 풀이 생성되어 있으면 반환
        return
    logger.info("Connecting to Oracle DB and creating connection pool...")

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
        raise ValueError("Oracle DB connection info is missing.") # 에러 발생

    try:
        # 비동기 연결 풀 생성
        oracle_pool = await oracledb.create_pool_async(
            user=user,
            password=password,
            dsn=dsn,
            min=pool_min,
            max=pool_max,
            increment=pool_increment,
            getmode=oracledb.POOL_GETMODE_WAIT, # 풀 여유 없을 때 대기
            timeout=pool_timeout,
            encoding=encoding
            # 다른 필요한 파라미터 추가 가능 (예: session_callback)
        )
        # 풀 생성 후 간단한 테스트 쿼리 실행 (선택 사항)
        async with oracle_pool.acquire() as conn:
             async with conn.cursor() as cursor:
                 await cursor.execute("SELECT 1 FROM DUAL")
                 await cursor.fetchone()
        logger.info(f"Oracle DB async connection pool created successfully (min={pool_min}, max={pool_max}). Ping successful.")
    except Exception as e:
        logger.error(f"Failed to create Oracle DB connection pool: {e}", exc_info=True)
        oracle_pool = None
        raise # 풀 생성 실패 시 에러 발생

async def close_oracle_connection():
    """Oracle DB 연결 풀을 닫습니다."""
    global oracle_pool
    if oracle_pool:
        try:
            await oracle_pool.close()
            logger.info("Oracle DB connection pool closed.")
        except Exception as e:
            logger.error(f"Error closing Oracle DB connection pool: {e}", exc_info=True)
        finally:
            oracle_pool = None

def get_mongo_db():
    """MongoDB 데이터베이스 객체를 반환합니다."""
    if mongo_db is None:
        # 이 함수는 연결이 이미 되어있다는 가정 하에 호출되어야 함 (startup에서 연결)
        logger.error("MongoDB requested before connection established.")
        raise RuntimeError("MongoDB is not connected.")
    return mongo_db

def get_os_client():
    """OpenSearch 클라이언트 객체를 반환합니다."""
    if os_client is None:
        logger.error("OpenSearch client requested before connection established.")
        raise RuntimeError("OpenSearch is not connected.")
    return os_client

# --- Oracle 풀 반환 함수 추가 ---
def get_oracle_pool():
    """Oracle DB 연결 풀 객체를 반환합니다."""
    if oracle_pool is None:
        logger.error("Oracle DB pool requested before connection established.")
        raise RuntimeError("Oracle DB connection pool is not available.")
    return oracle_pool