# simplers/batch/pipeline/final_candidate.py
import logging
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict
import pandas as pd # Timestamp 사용

# 로컬 후보 생성 함수
from batch.pipeline.local_candidate import compute_local_candidates

logger = logging.getLogger(__name__)

def calculate_initial_scores(
    user: Dict[str, Any],
    context: Dict[str, Any],
    global_candidate_ids: Set[str],
    local_candidate_ids: Set[str],
    other_candidate_ids: Set[str]
) -> Dict[str, float]:
    """
    3개의 pool(global, local, other)에 동일한 weight를 주어 점수를 계산합니다.
    """
    user_id = user.get('cust_no', 'UNKNOWN')
    log_prefix = f"[User: {user_id}] [Scoring]"
    logger.debug(f"{log_prefix} Calculating initial scores...")

    all_candidate_ids = global_candidate_ids.union(local_candidate_ids).union(other_candidate_ids)
    if not all_candidate_ids:
        logger.debug(f"{log_prefix} No candidates from any source.")
        return {}

    final_scores = defaultdict(float)
    
    # 3개 pool에 동일한 weight (1.0) 부여
    pool_weight = 1.0

    # 각 pool별로 점수 부여
    for item_id in all_candidate_ids:
        score = 0.0
        if item_id in global_candidate_ids: 
            score += pool_weight
        if item_id in local_candidate_ids: 
            score += pool_weight
        if item_id in other_candidate_ids: 
            score += pool_weight
        
        if score > 0:
            final_scores[item_id] = score

    # 점수 내림차순으로 정렬하여 상위 N개 선택
    max_candidates = context.get('max_candidates_per_user', 100)
    if len(final_scores) > max_candidates:
        logger.debug(f"{log_prefix} Selecting top {max_candidates} candidates from {len(final_scores)}.")
        ranked_items = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)
        top_n_scores = dict(ranked_items[:max_candidates])
        logger.info(f"{log_prefix} Calculated final scores for {len(top_n_scores)} items (Top N).")
        return top_n_scores
    else:
        logger.info(f"{log_prefix} Calculated final scores for {len(final_scores)} items.")
        return dict(final_scores)


def generate_candidate_for_user(
    user: Dict[str, Any],
    global_candidates: List[str],
    other_candidates: List[str],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    글로벌, 로컬, 기타 후보를 생성하고, 동일한 weight로 점수를 계산하여 최종 문서를 생성합니다.
    """
    user_id = user.get('cust_no', 'UNKNOWN_USER')
    log_prefix = f"[User: {user_id}]"
    logger.debug(f"{log_prefix} Generating final candidates and scores...")

    # --- 로컬 후보 생성 ---
    local_candidates = compute_local_candidates(user, context)

    # --- 후보 ID들을 Set으로 변환 ---
    global_candidate_set = set(global_candidates)
    local_candidate_set = set(local_candidates)
    other_candidate_set = set(other_candidates)

    # --- 초기 점수 계산 함수 호출 ---
    initial_scores = calculate_initial_scores(
        user,
        context,
        global_candidate_set,
        local_candidate_set,
        other_candidate_set
    )

    if not initial_scores:
        logger.warning(f"{log_prefix} No candidates with scores generated.")
        return {}

    # --- 결과 문서 생성 (user_candidate 스키마에 맞게) ---
    # curation_list를 [{curation_id: str, score: float}] 형태로 변환
    curation_list = []
    for curation_id, score in initial_scores.items():
        curation_list.append({
            "curation_id": str(curation_id),
            "score": float(score)
        })
    
    # 점수 내림차순으로 정렬
    curation_list.sort(key=lambda x: x["score"], reverse=True)

    result_doc = {
        'cust_no': user.get('cust_no'),
        'curation_list': curation_list,
        'create_dt': pd.Timestamp.now(),
        'modi_dt': pd.Timestamp.now()
    }

    logger.info(f"{log_prefix} Generated final document with {len(curation_list)} scored candidates.")
    return result_doc