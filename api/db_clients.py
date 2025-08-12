# simplers/api/db_clients.py
from common.db import (
    connect_to_mongo,
    close_mongo_connection,
    connect_to_opensearch,
    close_opensearch_connection,
    connect_to_oracle,
    close_oracle_connection,
    get_mongo_db,
    get_os_client,
    get_oracle_pool,
)
