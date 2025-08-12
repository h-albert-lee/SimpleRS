# simplers/batch/utils/db_manager.py
import logging
from contextlib import contextmanager
from typing import Dict, List, Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import pandas as pd
import dask.dataframe as dd

from batch.utils.config_loader import MONGO_CONFIG
from common.db import (
    connect_mongo, get_mongo_db, close_mongo,
    connect_opensearch, get_os_client, close_opensearch,
    connect_oracle, get_oracle_pool, close_oracle,
)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass


class MongoDBError(DatabaseError):
    """MongoDB related exceptions."""
    pass


class OpenSearchError(DatabaseError):
    """OpenSearch related exceptions."""
    pass


class DataIntegrityError(DatabaseError):
    """Data integrity related exceptions."""
    pass


@contextmanager
def mongodb_connection_context():
    """Context manager for safe MongoDB connections."""
    client = None
    try:
        uri = MONGO_CONFIG.get("uri")
        db_name = MONGO_CONFIG.get("db_name")
        if not uri or not db_name:
            raise MongoDBError("MongoDB URI or DB Name not configured in config.yaml")
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            maxPoolSize=10,
            retryWrites=True,
        )
        client.admin.command("ping")
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


# Data loading functions

def load_contents(db) -> dd.DataFrame:
    """Load content data from MongoDB 'curation' collection into a Dask DataFrame."""
    logger.info("Loading contents from MongoDB 'curation' collection...")
    start_time = pd.Timestamp.now()
    try:
        curation_coll = db['curation']
        contents_cursor = curation_coll.find()
        contents_list = list(contents_cursor)
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
    """Load user data from MongoDB 'user' collection into a Dask DataFrame."""
    logger.info("Loading users from MongoDB 'user' collection...")
    start_time = pd.Timestamp.now()
    try:
        user_coll = db['user']
        users_cursor = user_coll.find()
        users_list = list(users_cursor)
        for user in users_list:
            user['id'] = str(user.get('_id'))
            user.setdefault('owned_stocks', [])
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
    """Load user portfolio information from MongoDB 'user_port' collection."""
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


# Result validation

def validate_candidate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and clean candidate result data."""
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
                    'score': score,
                })
            except (ValueError, TypeError):
                continue

        if valid_curations:
            validated_results.append({'cust_no': cust_no, 'curation_list': valid_curations})
        else:
            invalid_count += 1

    if invalid_count > 0:
        logger.warning(f"Filtered out {invalid_count} invalid results")

    return validated_results
