# simplers/batch/utils/cf_utils.py
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity # 코사인 유사도 사용시
from scipy.sparse import csr_matrix # 희소 행렬 사용시
import numpy as np

# 설정 로더에서 CF 관련 설정 임포트
from batch.utils.config_loader import (
    CF_ITEM_SIMILARITY_METRIC, CF_USER_HISTORY_LIMIT, CF_MIN_CO_OCCURRENCE
)

logger = logging.getLogger(__name__)

# --- Item-Item 유사도 매트릭스 ---
item_similarity_matrix: Optional[pd.DataFrame] = None # Pandas DataFrame 사용 예시
item_id_map_cf: Optional[Dict[str, int]] = None # CF용 아이템 ID<->인덱스 맵
item_index_map_cf: Optional[Dict[int, str]] = None

def build_item_similarity(
    user_interactions: Dict[str, List[str]], # {user_id: [item_id1, item_id2, ...]}
    all_item_ids: Optional[List[str]] = None # 전체 아이템 ID 목록 (없으면 interaction 기반)
) -> bool:
    """
    사용자 상호작용 데이터를 기반으로 Item-Item 유사도 매트릭스를 계산합니다.
    결과는 모듈 전역 변수에 저장됩니다.
    """
    global item_similarity_matrix, item_id_map_cf, item_index_map_cf
    logger.info(f"Building Item-Item similarity matrix using metric: {CF_ITEM_SIMILARITY_METRIC}...")
    start_time = pd.Timestamp.now()

    if not user_interactions:
        logger.warning("Cannot build item similarity: user_interactions data is empty.")
        return False

    # --- 1. 아이템-사용자 상호작용 데이터 구조화 ---
    # 모든 등장 아이템 ID 집합 생성
    if all_item_ids:
        unique_item_ids = sorted(list(set(all_item_ids)))
    else:
        all_interacted_items = set()
        for items in user_interactions.values():
            all_interacted_items.update(items)
        if not all_interacted_items:
            logger.warning("No interacted items found in user interactions.")
            return False
        unique_item_ids = sorted(list(all_interacted_items))

    item_id_map_cf = {item_id: i for i, item_id in enumerate(unique_item_ids)}
    item_index_map_cf = {i: item_id for i, item_id in enumerate(unique_item_ids)}
    num_items = len(unique_item_ids)
    logger.debug(f"Total unique items for CF: {num_items}")

    # 아이템별 상호작용한 사용자 Set 생성: {item_id: {user1, user2, ...}}
    item_user_sets = defaultdict(set)
    for user_id, items in user_interactions.items():
        for item_id in set(items): # 사용자의 중복 상호작용은 1번만 카운트
            if item_id in item_id_map_cf: # 매핑에 있는 아이템만 처리
                item_user_sets[item_id].add(user_id)

    # --- 2. 유사도 계산 ---
    similarity_data = defaultdict(dict) # {item_idx1: {item_idx2: score}}

    if CF_ITEM_SIMILARITY_METRIC == "jaccard":
        logger.info("Calculating Jaccard similarity...")
        item_ids_list = list(item_user_sets.keys())
        for i in range(len(item_ids_list)):
            item_id1 = item_ids_list[i]
            users1 = item_user_sets[item_id1]
            idx1 = item_id_map_cf[item_id1]
            for j in range(i, len(item_ids_list)): # 자기 자신 및 이후 아이템과 비교
                item_id2 = item_ids_list[j]
                users2 = item_user_sets[item_id2]
                idx2 = item_id_map_cf[item_id2]

                intersection_count = len(users1.intersection(users2))
                # 최소 동시 등장 횟수 체크
                if intersection_count >= CF_MIN_CO_OCCURRENCE:
                    union_count = len(users1.union(users2))
                    if union_count > 0:
                        sim = intersection_count / union_count
                        if sim > 0: # 유사도 0은 저장 안 함 (메모리 절약)
                            similarity_data[idx1][idx2] = sim
                            if idx1 != idx2: # 대칭 저장
                                similarity_data[idx2][idx1] = sim
        logger.info("Jaccard similarity calculation complete.")

    elif CF_ITEM_SIMILARITY_METRIC == "cosine":
        logger.info("Calculating Cosine similarity using sparse matrix...")
        # 사용자 ID 리스트 및 매핑 생성
        all_user_ids = set()
        for users in item_user_sets.values():
            all_user_ids.update(users)
        user_id_list = sorted(list(all_user_ids))
        user_id_map = {user_id: i for i, user_id in enumerate(user_id_list)}
        num_users = len(user_id_list)

        if num_users == 0:
            logger.warning("No users found in interactions, cannot compute cosine similarity.")
            return False

        # 아이템-사용자 희소 행렬 생성 (아이템이 행, 사용자가 열)
        rows, cols, data = [], [], []
        for item_id, users in item_user_sets.items():
            item_idx = item_id_map_cf[item_id]
            for user_id in users:
                user_idx = user_id_map[user_id]
                rows.append(item_idx)
                cols.append(user_idx)
                data.append(1) # 이진 상호작용

        if not data:
             logger.warning("No interaction data to build sparse matrix.")
             return False

        item_user_matrix = csr_matrix((data, (rows, cols)), shape=(num_items, num_users))
        logger.debug(f"Built Item-User sparse matrix: {item_user_matrix.shape}, Sparsity: {item_user_matrix.nnz / (num_items * num_users):.4f}")

        # 코사인 유사도 계산 (아이템 벡터 간)
        cosine_sim_matrix = cosine_similarity(item_user_matrix, dense_output=False)
        logger.info("Cosine similarity calculation complete.")

        # 결과를 딕셔너리 형태로 변환 (필요시, 또는 매트릭스 직접 사용)
        # 임계값 이하 또는 자기 자신 유사도 제외 가능
        min_similarity_threshold = 0.01 # 예시 임계값
        non_zero_indices = cosine_sim_matrix.nonzero()
        for r, c in zip(*non_zero_indices):
             if r != c: # 자기 자신 제외
                 sim = cosine_sim_matrix[r, c]
                 if sim >= min_similarity_threshold:
                     similarity_data[r][c] = sim

    else:
        logger.error(f"Unsupported item similarity metric: {CF_ITEM_SIMILARITY_METRIC}")
        return False

    # 계산된 유사도 데이터를 DataFrame으로 변환 (메모리 주의)
    # 또는 유사도 데이터를 바로 사용할 수 있는 형태로 유지 (예: 딕셔너리)
    # 여기서는 DataFrame 예시 (메모리 효율적인 방식 고려 필요)
    try:
        item_similarity_matrix = pd.DataFrame.from_dict(similarity_data, orient='index').fillna(0)
        # 인덱스와 컬럼 이름을 실제 아이템 ID로 매핑 (선택 사항)
        # item_similarity_matrix.index = item_similarity_matrix.index.map(item_index_map_cf)
        # item_similarity_matrix.columns = item_similarity_matrix.columns.map(item_index_map_cf)
        logger.info(f"Item similarity matrix built. Shape: {item_similarity_matrix.shape}")
    except Exception as e:
         logger.error(f"Error converting similarity data to DataFrame: {e}", exc_info=True)
         item_similarity_matrix = None # 오류 시 None 처리
         return False


    duration = (pd.Timestamp.now() - start_time).total_seconds()
    logger.info(f"Item similarity build process took {duration:.2f} seconds.")
    return True

