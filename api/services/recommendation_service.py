# simplers/api/services/recommendation_service.py

import logging
import time
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime, timedelta
from bson import ObjectId # MongoDB ObjectId 사용 시 필요
from opensearchpy.exceptions import NotFoundError # OpenSearch 에러 처리용
import random # random 임포트 추가

# rules 및 db_clients 임포트 (경로 확인 필요)
from api.rules import PRE_RANKING_RULES, POST_RANKING_RULES
from api.db_clients import get_mongo_db, get_os_client

# 실제 랭킹 모델이 있다면 임포트
# from api.ranking_model import YourRankingModel

logger = logging.getLogger(__name__)

# --- 데이터 로딩 헬퍼 함수들 (DB 직접 조회 버전, 캐싱 고려 필요) ---

async def fetch_user_profile_data(cust_no: int, db) -> Dict[str, Any]:
    """MongoDB에서 사용자 기본 정보 로드"""
    log_prefix = f"[cust_no={cust_no}]"
    logger.debug(f"{log_prefix} Fetching user profile data from DB...")
    start_time = time.perf_counter()
    user_profile = {}
    try:
        # CUST_NO 필드명 확인 필요
        user_profile_doc = await db.user.find_one({"CUST_NO": cust_no})
        if user_profile_doc:
             # ObjectId 등 BSON 타입을 JSON 호환 가능하게 변환 (필요시)
             if '_id' in user_profile_doc:
                 user_profile_doc['_id'] = str(user_profile_doc['_id'])
             if 'last_login_dt' in user_profile_doc and isinstance(user_profile_doc['last_login_dt'], datetime):
                 user_profile_doc['last_login_dt'] = user_profile_doc['last_login_dt'].isoformat()
             if 'last_upd_dt' in user_profile_doc and isinstance(user_profile_doc['last_upd_dt'], datetime):
                 user_profile_doc['last_upd_dt'] = user_profile_doc['last_upd_dt'].isoformat()
             user_profile = user_profile_doc
        else:
             user_profile = {}
    except Exception as e:
        logger.error(f"{log_prefix} Error fetching user profile: {e}", exc_info=True)
        user_profile = {} # 에러 시 빈 dict 반환
    duration_ms = (time.perf_counter() - start_time) * 1000
    found_status = "Found" if user_profile else "Not Found"
    logger.debug(f"{log_prefix} User profile fetch from DB took {duration_ms:.2f}ms. Status: {found_status}")
    return user_profile

async def fetch_seen_items(cust_no: int, os_client) -> Set[str]:
    """OpenSearch curation-logs 에서 본 콘텐츠 ID 로드 (캐싱 강력 권장!)"""
    log_prefix = f"[cust_no={cust_no}]"
    logger.debug(f"{log_prefix} Fetching seen items from OpenSearch...")
    start_time = time.perf_counter()
    seen_items_set = set()
    # 성능을 위해 최근 N일치만 조회하거나 캐싱 사용 필수
    # 여기서는 예시로 최근 3일치만 조회
    days_to_check = 3
    tasks = []

    # 최근 N일 인덱스 병렬 조회
    for i in range(days_to_check):
        target_date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y%m%d')
        index_name = f"curation-logs-{target_date}" # 인덱스 패턴 확인!
        tasks.append(
            os_client.search(
                index=index_name,
                size=500, # 하루 최대 조회 수 (조정 필요)
                _source=["curation_id"],
                body={"query": {"term": {"cust_no": cust_no}}}, # cust_no 필드명 확인!
                ignore=[404], # 인덱스 없어도 에러 아님
                request_timeout=0.5 # 짧은 타임아웃
            )
        )

    # 병렬 실행 및 결과 처리
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            # 타임아웃 또는 기타 에러 로깅
            if isinstance(result, asyncio.TimeoutError):
                 logger.warning(f"{log_prefix} Timeout fetching seen items from an index.")
            elif not isinstance(result, NotFoundError): # NotFoundError는 예상 가능하므로 로깅 안 함
                 logger.warning(f"{log_prefix} Failed to fetch seen items from an index: {result}", exc_info=result)
            continue # 에러 발생 시 해당 인덱스는 건너뜀

        # 성공 시 결과 처리
        for hit in result.get('hits', {}).get('hits', []):
            if '_source' in hit and 'curation_id' in hit['_source']:
                curation_id_val = hit['_source']['curation_id']
                if curation_id_val: # Null이나 빈 문자열 제외
                    seen_items_set.add(curation_id_val)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(f"{log_prefix} Found {len(seen_items_set)} seen items in {duration_ms:.2f}ms (from OpenSearch over {days_to_check} indices).")
    return seen_items_set

