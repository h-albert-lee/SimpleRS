import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, OpenSearch, RequestsHttpConnection
import oracledb

from common.config import MONGO_CONFIG, OPENSEARCH_CONFIG, ORACLE_CONFIG

logger = logging.getLogger(__name__)

# --- Async clients ---
async_mongo_client: Optional[AsyncIOMotorClient] = None
async_mongo_db = None
async_os_client: Optional[AsyncOpenSearch] = None
async_oracle_pool = None

# --- Sync clients ---
mongo_client: Optional[MongoClient] = None
mongo_db = None
os_client: Optional[OpenSearch] = None
oracle_pool = None


# ===== MongoDB =====
async def connect_to_mongo():
    """Connect to MongoDB asynchronously."""
    global async_mongo_client, async_mongo_db
    if async_mongo_db:
        return
    logger.info("Connecting to MongoDB (async)...")
    uri = MONGO_CONFIG.get("uri")
    db_name = MONGO_CONFIG.get("db_name")
    async_mongo_client = AsyncIOMotorClient(uri)
    async_mongo_db = async_mongo_client[db_name]
    await async_mongo_db.command("ping")
    logger.info("MongoDB connected and ping successful.")


def connect_mongo():
    """Connect to MongoDB synchronously."""
    global mongo_client, mongo_db
    if mongo_db:
        return mongo_db
    logger.info("Connecting to MongoDB (sync)...")
    uri = MONGO_CONFIG.get("uri")
    db_name = MONGO_CONFIG.get("db_name")
    mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000, socketTimeoutMS=30000, maxPoolSize=10, retryWrites=True)
    mongo_client.admin.command("ping")
    mongo_db = mongo_client[db_name]
    logger.info("MongoDB connected successfully.")
    return mongo_db


def get_mongo_db():
    if async_mongo_db is not None:
        return async_mongo_db
    if mongo_db is not None:
        return mongo_db
    logger.error("MongoDB requested before connection established.")
    raise RuntimeError("MongoDB is not connected.")


async def close_mongo_connection():
    global async_mongo_client, async_mongo_db
    if async_mongo_client:
        async_mongo_client.close()
        async_mongo_client = None
        async_mongo_db = None
        logger.info("MongoDB async connection closed.")


def close_mongo():
    global mongo_client, mongo_db
    if mongo_client:
        mongo_client.close()
        mongo_client = None
        mongo_db = None
        logger.info("MongoDB sync connection closed.")


# ===== OpenSearch =====
async def connect_to_opensearch():
    """Connect to OpenSearch asynchronously."""
    global async_os_client
    if async_os_client:
        return
    logger.info("Connecting to OpenSearch (async)...")
    hosts = OPENSEARCH_CONFIG.get("hosts")
    http_auth_config = OPENSEARCH_CONFIG.get("http_auth")
    client_args = {
        "hosts": hosts,
        "use_ssl": True,
        "verify_certs": False,
        "ssl_assert_hostname": False,
        "ssl_show_warn": False,
        "connections_per_node": 100,
        "connection_class": AsyncHttpConnection,
    }
    if http_auth_config:
        if isinstance(http_auth_config, dict):
            user = http_auth_config.get("user")
            password = http_auth_config.get("password") or http_auth_config.get("pass")
            if user is not None and password is not None:
                client_args["http_auth"] = (user, password)
        elif isinstance(http_auth_config, (list, tuple)) and len(http_auth_config) == 2:
            client_args["http_auth"] = tuple(http_auth_config)
    async_os_client = AsyncOpenSearch(**client_args)
    if not await async_os_client.ping():
        logger.warning("Failed to ping OpenSearch (async).")
    else:
        logger.info("OpenSearch async connected and ping successful.")


