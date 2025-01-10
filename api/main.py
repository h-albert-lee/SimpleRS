# main.py
import asyncio
from fastapi import FastAPI
from api.routers import recommendations
from api.batch_processor import batch_processor

app = FastAPI(title="Recommendation System", version="1.0.0")
app.include_router(recommendations.router, prefix="/recommendations")

@app.on_event("startup")
async def startup_event():
    # 애플리케이션 시작 시 배치 프로세서 백그라운드 태스크 실행
    asyncio.create_task(batch_processor())