async def fetch_user_stock_lists(cust_no: int) -> Dict[str, Set[str]]:
    """사용자 관련 주식 목록 로드 (!!! 현재 Dummy 구현 !!!)"""
    # !!! 중요: 이 부분은 실제 DB 또는 캐시 조회 로직으로 반드시 대체되어야 합니다 !!!
    log_prefix = f"[cust_no={cust_no}]"
    logger.warning(f"{log_prefix} Fetching user stock lists using DUMMY data!")
    start_time = time.perf_counter()
    await asyncio.sleep(0.001) # 임시 지연
    # 실제로는 DB 조회 후 Set으로 변환 필요
    data = {
        "owned_stocks_set": {"005930", "035720"}, # 예시: 삼성전자, 카카오
        "recent_stocks_set": {"000660"},          # 예시: SK하이닉스
        "group1_stocks_set": {"005380"},          # 예시: 현대차
        "onboarding_stocks_set": {"005930"}       # 예시: 삼성전자
    }
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(f"{log_prefix} Dummy user stock lists fetch took {duration_ms:.2f}ms")
    return data

async def fetch_owned_stock_returns(owned_stocks: Set[str], os_client) -> Dict[str, Dict[str, Optional[float]]]:
    """보유 주식 수익률 정보 로드 (OpenSearch screen-* 조회, 캐싱 권장)"""
    log_prefix = "[fetch_owned_stock_returns]" # cust_no 없으므로 별도 접두사
    logger.debug(f"{log_prefix} Fetching returns for {len(owned_stocks)} owned stocks from OpenSearch...")
    start_time = time.perf_counter()
    stock_returns = {}
    if not owned_stocks:
        logger.debug(f"{log_prefix} No owned stocks provided to fetch returns.")
        return {}

    # 오늘 날짜 인덱스 이름 생성 (인덱스 패턴 확인!)
    index_name = f"screen-{datetime.utcnow().strftime('%Y%m%d')}"

    try:
        # terms 쿼리를 사용하여 여러 종목 정보 한 번에 조회
        response = await os_client.search(
            index=index_name,
            size=len(owned_stocks), # 보유 종목 수만큼 조회 시도
            _source=["shrt_code", "1m_returns", "1d_returns"], # 필요한 필드만
            body={
                "query": {
                    "terms": {
                        # shrt_code 필드가 keyword 타입일 경우 .keyword 추가 필요할 수 있음
                        # 예: "shrt_code.keyword"
                        "shrt_code": list(owned_stocks)
                    }
                }
            },
            ignore=[404], # 인덱스 없을 경우 에러 아님
            request_timeout=0.8 # 타임아웃 설정 (0.8초)
        )
        fetched_count = 0
        for hit in response.get('hits', {}).get('hits', []):
            if '_source' in hit:
                source = hit['_source']
                code = source.get('shrt_code')
                # code가 None이 아니고, 요청한 보유 주식 목록에 있는지 확인
                if code and code in owned_stocks:
                    stock_returns[code] = {
                        '1m_returns': source.get('1m_returns'), # 값이 없으면 None
                        '1d_returns': source.get('1d_returns')  # 값이 없으면 None
                    }
                    fetched_count += 1
        logger.debug(f"{log_prefix} Fetched return data for {fetched_count} / {len(owned_stocks)} stocks from index {index_name}")

    except asyncio.TimeoutError:
        logger.warning(f"{log_prefix} Timeout fetching stock returns from index {index_name}")
    except NotFoundError:
         logger.warning(f"{log_prefix} Stock return index not found: {index_name}")
    except Exception as e:
        logger.error(f"{log_prefix} Failed to fetch stock returns from index {index_name}: {e}", exc_info=True)

    # 조회되지 않은 보유 주식 처리 (기본값 설정)
    for stock in owned_stocks:
        if stock not in stock_returns:
            stock_returns[stock] = {'1m_returns': None, '1d_returns': None}

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(f"{log_prefix} Owned stock returns fetch from OpenSearch took {duration_ms:.2f}ms")
    return stock_returns


