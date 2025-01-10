from typing import List, Dict, Any
from models.bert4rec import BERT4RecModel

# 전역으로 BERT4Rec 모델을 초기화하거나 싱글톤 패턴으로 관리 가능
bert4rec_model = BERT4RecModel(num_items=1000, embedding_dim=64)
# 필요하다면 미리 학습된 모델 로드
# bert4rec_model.load("path/to/bert4rec/model.pth")

def rank_candidates(candidates: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """
    BERT4Rec 모델을 사용해 주어진 후보들을 순위화.
    """
    # 후보 콘텐츠의 ID 목록 추출
    candidate_ids = [candidate['id'] for candidate in candidates]
    
    # BERT4Rec 모델로 예측 점수 획득
    # 여기서는 predict 메서드가 단순 예시 점수를 반환한다고 가정
    scores = bert4rec_model.predict(user_id, candidate_ids)
    # scores는 (item_id, score) 튜플 리스트라고 가정

    # scores를 기반으로 후보 정렬
    score_dict = dict(scores)
    ranked_candidates = sorted(candidates, key=lambda x: score_dict.get(x['id'], 0), reverse=True)
    return ranked_candidates