def connect_opensearch():
    """Connect to OpenSearch synchronously."""
    global os_client
    if os_client:
        return os_client
    logger.info("Connecting to OpenSearch (sync)...")
    hosts = OPENSEARCH_CONFIG.get("hosts")
    http_auth_config = OPENSEARCH_CONFIG.get("http_auth")
    client_args = {
        "hosts": hosts,
        "use_ssl": True,
        "verify_certs": False,
        "ssl_assert_hostname": False,
        "ssl_show_warn": False,
        "connection_class": RequestsHttpConnection,
    }
    if http_auth_config:
        if isinstance(http_auth_config, dict):
            user = http_auth_config.get("user")
            password = http_auth_config.get("password") or http_auth_config.get("pass")
            if user is not None and password is not None:
                client_args["http_auth"] = (user, password)
        elif isinstance(http_auth_config, (list, tuple)) and len(http_auth_config) == 2:
            client_args["http_auth"] = tuple(http_auth_config)
    os_client = OpenSearch(**client_args)
    if os_client.ping():
        logger.info("OpenSearch sync connected successfully.")
    else:
        logger.warning("Failed to ping OpenSearch (sync).")
    return os_client


def get_os_client():
    if async_os_client is not None:
        return async_os_client
    if os_client is not None:
        return os_client
    logger.error("OpenSearch client requested before connection established.")
    raise RuntimeError("OpenSearch is not connected.")


async def close_opensearch_connection():
    global async_os_client
    if async_os_client:
        await async_os_client.close()
        async_os_client = None
        logger.info("OpenSearch async connection closed.")


def close_opensearch():
    global os_client
    if os_client is not None:
        os_client = None
        logger.info("OpenSearch sync client object cleared.")


# ===== Oracle DB =====
async def connect_to_oracle():
    """Create Oracle async connection pool."""
    global async_oracle_pool
    if async_oracle_pool:
        return
    logger.info("Connecting to Oracle DB (async)...")
    user = ORACLE_CONFIG.get("user")
    password = ORACLE_CONFIG.get("password")
    dsn = ORACLE_CONFIG.get("dsn")
    encoding = ORACLE_CONFIG.get("encoding", "UTF-8")
    pool_min = ORACLE_CONFIG.get("pool_min", 1)
    pool_max = ORACLE_CONFIG.get("pool_max", 4)
    pool_increment = ORACLE_CONFIG.get("pool_increment", 1)
    pool_timeout = ORACLE_CONFIG.get("pool_timeout", 60)
    async_oracle_pool = await oracledb.create_pool_async(
        user=user,
        password=password,
        dsn=dsn,
        min=pool_min,
        max=pool_max,
        increment=pool_increment,
        getmode=oracledb.POOL_GETMODE_WAIT,
        timeout=pool_timeout,
        encoding=encoding,
    )
    async with async_oracle_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1 FROM DUAL")
            await cursor.fetchone()
    logger.info("Oracle async pool created successfully.")


def connect_oracle():
    """Create Oracle sync connection pool."""
    global oracle_pool
    if oracle_pool:
        return oracle_pool
    logger.info("Connecting to Oracle DB (sync)...")
    user = ORACLE_CONFIG.get("user")
    password = ORACLE_CONFIG.get("password")
    dsn = ORACLE_CONFIG.get("dsn")
    encoding = ORACLE_CONFIG.get("encoding", "UTF-8")
    pool_min = ORACLE_CONFIG.get("pool_min", 1)
    pool_max = ORACLE_CONFIG.get("pool_max", 4)
    pool_increment = ORACLE_CONFIG.get("pool_increment", 1)
    pool_timeout = ORACLE_CONFIG.get("pool_timeout", 60)
    oracle_pool = oracledb.create_pool(
        user=user,
        password=password,
        dsn=dsn,
        min=pool_min,
        max=pool_max,
        increment=pool_increment,
        getmode=oracledb.POOL_GETMODE_WAIT,
        timeout=pool_timeout,
        encoding=encoding,
    )
    with oracle_pool.acquire() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
    logger.info("Oracle sync pool created successfully.")
    return oracle_pool


def get_oracle_pool():
    if async_oracle_pool is not None:
        return async_oracle_pool
    if oracle_pool is not None:
        return oracle_pool
    logger.error("Oracle DB pool requested before connection established.")
    raise RuntimeError("Oracle DB connection pool is not available.")


async def close_oracle_connection():
    global async_oracle_pool
    if async_oracle_pool:
        await async_oracle_pool.close()
        async_oracle_pool = None
        logger.info("Oracle async pool closed.")


def close_oracle():
    global oracle_pool
    if oracle_pool:
        oracle_pool.close()
        oracle_pool = None
        logger.info("Oracle sync pool closed.")