async def fetch_content_metadata(item_ids: List[str], db) -> Dict[str, Dict[str, Any]]:
    """콘텐츠 메타데이터 로드 (MongoDB curation 조회, 캐싱 필수!)"""
    log_prefix = "[fetch_content_metadata]"
    logger.debug(f"{log_prefix} Fetching metadata for {len(item_ids)} items from MongoDB...")
    start_time = time.perf_counter()
    content_meta = {}
    if not item_ids:
        logger.debug(f"{log_prefix} No item IDs provided to fetch metadata.")
        return {}

    # item_ids (문자열)를 ObjectId로 변환 시도
    object_ids = []
    invalid_ids = []
    valid_str_ids = [] # ObjectId 변환 실패 시 원본 ID 저장
    for item_id in item_ids:
        try:
            object_ids.append(ObjectId(item_id))
            valid_str_ids.append(item_id)
        except Exception:
            invalid_ids.append(item_id)

    if invalid_ids:
        logger.warning(f"{log_prefix} Invalid ObjectId format found in item_ids: {invalid_ids}")

    if not object_ids:
         logger.warning(f"{log_prefix} No valid ObjectIds to query for metadata.")
         return {}

    try:
        # $in 쿼리로 한 번에 조회
        cursor = db.curation.find(
            {"_id": {"$in": object_ids}},
            # 필요한 필드만 명시적으로 가져오기
            {"label": 1, "title": 1, "category": 1, "_id": 1} # category 필드 추가 예시
        )
        fetched_count = 0
        # motor cursor는 to_list() 또는 async for 사용
        async for doc in cursor: # 대량 데이터 처리 시 to_list()보다 효율적일 수 있음
            # MongoDB _id 는 ObjectId 객체이므로 다시 문자열로 변환하여 key로 사용
            item_id_str = str(doc['_id'])
            content_meta[item_id_str] = {
                "_id": item_id_str, # 문자열 ID 저장
                "label": doc.get("label"), # 주식 코드
                "title": doc.get("title"),
                "category": doc.get("category") # 규칙에서 사용할 카테고리
            }
            fetched_count += 1
        logger.debug(f"{log_prefix} Fetched metadata for {fetched_count} / {len(object_ids)} items from DB.")

    except Exception as e:
        logger.error(f"{log_prefix} Failed to fetch content metadata from MongoDB: {e}", exc_info=True)

    # 조회되지 않은 ID에 대한 처리 (선택 사항)
    # for item_id_str in valid_str_ids:
    #     if item_id_str not in content_meta:
    #         content_meta[item_id_str] = {"_id": item_id_str} # 최소한의 정보라도 넣어주기

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(f"{log_prefix} Content metadata fetch from MongoDB took {duration_ms:.2f}ms")
    return content_meta


