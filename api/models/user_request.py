# api/models/user_request.py
from pydantic import BaseModel
from typing import List, Optional

class RecommendationRequest(BaseModel):
    user_id: str
    # 추가적으로 요청에 필요한 필드를 정의할 수 있음
    # 예: 최근 시청한 콘텐츠 IDs, 선호도 필터링 옵션 등
    recent_history: Optional[List[str]] = None  # 예시: 최근에 본 콘텐츠 ID 리스트

class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: List[str]  # 추천 콘텐츠 ID 리스트 또는 상세 정보 리스트
