import random
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pymongo.errors import CollectionInvalid # 특정 에러 처리용
from opensearchpy.exceptions import NotFoundError # OpenSearch 인덱스 부재 처리용
from api.db_clients import get_mongo_db, get_os_client
import logging # 로깅 추가
import time # 시간 측정용

logger = logging.getLogger(__name__) # 로거 설정

async def get_bmt_recommendations(cust_no: int) -> List[str]:
    """
    BMT(벤치마크 테스트)를 위한 핵심 로직입니다.

    1. 주어진 cust_no에 대해 MongoDB의 'user_candidate' 컬렉션에서 데이터를 조회합니다. (curation_list 필드만)
    2. 주어진 cust_no에 대해 MongoDB의 'user' 컬렉션에서 데이터를 조회합니다. (_id 필드만, 부하 발생 목적)
    3. 주어진 cust_no에 대해 OpenSearch의 당일 'curation-logs-YYYYMMDD' 인덱스에서 로그를 조회합니다. (size: 0, 부하 발생 목적)
    4. 'user_candidate'에서 가져온 'curation_list'의 키(콘텐츠 ID)들을 무작위로 섞습니다.
    5. 셔플된 콘텐츠 ID 리스트를 반환합니다.

    모든 DB 조회는 부하 테스트 시나리오의 일부로 필수적으로 수행됩니다.
    """
    log_prefix = f"[cust_no={cust_no}]" # 로그 메시지에 고객 번호 포함
    logger.info(f"{log_prefix} Processing BMT recommendations")
    overall_start_time = time.perf_counter() # 전체 함수 시작 시간

    db = get_mongo_db() # DB 클라이언트 가져오기
    os_client = get_os_client() # OS 클라이언트 가져오기

    candidate_ids: List[str] = [] # 최종 반환될 ID 리스트 초기화

    # --- 병렬 DB 조회 함수 정의 ---
    async def fetch_user_candidate() -> Optional[Dict[str, Any]]:
        """MongoDB 'user_candidate' 컬렉션 조회 (curation_list만)"""
        start_time = time.perf_counter()
        logger.debug(f"{log_prefix} Fetching user_candidate...")
        doc = None
        try:
            doc = await db.user_candidate.find_one(
                {"cust_no": cust_no},
                {"curation_list": 1, "_id": 0} # projection 사용
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            status = "Found" if doc else "Not Found"
            logger.debug(f"{log_prefix} Fetched user_candidate in {duration_ms:.2f}ms. Status: {status}")
            return doc
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"{log_prefix} Error fetching user_candidate after {duration_ms:.2f}ms: {e}", exc_info=True)
            return None

    async def fetch_user_info() -> Optional[Dict[str, Any]]:
        """MongoDB 'user' 컬렉션 조회 (_id만, BMT 부하용)"""
        start_time = time.perf_counter()
        logger.debug(f"{log_prefix} Fetching user info...")
        doc = None
        try:
            # CUST_NO 필드명 확인 필요 (스키마 문서에는 대문자였음)
            doc = await db.user.find_one(
                {"CUST_NO": cust_no},
                {"_id": 1} # projection 사용
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            status = "Found" if doc else "Not Found"
            logger.debug(f"{log_prefix} Fetched user info in {duration_ms:.2f}ms. Status: {status}")
            return doc
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"{log_prefix} Error fetching user info after {duration_ms:.2f}ms: {e}", exc_info=True)
            return None

    async def fetch_os_logs() -> Tuple[bool, int]:
        """OpenSearch 'curation-logs-YYYYMMDD' 인덱스 조회 (size:0, BMT 부하용)"""
        start_time = time.perf_counter()
        logger.debug(f"{log_prefix} Fetching os logs...")
        # 실제 인덱스 패턴 확인 필요 (예: '-' 또는 '.' 구분자)
        index_name = f"curation-logs-{datetime.utcnow().strftime('%Y%m%d')}"
        hits_count = 0
        success = False
        try:
            response = await os_client.search(
                index=index_name,
                body={
                    "size": 0, # 실제 문서는 가져오지 않음 (count만 확인 또는 메타데이터만)
                    "query": {
                        "term": {
                            "cust_no": cust_no # 필드명 확인 필요
                        }
                    }
                    # 정렬은 size:0 일때는 불필요할 수 있음
                    # "sort": [ {"timestamp": {"order": "desc"}} ]
                },
                ignore=[404] # 인덱스 없을 때 에러 대신 빈 결과
            )
            hits_count = response.get('hits', {}).get('total', {}).get('value', 0)
            success = True
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"{log_prefix} Fetched os logs in {duration_ms:.2f}ms. Index: {index_name}, Hits: {hits_count}")
            return success, hits_count
        except NotFoundError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(f"{log_prefix} OpenSearch index not found: {index_name} after {duration_ms:.2f}ms")
            return False, 0
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"{log_prefix} Error fetching OpenSearch logs after {duration_ms:.2f}ms, index={index_name}: {e}", exc_info=True)
            return False, 0

    # --- DB 조회 병렬 실행 ---
    gather_start_time = time.perf_counter()
    logger.debug(f"{log_prefix} Starting parallel DB fetches...")
    user_candidate_doc = None # 결과 변수 초기화
    try:
        # await asyncio.gather 로 실행
        results = await asyncio.gather(
            fetch_user_candidate(),
            fetch_user_info(),
            fetch_os_logs()
        )
        gather_duration_ms = (time.perf_counter() - gather_start_time) * 1000
        logger.info(f"{log_prefix} Finished parallel DB fetches in {gather_duration_ms:.2f}ms")

        # 결과 할당 (None 가능성 있음)
        user_candidate_doc, user_info_doc, (os_fetch_success, os_hits_count) = results

    except Exception as e:
        gather_duration_ms = (time.perf_counter() - gather_start_time) * 1000
        logger.error(f"{log_prefix} Critical error during parallel DB fetch after {gather_duration_ms:.2f}ms: {e}", exc_info=True)
        # gather 실패 시 빈 리스트 반환
        return []

    # --- 결과 처리 및 셔플 ---
    shuffle_start_time = time.perf_counter()
    if user_candidate_doc and "curation_list" in user_candidate_doc:
        curation_list_dict: Dict[str, float] = user_candidate_doc.get("curation_list", {})
        if isinstance(curation_list_dict, dict): # 타입 체크
            candidate_ids = list(curation_list_dict.keys())
            if candidate_ids: # ID가 있을 때만 셔플
                logger.debug(f"{log_prefix} Shuffling {len(candidate_ids)} candidate IDs...")
                random.shuffle(candidate_ids)
                shuffle_duration_ms = (time.perf_counter() - shuffle_start_time) * 1000
                logger.debug(f"{log_prefix} Finished shuffling in {shuffle_duration_ms:.4f}ms")
            else:
                logger.debug(f"{log_prefix} No candidate IDs to shuffle.")
                shuffle_duration_ms = (time.perf_counter() - shuffle_start_time) * 1000 # 시간 측정
        else:
            logger.warning(f"{log_prefix} 'curation_list' is not a dictionary. Type: {type(curation_list_dict)}")
            candidate_ids = [] # 형식 오류 시 빈 리스트
            shuffle_duration_ms = (time.perf_counter() - shuffle_start_time) * 1000 # 시간 측정
    else:
        logger.warning(f"{log_prefix} User candidate data not found or 'curation_list' missing.")
        candidate_ids = [] # 데이터 없을 시 빈 리스트
        shuffle_duration_ms = (time.perf_counter() - shuffle_start_time) * 1000 # 시간 측정

    overall_duration_ms = (time.perf_counter() - overall_start_time) * 1000 # 전체 함수 소요 시간
    logger.info(f"{log_prefix} Finished processing BMT recommendations in {overall_duration_ms:.2f}ms, returning {len(candidate_ids)} ids.")
    return candidate_ids