async def fetch_user_context_data(cust_no: int) -> Dict[str, Any]:
    """API 요청 처리에 필요한 모든 컨텍스트 데이터를 병렬로 로드하고 통합합니다."""
    start_time = time.perf_counter()
    log_prefix = f"[cust_no={cust_no}]"
    logger.debug(f"{log_prefix} Fetching user context data (parallel)...")
    db = get_mongo_db()
    os_client = get_os_client()

    # 병렬 조회 항목 정의
    tasks = {
        "profile": fetch_user_profile_data(cust_no, db),
        "seen": fetch_seen_items(cust_no, os_client),
        "stocks": fetch_user_stock_lists(cust_no), # Dummy 사용 중
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    context_data = {"cust_no": cust_no}
    task_keys = list(tasks.keys())
    for i, result in enumerate(results):
        key = task_keys[i]
        if isinstance(result, Exception):
            logger.error(f"{log_prefix} Error fetching context data for '{key}': {result}", exc_info=result)
            # 에러 발생 시 기본값 설정
            if key == "profile": context_data[key] = {}
            elif key == "seen": context_data["seen_items_set"] = set()
            elif key == "stocks": context_data.update({k: set() for k in ["owned_stocks_set", "recent_stocks_set", "group1_stocks_set", "onboarding_stocks_set"]})
        else:
            # 성공 시 데이터 할당
            if key == "profile": context_data[key] = result
            elif key == "seen": context_data["seen_items_set"] = result # 키 이름 변경
            elif key == "stocks": context_data.update(result) # 결과 딕셔너리 업데이트

    # 보유 주식 수익률 조회 (보유 주식 목록이 있어야 가능)
    owned_stocks = context_data.get("owned_stocks_set", set())
    if owned_stocks:
        try:
            # 수익률 조회 함수 호출
            context_data["owned_stock_returns"] = await fetch_owned_stock_returns(owned_stocks, os_client)
        except Exception as e:
             logger.error(f"{log_prefix} Error fetching owned stock returns: {e}", exc_info=True)
             context_data["owned_stock_returns"] = {}
    else:
        context_data["owned_stock_returns"] = {} # 보유 주식 없으면 빈 딕셔너리

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"{log_prefix} Fetched user context data in {duration_ms:.2f}ms")
    return context_data


async def fetch_initial_candidates_with_scores(cust_no: int, db) -> List[Tuple[str, float]]:
    """초기 후보군과 점수 로드 (user_candidate 사용)"""
    log_prefix = f"[cust_no={cust_no}]"
    logger.debug(
        f"{log_prefix} Fetching initial candidates with scores from user_candidate..."
    )
    start_time = time.perf_counter()
    candidates_with_scores: List[Tuple[str, float]] = []
    try:
        doc = await db.user_candidate.find_one(
            {"cust_no": cust_no}, {"curation_list": 1, "_id": 0}
        )
        if doc and isinstance(doc.get("curation_list"), dict):
            for item_id, score in doc["curation_list"].items():
                try:
                    candidates_with_scores.append((item_id, float(score)))
                except (ValueError, TypeError):
                    logger.warning(
                        f"{log_prefix} Invalid score format for item {item_id}: {score}. Using 0.0."
                    )
                    candidates_with_scores.append((item_id, 0.0))
        else:
            logger.warning(
                f"{log_prefix} No initial candidates found in user_candidate or format invalid."
            )
    except Exception as e:
        logger.error(f"{log_prefix} Error fetching initial candidates: {e}", exc_info=True)

    if not candidates_with_scores:
        for coll in ["curation_hist", "curation"]:
            try:
                cursor = (
                    db[coll]
                    .find({}, {"_id": 1})
                    .sort("created_at", -1)
                    .limit(100)
                )
                docs = await cursor.to_list(length=100)
                if docs:
                    candidates_with_scores = [(str(doc["_id"]), 0.0) for doc in docs]
                    logger.warning(
                        f"{log_prefix} Falling back to {coll} for {len(candidates_with_scores)} candidates."
                    )
                    break
            except Exception as fallback_err:
                logger.error(
                    f"{log_prefix} Fallback to {coll} failed: {fallback_err}",
                    exc_info=True,
                )

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        f"{log_prefix} Initial candidates fetch took {duration_ms:.2f}ms. Count: {len(candidates_with_scores)}"
    )
    return candidates_with_scores

