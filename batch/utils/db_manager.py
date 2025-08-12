# simplers/batch/utils/db_manager.py
import logging
from contextlib import contextmanager
from typing import Dict, List, Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import pandas as pd
import dask.dataframe as dd
import dask.bag as dbag
from datetime import datetime

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

def load_contents(db, query: Dict[str, Any] | None = None, partition_size: int = 1000) -> dd.DataFrame:
    """Load content data from MongoDB 'curation' collection into a Dask DataFrame.

    This implementation streams data directly from the MongoDB cursor without
    materialising the entire result set in memory. The optional ``query``
    parameter allows callers to limit the data fetched from MongoDB.
    """
    logger.info("Loading contents from MongoDB 'curation' collection via streaming cursor...")
    start_time = pd.Timestamp.now()
    try:
        curation_coll = db['curation']
        contents_cursor = curation_coll.find(query or {}, batch_size=partition_size)

        def _prepare(doc: Dict[str, Any]) -> Dict[str, Any]:
            doc = dict(doc)
            doc['id'] = str(doc.get('_id'))
            return doc

        bag = dbag.from_sequence(contents_cursor, partition_size=partition_size).map(_prepare)
        ddf = bag.to_dataframe()
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"Created Dask DataFrame for contents in {duration:.2f} seconds.")
        return ddf
    except Exception as e:
        logger.error(f"Error loading contents: {e}", exc_info=True)
        raise


def load_users(
    db,
    last_login_after: datetime | None = None,
    partition_size: int = 1000,
) -> dd.DataFrame:
    """Load user data from MongoDB 'user' collection into a Dask DataFrame.

    The function streams user documents in chunks. If ``last_login_after`` is
    provided, only users whose ``last_login_dt`` is greater than or equal to the
    given datetime are fetched.
    """
    logger.info("Loading users from MongoDB 'user' collection via streaming cursor...")
    start_time = pd.Timestamp.now()
    try:
        user_coll = db['user']
        query: Dict[str, Any] = {}
        if last_login_after is not None:
            query['last_login_dt'] = {'$gte': last_login_after}
        users_cursor = user_coll.find(query, batch_size=partition_size)

        def _prepare(user: Dict[str, Any]) -> Dict[str, Any]:
            user = dict(user)
            user['id'] = str(user.get('_id'))
            user.setdefault('owned_stocks', [])
            return user

        bag = dbag.from_sequence(users_cursor, partition_size=partition_size).map(_prepare)
        ddf = bag.to_dataframe()
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"Created Dask DataFrame for users in {duration:.2f} seconds.")
        return ddf
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
