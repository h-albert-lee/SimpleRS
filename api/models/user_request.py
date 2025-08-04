# simplers/api/models/user_request.py
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 추천 아이템 모델 (점수 포함) ---
class RecommendationItemScore(BaseModel):
    item_id: str = Field(..., description="추천된 아이템의 고유 ID")
    score: float = Field(..., description="최종 추천 점수")
    # 필요시 title 등 메타데이터 추가 가능

# --- 비로그인 추천 응답 모델 ---
class AnonymousRecommendationResponse(BaseModel):
    recommendations: List[str] = Field(..., description="셔플된 비로그인 추천 콘텐츠 ID 목록")

# --- 프로덕션 추천 응답 모델 ---
class ProductionRecommendationResponse(BaseModel):
    cust_no: int = Field(..., description="요청한 고객 번호")
    recommendations: List[RecommendationItemScore] = Field(..., description="추천 아이템 목록 (ID 및 점수)")

# --- 기존 모델들 (필요 없으면 삭제 가능) ---
class RecommendationRequest(BaseModel):
    user_id: str
    recent_history: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: List[str] # BMT 또는 다른 용도로 남겨둘 수 있음

# BMT 응답 모델도 필요 없으면 삭제 가능
# class BMTRecommendationResponse(BaseModel):
#     cust_no: int = Field(...)
#     recommendations: List[str] = Field(...)