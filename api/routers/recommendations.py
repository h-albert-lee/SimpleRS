from fastapi import APIRouter, HTTPException
from api.models.user_request import RecommendationRequest, RecommendationResponse
from api.batch_processor import request_queue
import asyncio

router = APIRouter()

@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    loop = asyncio.get_running_loop()
    response_future = loop.create_future()
    
    # 요청 큐에 user_id와 future를 추가
    await request_queue.put((request.user_id, response_future))
    
    try:
        result = await response_future  # 배치 처리 결과 대기
        return RecommendationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
