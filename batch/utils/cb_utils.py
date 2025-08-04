# simplers/batch/utils/cb_utils.py
import logging
from typing import Dict, List, Any, Optional, Set
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# 설정 로더에서 CB 관련 설정 임포트
from batch.utils.config_loader import CB_TFIDF_FIELDS, CB_USER_HISTORY_LIMIT

logger = logging.getLogger(__name__)

# --- TF-IDF 기반 콘텐츠 벡터 생성 ---
tfidf_vectorizer: Optional[TfidfVectorizer] = None
item_tfidf_vectors: Optional[np.ndarray] = None
item_id_to_index: Optional[Dict[str, int]] = None
index_to_item_id: Optional[Dict[int, str]] = None

def build_tfidf_vectors(contents_list: List[Dict[str, Any]]) -> bool:
    """
    콘텐츠 리스트로부터 TF-IDF 벡터라이저를 학습시키고 아이템 벡터를 생성합니다.
    결과는 모듈 전역 변수에 저장됩니다.
    """
    global tfidf_vectorizer, item_tfidf_vectors, item_id_to_index, index_to_item_id
    logger.info(f"Building TF-IDF vectors for {len(contents_list)} items using fields: {CB_TFIDF_FIELDS}...")
    start_time = pd.Timestamp.now()

    if not contents_list:
        logger.warning("Cannot build TF-IDF vectors: contents_list is empty.")
        return False

    # TF-IDF 계산에 사용할 텍스트 데이터 추출 및 결합
    corpus = []
    item_ids = []
    valid_content_indices = [] # 유효한 콘텐츠의 원본 인덱스
    for i, content in enumerate(contents_list):
        text_parts = []
        # 설정된 필드에서 텍스트 추출 (None 값 제외)
        for field in CB_TFIDF_FIELDS:
            value = content.get(field)
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            elif isinstance(value, list): # 필드가 리스트인 경우 (예: 태그)
                 text_parts.extend([str(v) for v in value if isinstance(v, str) and v.strip()])

        # 텍스트 데이터가 있는 경우만 포함
        if text_parts:
             corpus.append(" ".join(text_parts))
             item_ids.append(content.get('id')) # 'id' 필드가 고유 ID라고 가정
             valid_content_indices.append(i)
        else:
            logger.debug(f"Content item {content.get('id', i)} has no text data in specified fields. Skipping.")

    if not corpus:
        logger.warning("Cannot build TF-IDF vectors: No valid text data found in corpus.")
        return False

    try:
        # TF-IDF 벡터라이저 초기화 및 학습
        # max_features, min_df, max_df 등 파라미터 조정 가능
        tfidf_vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
        item_tfidf_vectors = tfidf_vectorizer.fit_transform(corpus)

        # 아이템 ID와 내부 인덱스 매핑 생성
        item_id_to_index = {item_id: i for i, item_id in enumerate(item_ids)}
        index_to_item_id = {i: item_id for i, item_id in enumerate(item_ids)}

        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(f"TF-IDF vectors built successfully. Shape: {item_tfidf_vectors.shape}. Took {duration:.2f} seconds.")
        return True

    except Exception as e:
        logger.error(f"Error building TF-IDF vectors: {e}", exc_info=True)
        tfidf_vectorizer = item_tfidf_vectors = item_id_to_index = index_to_item_id = None
        return False


# --- 사용자 프로필 벡터 계산 ---
def compute_user_profile_vector(user_history_item_ids: List[str]) -> Optional[np.ndarray]:
    """
    사용자의 상호작용 아이템 ID 리스트를 받아 평균 TF-IDF 벡터 (프로필)를 계산합니다.
    최근 N개 기록만 사용 (설정값 CB_USER_HISTORY_LIMIT).
    """
    if not user_history_item_ids:
        return None
    if item_tfidf_vectors is None or item_id_to_index is None:
        logger.warning("TF-IDF vectors not built. Cannot compute user profile.")
        return None

    # 최근 기록 제한 적용
    recent_history = user_history_item_ids[-CB_USER_HISTORY_LIMIT:]

    user_vectors = []
    for item_id in recent_history:
        idx = item_id_to_index.get(item_id)
        if idx is not None:
            # item_tfidf_vectors는 CSR(Compressed Sparse Row) 포맷일 수 있음
            user_vectors.append(item_tfidf_vectors[idx].toarray().flatten()) # 밀집 벡터로 변환

    if not user_vectors:
        # logger.debug(f"No valid item vectors found for user history: {recent_history}")
        return None

    # 벡터들의 평균 계산
    profile_vector = np.mean(user_vectors, axis=0)
    return profile_vector

# --- 콘텐츠 기반 점수 계산 ---
def get_content_based_scores(
    user_profile_vector: np.ndarray,
    candidate_item_ids: Set[str]
) -> Dict[str, float]:
    """
    사용자 프로필 벡터와 후보 아이템 ID 목록을 받아 코사인 유사도 기반 점수를 계산합니다.
    """
    scores = {}
    if user_profile_vector is None or not candidate_item_ids:
        return scores
    if item_tfidf_vectors is None or item_id_to_index is None:
        logger.warning("TF-IDF vectors not built. Cannot compute CB scores.")
        return scores

    candidate_indices = []
    valid_candidate_ids = []
    for item_id in candidate_item_ids:
        idx = item_id_to_index.get(item_id)
        if idx is not None:
            candidate_indices.append(idx)
            valid_candidate_ids.append(item_id)

    if not valid_candidate_ids:
        return scores

    # 후보 아이템들의 벡터 추출
    candidate_vectors = item_tfidf_vectors[candidate_indices]

    # 사용자 프로필 벡터와 후보 벡터들 간의 코사인 유사도 계산
    # 사용자 프로필 벡터를 2D 배열로 변환 (1, num_features)
    user_profile_2d = user_profile_vector.reshape(1, -1)
    try:
        similarities = cosine_similarity(user_profile_2d, candidate_vectors)
        # similarities는 (1, num_candidates) 형태의 배열
        sim_scores = similarities[0]

        # 결과를 {item_id: score} 딕셔너리로 변환
        for item_id, score in zip(valid_candidate_ids, sim_scores):
            # 유사도 점수는 0~1 사이 값이지만, 음수가 나올 경우 0으로 처리
            scores[item_id] = max(0.0, float(score))

    except Exception as e:
        logger.error(f"Error calculating cosine similarity for CB scores: {e}", exc_info=True)

    return scores