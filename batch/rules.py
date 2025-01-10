from typing import List, Dict, Any
from batch.utils.db_manager import DBManager
from models.collaborative_filtering import CollaborativeFilteringModel

def generate_global_candidates(db: DBManager) -> List[Dict[str, Any]]:
    # 기존 글로벌 후보 생성 로직
    popular_content = db.get_popular_content(limit=50)
    recent_content = db.get_recent_content(limit=50)
    combined = popular_content + recent_content
    unique_candidates = {content['id']: content for content in combined}
    return list(unique_candidates.values())

def generate_local_candidates_with_cf(db: DBManager, user_id: str, cf_model: CollaborativeFilteringModel) -> List[Dict[str, Any]]:
    """
    협업 필터링을 활용하여 사용자별 후보 콘텐츠 생성.
    """
    # 기존 로컬 후보: 보유 종목 및 최근 상호작용 기반
    owned_stocks = db.get_user_owned_stocks(user_id)
    stock_related_content = db.get_content_by_stocks(owned_stocks)
    recent_interactions = db.get_recent_interactions(user_id)
    interaction_related_content = db.get_content_by_ids(recent_interactions)

    combined = stock_related_content + interaction_related_content
    # 기존 방식: 중복 제거
    unique_candidates = {content['id']: content for content in combined}

    # 협업 필터링 예측 점수를 사용하여 추가 후보 선정
    # 예를 들어, 사용자에 대해 CF 모델이 높은 점수를 반환하는 아이템을 후보에 추가
    # candidates는 데이터베이스에서 가져온 모든 item 목록이라고 가정
    all_items = db.get_all_items()  # 전체 아이템 목록 가져오기 (구현 필요)
    cf_predictions = cf_model.predict(user_id, [item['id'] for item in all_items])
    
    # cf_predictions 결과에서 높은 점수를 받은 아이템을 후보에 추가
    # (예시는 상위 10개 아이템 추가)
    cf_predictions_sorted = sorted(cf_predictions, key=lambda x: x[1], reverse=True)
    top_cf_items = [item_id for item_id, score in cf_predictions_sorted[:10]]
    
    # CF 기반 추가 콘텐츠 가져오기
    cf_related_content = db.get_content_by_ids(top_cf_items)
    for content in cf_related_content:
        unique_candidates.setdefault(content['id'], content)

    return list(unique_candidates.values())