# --- 협업 필터링 점수 계산 ---
def get_collaborative_filtering_scores(
    user_history_item_ids: List[str],
    candidate_item_ids: Set[str]
) -> Dict[str, float]:
    """
    사용자의 최근 상호작용 기록과 아이템 유사도 매트릭스를 기반으로
    후보 아이템들에 대한 CF 점수를 계산합니다 (Item-to-Item 방식).
    """
    scores = defaultdict(float)
    if not user_history_item_ids or not candidate_item_ids:
        return dict(scores)
    if item_similarity_matrix is None or item_id_map_cf is None:
        logger.warning("Item similarity matrix not built. Cannot compute CF scores.")
        return dict(scores)

    # 사용자의 최근 상호작용 기록 (제한 적용)
    recent_history = user_history_item_ids[-CF_USER_HISTORY_LIMIT:]
    # 유효한 (유사도 매트릭스에 있는) 사용자 상호작용 아이템 인덱스 추출
    user_interacted_indices = {item_id_map_cf[item_id] for item_id in recent_history if item_id in item_id_map_cf}

    if not user_interacted_indices:
        return dict(scores)

    # 후보 아이템들에 대해 점수 계산
    for cand_id in candidate_item_ids:
        cand_idx = item_id_map_cf.get(cand_id)
        if cand_idx is None: continue # 후보가 유사도 매트릭스에 없으면 스킵
        # 후보 아이템과 사용자가 상호작용한 아이템들 간의 유사도 합산/평균 등
        total_similarity = 0.0
        count = 0
        # 유사도 매트릭스(DataFrame)에서 후보 아이템(cand_idx)과 관련된 유사도 조회
        if cand_idx in item_similarity_matrix.index:
            # 후보 아이템 행(row) 가져오기
            sim_row = item_similarity_matrix.loc[cand_idx]
            for hist_idx in user_interacted_indices:
                if hist_idx in sim_row.index: # 상호작용 아이템이 유사도 row의 컬럼(인덱스)에 있는지 확인
                    similarity = sim_row[hist_idx]
                    if similarity > 0:
                        total_similarity += similarity
                        count += 1

        # 점수 계산 방식 (예: 유사도 합)
        if count > 0:
             # 점수 정규화 또는 스케일링 필요시 적용
             final_score = total_similarity # 또는 total_similarity / count 등
             scores[cand_id] = max(0.0, float(final_score)) # 음수 방지

    return dict(scores)