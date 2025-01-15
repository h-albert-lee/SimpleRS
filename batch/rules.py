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

def generate_local_candidates_rule(db: DBManager, user_id: str) -> List[Dict[str, Any]]:
    """
    기존 규칙 기반의 사용자별 로컬 후보 콘텐츠 생성.
    """
    owned_stocks = db.get_user_owned_stocks(user_id)
    stock_related_content = db.get_content_by_stocks(owned_stocks)
    recent_interactions = db.get_recent_interactions(user_id)
    interaction_related_content = db.get_content_by_ids(recent_interactions)

    combined = stock_related_content + interaction_related_content
    unique_candidates = {content['id']: content for content in combined}
    return list(unique_candidates.values())


def generate_local_candidates(db: DBManager, user_id: str) -> List[Dict[str, Any]]:
    """
    규칙 기반과 콘텐츠 기반 협업 필터링을 모두 활용하여 사용자별 후보 콘텐츠 생성.
    """
    # 1. 규칙 기반 후보 생성
    rule_based_candidates = generate_local_candidates_rule(db, user_id)
    rule_based_ids = {content['id'] for content in rule_based_candidates}
    
    # 2. 콘텐츠 기반 협업 필터링 과정
    # 사용자 소비 콘텐츠 메타데이터 가져오기
    user_history_meta = db.get_user_history(user_id)  # [(content_meta1), (content_meta2), ...]
    user_embeddings = [embed_content(meta) for meta in user_history_meta]
    user_profile = compute_user_profile(user_embeddings)
    
    # 글로벌 후보 목록 활용 (CF 과정에서)
    global_candidates = generate_global_candidates(db)
    
    # 후보 콘텐츠 임베딩 계산
    candidate_ids = []
    candidate_embeddings = []
    for content in global_candidates:
        candidate_ids.append(content['id'])
        candidate_embeddings.append(embed_content(content))
    
    # 콘텐츠 기반 CF로 top_k 추천 아이템 ID 선정
    recommended_ids = recommend_with_content_based_cf(
        user_profile, candidate_embeddings, candidate_ids, top_k=50
    )
    
    # CF 기반 추천된 후보 콘텐츠 필터링
    cf_based_candidates = [content for content in global_candidates if content['id'] in recommended_ids]
    
    # 3. 규칙 기반 후보와 CF 기반 후보 통합 (중복 제거)
    combined_candidates = {content['id']: content for content in (rule_based_candidates + cf_based_candidates)}
    
    return list(combined_candidates.values())
