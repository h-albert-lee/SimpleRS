import numpy as np
from typing import List
from batch.utils.db_manager import DBManager

def embed_content(content_meta: dict) -> np.ndarray:
    """
    콘텐츠 메타데이터를 받아 임베딩 벡터를 반환하는 함수.
    실제로는 pretrained 모델이나 다른 방식으로 임베딩을 추출.
    여기서는 예시로 난수 벡터를 반환.
    """
    embedding_dim = 64
    return np.random.rand(embedding_dim)

def compute_user_profile(user_embeddings: List[np.ndarray]) -> np.ndarray:
    """
    주어진 사용자 소비 콘텐츠 임베딩 리스트로부터 사용자 프로필 벡터 계산.
    단순 평균을 사용.
    """
    if not user_embeddings:
        return np.zeros((64,))
    return np.mean(user_embeddings, axis=0)

def recommend_with_content_based_cf(user_profile: np.ndarray, candidate_embeddings: List[np.ndarray], candidate_ids: List[str], top_k: int = 10) -> List[str]:
    """
    사용자 프로필과 후보 콘텐츠 임베딩을 기반으로 유사도 계산 후 top_k 추천.
    """
    similarities = []
    for emb in candidate_embeddings:
        # 코사인 유사도 계산
        norm_user = np.linalg.norm(user_profile) + 1e-8
        norm_item = np.linalg.norm(emb) + 1e-8
        sim = np.dot(user_profile, emb) / (norm_user * norm_item)
        similarities.append(sim)
    
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    recommended_ids = [candidate_ids[i] for i in top_indices]
    return recommended_ids
