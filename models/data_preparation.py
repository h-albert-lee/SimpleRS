from typing import Any, List, Tuple
import numpy as np

def embed_content(content_meta: dict) -> np.ndarray:
    """
    콘텐츠 메타데이터를 받아 임베딩 벡터를 반환하는 함수.
    실제로는 pretrained 모델이나 다른 방식으로 임베딩을 추출.
    여기는 단순한 예시로 난수 벡터를 반환.
    """
    embedding_dim = 64
    return np.random.rand(embedding_dim)

def fetch_user_interaction_data() -> List[Tuple[str, dict]]:
    """
    사용자 상호작용 데이터를 수집.
    각 항목은 (user_id, content_meta) 형태로 반환.
    content_meta는 콘텐츠 메타데이터 딕셔너리.
    """
    # 실제 DB 및 Elasticsearch 연동 코드 필요
    # 아래는 더미 데이터 예시
    dummy_data = [
        ("user1", {"title": "video1", "tags": ["tag1", "tag2"]}),
        ("user1", {"title": "video2", "tags": ["tag2", "tag3"]}),
        ("user1", {"title": "video3", "tags": ["tag1", "tag4"]}),
        # 다른 사용자 데이터...
    ]
    return dummy_data

def preprocess_data(raw_data: List[Tuple[str, dict]]) -> dict:
    """
    수집된 원시 데이터를 사용자별 콘텐츠 임베딩 시퀀스로 전처리.
    반환: {user_id: [embedding1, embedding2, ...], ...}
    """
    user_sequences = {}
    for user_id, content_meta in raw_data:
        embedding = embed_content(content_meta)
        user_sequences.setdefault(user_id, []).append(embedding)
    return user_sequences
