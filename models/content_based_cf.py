import numpy as np
from typing import List
from models.data_preparation import embed_content

def compute_user_profile(user_consumed_content_metas: List[dict]) -> np.ndarray:
    """
    주어진 사용자 소비 콘텐츠 메타데이터 리스트로부터 사용자 프로필 벡터 계산.
    """
    embeddings = [embed_content(meta) for meta in user_consumed_content_metas]
    if not embeddings:
        return np.zeros((64,))  # 임베딩 차원에 맞게 초기화
    return np.mean(embeddings, axis=0)

def recommend_content(user_profile: np.ndarray, candidate_content_metas: List[dict], top_k: int = 10) -> List[dict]:
    """
    사용자 프로필과 후보 콘텐츠 메타데이터를 기반으로 유사도 계산 후 top_k 추천.
    """
    similarities = []
    for meta in candidate_content_metas:
        emb = embed_content(meta)
        # 코사인 유사도 계산
        sim = np.dot(user_profile, emb) / (np.linalg.norm(user_profile) * np.linalg.norm(emb) + 1e-8)
        similarities.append(sim)
    
    # 유사도를 기준으로 상위 top_k 콘텐츠 선택
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    return [candidate_content_metas[i] for i in top_indices]
