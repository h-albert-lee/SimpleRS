from typing import List, Dict, Any
from batch.utils.db_manager import DBManager
from batch.utils.cf_utils import embed_content, compute_user_profile, recommend_with_content_based_cf
import numpy as np

def generate_global_candidates(db: DBManager) -> List[Dict[str, Any]]:
    popular_content = db.get_popular_content(limit=50)
    recent_content = db.get_recent_content(limit=50)
    combined = popular_content + recent_content
    unique_candidates = {content['id']: content for content in combined}
    return list(unique_candidates.values())

def generate_local_candidates_with_cf(db: DBManager, user_id: str) -> List[Dict[str, Any]]:
    """
    콘텐츠 기반 협업 필터링을 활용하여 사용자별 후보 콘텐츠 생성.
    """
    # 사용자가 소비한 콘텐츠 메타데이터 가져오기
    user_history_meta = db.get_user_history(user_id)  # [(content_meta1), (content_meta2), ...] 형태
    user_embeddings = [embed_content(meta) for meta in user_history_meta]
    
    # 사용자 프로필 계산
    user_profile = compute_user_profile(user_embeddings)
    
    # 후보 콘텐츠 목록 준비 (예: 글로벌 후보 활용)
    global_candidates = generate_global_candidates(db)
    
    # 후보 콘텐츠 임베딩 계산
    candidate_ids = []
    candidate_embeddings = []
    for content in global_candidates:
        candidate_ids.append(content['id'])
        candidate_embeddings.append(embed_content(content))
    
    # 콘텐츠 기반 CF로 top_k 추천 아이템 ID 선정
    recommended_ids = recommend_with_content_based_cf(user_profile, candidate_embeddings, candidate_ids, top_k=50)
    
    # 추천된 콘텐츠를 최종 후보 목록으로 구성
    recommended_candidates = [content for content in global_candidates if content['id'] in recommended_ids]
    return recommended_candidates
