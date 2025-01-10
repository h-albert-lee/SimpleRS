# api/routers/recommendations.py
from fastapi import APIRouter, HTTPException
from api.batch_processor import request_queue
import asyncio

router = APIRouter()

@router.get("/")
async def get_recommendations(user_id: str):
    loop = asyncio.get_running_loop()
    response_future = loop.create_future()
    
    # 요청 큐에 추가
    await request_queue.put((user_id, response_future))
    
    try:
        result = await response_future  # 배치 처리 완료 대기
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