# --- 메인 추천 서비스 함수 ---
async def get_live_recommendations(cust_no: int) -> List[Tuple[str, float]]:
    """ 규칙 기반 실시간 추천 생성 (ID와 점수 반환) """
    log_prefix = f"[cust_no={cust_no}]"
    logger.info(f"{log_prefix} Processing live recommendations...")
    overall_start_time = time.perf_counter()

    db = get_mongo_db() # DB 클라이언트 한 번만 가져오기

    # --- 1. 사용자 컨텍스트 및 초기 후보군+점수 준비 ---
    # gather 내에서 db 클라이언트를 인자로 전달
    user_context, initial_candidates_with_scores = await asyncio.gather(
        fetch_user_context_data(cust_no), # 내부에서 db, os 클라이언트 가져옴
        fetch_initial_candidates_with_scores(cust_no, db)
    )

    if not initial_candidates_with_scores:
         logger.warning(f"{log_prefix} No initial candidates found. Returning empty list.")
         return []

    initial_candidates = [item_id for item_id, score in initial_candidates_with_scores]
    logger.debug(f"{log_prefix} Initial candidates count: {len(initial_candidates)}")

    # --- 2. Pre-Ranking 규칙 적용 (후보 ID 리스트 필터링) ---
    candidates_after_pre_rules = initial_candidates
    logger.debug(f"{log_prefix} Applying pre-ranking rules...")
    pre_rules_start_time = time.perf_counter()
    for rule in PRE_RANKING_RULES:
        rule_start = time.perf_counter()
        try:
            # apply 호출 시 user_context와 후보 리스트 전달
            candidates_after_pre_rules = await rule.apply(user_context, candidates_after_pre_rules)
            rule_duration = (time.perf_counter() - rule_start) * 1000
            logger.debug(f"{log_prefix} Applied rule '{rule.rule_name}' in {rule_duration:.2f}ms. Candidates: {len(candidates_after_pre_rules)}")
        except Exception as e:
            logger.error(f"{log_prefix} Error applying pre-rank rule {rule.rule_name}: {e}", exc_info=True)

    pre_rules_duration_ms = (time.perf_counter() - pre_rules_start_time) * 1000
    logger.info(f"{log_prefix} Finished pre-ranking rules in {pre_rules_duration_ms:.2f}ms. Candidates after pre-rules: {len(candidates_after_pre_rules)}")

    if not candidates_after_pre_rules:
         logger.warning(f"{log_prefix} No candidates left after pre-ranking rules.")
         return []

    # --- 3. Post-Rank 규칙 적용을 위한 초기 아이템-점수 목록 준비 ---
    candidate_set_after_pre = set(candidates_after_pre_rules)
    # 초기 점수 유지, 필터링된 후보만 포함
    ranked_items_before_post_rules = [
        (item_id, score) for item_id, score in initial_candidates_with_scores
        if item_id in candidate_set_after_pre
    ]
    logger.debug(f"{log_prefix} Prepared {len(ranked_items_before_post_rules)} items with initial scores for post-ranking rules.")

    # --- 3.5 콘텐츠 메타데이터 로드 (Post-Rank 규칙 필요 데이터) ---
    ids_for_meta = [item_id for item_id, score in ranked_items_before_post_rules]
    logger.debug(f"{log_prefix} Fetching metadata for {len(ids_for_meta)} items before post-ranking rules.")
    # 메타데이터 로드 시 DB 클라이언트 전달
    content_meta_map = await fetch_content_metadata(ids_for_meta, db)
    user_context["content_meta"] = content_meta_map # 컨텍스트 업데이트

    # --- 4. Post-Ranking 규칙 적용 (점수 조정 및 정렬) ---
    final_ranked_items = ranked_items_before_post_rules
    logger.debug(f"{log_prefix} Applying post-ranking rules...")
    post_rules_start_time = time.perf_counter()
    for rule in POST_RANKING_RULES:
        rule_start = time.perf_counter()
        try:
             # apply 호출 시 user_context와 (ID, 점수) 리스트 전달
            final_ranked_items = await rule.apply(user_context, final_ranked_items)
            rule_duration = (time.perf_counter() - rule_start) * 1000
            logger.debug(f"{log_prefix} Applied rule '{rule.rule_name}' in {rule_duration:.2f}ms. Items: {len(final_ranked_items)}")
        except Exception as e:
            logger.error(f"{log_prefix} Error applying post-rank rule {rule.rule_name}: {e}", exc_info=True)

    post_rules_duration_ms = (time.perf_counter() - post_rules_start_time) * 1000
    logger.info(f"{log_prefix} Finished post-ranking rules in {post_rules_duration_ms:.2f}ms. Final items: {len(final_ranked_items)}")

    # 최종 정렬 (AddScoreNoiseRule 등 순서에 영향을 주는 규칙 적용 후 필수)
    final_ranked_items.sort(key=lambda x: x[1], reverse=True)

    # --- 5. 최종 결과 반환 (ID와 점수) ---
    RECOMMENDATION_COUNT = 20 # 최종 반환 개수 (조정 가능)
    final_result = final_ranked_items[:RECOMMENDATION_COUNT]

    overall_duration_ms = (time.perf_counter() - overall_start_time) * 1000
    logger.info(f"{log_prefix} Finished live recommendations in {overall_duration_ms:.2f}ms. Returning {len(final_result)} items with scores.")
    return final_result # (ID, 점수) 튜플 리스트 반환


