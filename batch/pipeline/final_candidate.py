# simplers/batch/pipeline/final_candidate.py
import logging
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict
import pandas as pd # Timestamp 사용

# 로컬 후보 생성 함수
from batch.pipeline.local_candidate import compute_local_candidates
# 스코어링 설정을 위한 config 로더
from batch.utils.config_loader import (
    SOURCE_WEIGHTS, CF_WEIGHT, CB_WEIGHT, MIN_SCORE_THRESHOLD, MAX_CANDIDATES_PER_USER
)
# CF/CB 유틸리티 임포트
from batch.utils.cf_utils import get_collaborative_filtering_scores
from batch.utils.cb_utils import compute_user_profile_vector, get_content_based_scores

logger = logging.getLogger(__name__)

def calculate_initial_scores(
    user: Dict[str, Any],
    context: Dict[str, Any],
    global_candidate_ids: Set[str],
    cluster_candidate_ids: Set[str],
    local_candidate_ids: Set[str]
) -> Dict[str, float]:
    """
    다양한 소스 후보 + CF + CB 점수를 조합하여 초기 점수를 계산합니다.
    """
    user_id = user.get('id', 'UNKNOWN')
    log_prefix = f"[User: {user_id}] [Scoring]"
    logger.debug(f"{log_prefix} Calculating initial scores...")

    all_candidate_ids = global_candidate_ids.union(cluster_candidate_ids).union(local_candidate_ids)
    if not all_candidate_ids:
        logger.debug(f"{log_prefix} No candidates from any source.")
        return {}

    item_scores = defaultdict(float)
    base_scores = defaultdict(float) # 소스 가중치 기반 점수

    # --- 1. 소스별 가중치 기반 점수 계산 ---
    weight_global = SOURCE_WEIGHTS.get("global", 0.1)
    weight_cluster = SOURCE_WEIGHTS.get("cluster", 0.1)
    weight_local = SOURCE_WEIGHTS.get("local", 0.1)

    for item_id in all_candidate_ids:
        score = 0.0
        if item_id in global_candidate_ids: score += weight_global
        if item_id in cluster_candidate_ids: score += weight_cluster
        if item_id in local_candidate_ids: score += weight_local
        base_scores[item_id] = score

    # --- 2. CF 점수 계산 ---
    cf_scores = {}
    if CF_WEIGHT > 0:
        # 컨텍스트에서 사용자 상호작용 기록 가져오기
        user_interactions = context.get('user_interactions', {}) # {user_id: [item_id1,...]} 형태 가정
        user_history = user_interactions.get(user_id, [])
        if user_history:
            try:
                # get_collaborative_filtering_scores 는 {item_id: score} 반환
                cf_scores = get_collaborative_filtering_scores(user_history, all_candidate_ids)
                logger.debug(f"{log_prefix} Calculated CF scores for {len(cf_scores)} items.")
            except Exception as e:
                logger.error(f"{log_prefix} Error calculating CF scores: {e}", exc_info=True)
        else:
            logger.debug(f"{log_prefix} No user history found for CF calculation.")


    # --- 3. CB 점수 계산 ---
    cb_scores = {}
    if CB_WEIGHT > 0:
        user_interactions = context.get('user_interactions', {})
        user_history = user_interactions.get(user_id, [])
        if user_history:
            try:
                # 사용자 프로필 벡터 계산
                user_profile_vector = compute_user_profile_vector(user_history)
                if user_profile_vector is not None:
                    # CB 점수 계산
                    cb_scores = get_content_based_scores(user_profile_vector, all_candidate_ids)
                    logger.debug(f"{log_prefix} Calculated CB scores for {len(cb_scores)} items.")
                else:
                    logger.debug(f"{log_prefix} Could not compute user profile vector for CB.")
            except Exception as e:
                 logger.error(f"{log_prefix} Error calculating CB scores: {e}", exc_info=True)
        else:
             logger.debug(f"{log_prefix} No user history found for CB calculation.")

    # --- 4. 최종 점수 조합 ---
    final_scores = defaultdict(float)
    for item_id in all_candidate_ids:
        final_score = base_scores.get(item_id, 0.0) \
                    + CF_WEIGHT * cf_scores.get(item_id, 0.0) \
                    + CB_WEIGHT * cb_scores.get(item_id, 0.0)

        # (확장 지점) 인기도/최신성 등 다른 점수 추가 가능
        # final_score += calculate_popularity_score(item_id, context) * POPULARITY_WEIGHT

        # 최소 점수 임계값 필터링
        if final_score >= MIN_SCORE_THRESHOLD:
            final_scores[item_id] = final_score

    # --- 5. 상위 N개 후보 선정 ---
    if len(final_scores) > MAX_CANDIDATES_PER_USER:
        logger.debug(f"{log_prefix} Selecting top {MAX_CANDIDATES_PER_USER} candidates from {len(final_scores)}.")
        ranked_items = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)
        top_n_scores = dict(ranked_items[:MAX_CANDIDATES_PER_USER])
        logger.info(f"{log_prefix} Calculated final scores for {len(top_n_scores)} items (Top N).")
        return top_n_scores
    else:
        logger.info(f"{log_prefix} Calculated final scores for {len(final_scores)} items.")
        return dict(final_scores)


def generate_candidate_for_user(
    user: Dict[str, Any],
    global_candidates: List[str],
    cluster_candidates_map: Dict[str, List[str]],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    글로벌, 클러스터, 로컬 후보를 생성하고, 초기 점수를 계산하여 최종 문서를 생성합니다.
    """
    user_id = user.get('id', 'UNKNOWN_USER')
    log_prefix = f"[User: {user_id}]"
    logger.debug(f"{log_prefix} Generating final candidates and scores...")

    # --- 로컬 후보 생성 ---
    local_candidates = compute_local_candidates(user, context)

    # --- 클러스터 후보 가져오기 ---
    user_cluster = str(user.get('cluster_id', 'default'))
    cluster_candidates = cluster_candidates_map.get(user_cluster, [])

    # --- 후보 ID들을 Set으로 변환 ---
    global_candidate_set = set(global_candidates)
    cluster_candidate_set = set(cluster_candidates)
    local_candidate_set = set(local_candidates)

    # --- 초기 점수 계산 함수 호출 ---
    initial_scores = calculate_initial_scores(
        user,
        context,
        global_candidate_set,
        cluster_candidate_set,
        local_candidate_set
    )

    if not initial_scores:
        logger.warning(f"{log_prefix} No candidates with scores generated.")

    # --- 결과 문서 생성 ---
    result_doc = {
        'cust_no': user.get('CUST_NO') if isinstance(user.get('CUST_NO'), int) else int(user_id) if user_id.isdigit() else None,
        'curation_list': initial_scores,
        'last_updated': pd.Timestamp.now()
    }
    if result_doc['cust_no'] is None:
         # logger.warning(f"{log_prefix} Could not determine numeric cust_no for user. Saving without it.")
         del result_doc['cust_no']
         result_doc['user_id_str'] = user_id # 문자열 ID 추가 (대체 키)

    logger.info(f"{log_prefix} Generated final document with {len(initial_scores)} scored candidates.")
    return result_doc