# --- 비로그인 사용자 추천 로직 ---
async def get_anonymous_recommendations() -> List[str]:
    """
    비로그인 사용자를 위한 추천 목록을 생성합니다.
    MongoDB의 'global_data' 컬렉션에서 미리 정의된 목록을 가져와 셔플합니다.
    """
    log_prefix = "[Anonymous]"
    logger.info(f"{log_prefix} Processing anonymous recommendations...")
    start_time = time.perf_counter()

    db = get_mongo_db()
    recommendation_ids = []

    try:
        # MongoDB에서 비로그인 추천 목록 조회 (컬렉션/도큐먼트/필드 이름 확인 필요!)
        collection_name = "global_data" # 예시 컬렉션 이름
        document_id = "anonymous_recs" # 예시 도큐먼트 ID
        field_name = "curation_ids"    # 예시 필드 이름

        query_start_time = time.perf_counter()
        # 실제 DB 조회
        anonymous_recs_doc = await db[collection_name].find_one({"_id": document_id})
        query_duration_ms = (time.perf_counter() - query_start_time) * 1000
        logger.debug(f"{log_prefix} Fetched doc '{document_id}' from '{collection_name}' in {query_duration_ms:.2f}ms")

        if anonymous_recs_doc and field_name in anonymous_recs_doc:
            raw_ids = anonymous_recs_doc.get(field_name, [])
            if isinstance(raw_ids, list):
                recommendation_ids = list(raw_ids) # 복사
                logger.debug(f"{log_prefix} Found {len(recommendation_ids)} initial anonymous recommendations.")

                # 리스트 셔플
                shuffle_start_time = time.perf_counter()
                random.shuffle(recommendation_ids)
                shuffle_duration_ms = (time.perf_counter() - shuffle_start_time) * 1000
                logger.debug(f"{log_prefix} Shuffled recommendations in {shuffle_duration_ms:.4f}ms.")
            else:
                logger.warning(f"{log_prefix} Field '{field_name}' is not a list in doc '{document_id}'.")
        else:
            logger.warning(f"{log_prefix} Doc '{document_id}' not found or field '{field_name}' missing.")

    except Exception as e:
        logger.error(f"{log_prefix} Error processing anonymous recommendations: {e}", exc_info=True)
        recommendation_ids = [] # 오류 발생 시 빈 리스트 반환

    overall_duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"{log_prefix} Finished processing anonymous recommendations in {overall_duration_ms:.2f}ms. Returning {len(recommendation_ids)} items.")

    RECOMMENDATION_COUNT = 20  # 최종 반환 개수 제한
    return recommendation_ids[:RECOMMENDATION_COUNT]
