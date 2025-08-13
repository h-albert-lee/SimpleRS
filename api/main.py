import asyncio
import logging
from fastapi import FastAPI
from api.routers import recommendations
from api.db_clients import (
    connect_to_mongo, close_mongo_connection,
    connect_to_opensearch, close_opensearch_connection,
    connect_to_oracle, close_oracle_connection, # Oracle 함수 임포트
    get_mongo_db, get_os_client, get_oracle_pool # DB 객체/풀 가져오는 함수 임포트 (상태 확인용)
)
from api.logger_manager import init_logging, LOGGING_CONFIG

init_logging()
logger = logging.getLogger(__name__)
app = FastAPI(
    title="Recommendation System API", # BMT 문구 제거 또는 수정
    version="1.1.0", # 버전 업데이트
    description="Recommendation System API with MongoDB, OpenSearch, and Oracle DB support." # 설명 업데이트
)

# 라우터 포함
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 DB 연결"""
    logger.info("Application startup sequence initiated...")
    try:
        # DB 연결들을 병렬로 시도
        await asyncio.gather(
            connect_to_mongo(),
            connect_to_opensearch(),
            connect_to_oracle() # Oracle 연결 추가
        )
        logger.info("All database connections established.")
    except Exception as e:
        # DB 연결 중 하나라도 실패하면 로깅하지만 앱 시작은 계속 진행 (테스트 목적)
        logger.warning(f"Database connection failed during startup: {e}", exc_info=True)
        logger.warning("Continuing startup without database connections for testing purposes.")
        # 실제 운영 환경에서는 여기서 애플리케이션을 안전하게 종료하는 로직 필요
        # 예: import sys; sys.exit(1)
        # raise RuntimeError("Application startup failed due to DB connection error.") from e

    # --- 배치 프로세서 관련 로직은 현재 주석 처리됨 ---
    # logger.info("Starting background batch processor...")
    # asyncio.create_task(batch_processor())
    # logger.info("Background batch processor started.")
    logger.info("Application startup complete.")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 DB 연결 해제"""
    logger.info("Application shutdown sequence initiated...")
    # 연결 해제는 순차적으로 또는 병렬로 처리 가능
    # 순차 처리 예시 (에러 발생 시 다음 단계 진행 보장)
    try:
        await close_mongo_connection()
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}", exc_info=True)
    try:
        await close_opensearch_connection()
    except Exception as e:
        logger.error(f"Error closing OpenSearch connection: {e}", exc_info=True)
    try:
        await close_oracle_connection() # Oracle 연결 해제 추가
    except Exception as e:
        logger.error(f"Error closing Oracle connection pool: {e}", exc_info=True)

    logger.info("Finished closing database connections.")
    logger.info("Application shutdown complete.")


# 기본 루트 엔드포인트 (서버 상태 확인용)
@app.get("/", tags=["Status"])
async def root():
    """API 서버의 기본 상태 및 DB 연결 상태를 확인합니다."""
    # 각 DB 연결 상태를 확인 (단, 실제 연결 테스트는 부하를 줄 수 있으므로 주의)
    db_status = {}
    try:
        # get_mongo_db() 내부에서 ping 테스트가 없으므로, 객체 존재 여부로 판단
        if get_mongo_db():
            db_status["mongodb"] = "Connected (Client Available)"
        else:
            db_status["mongodb"] = "Disconnected"
    except Exception:
         db_status["mongodb"] = "Error checking status"

    try:
        # get_os_client() 내부에서 ping 테스트가 없으므로, 객체 존재 여부로 판단
        if get_os_client():
            # 필요시 간단한 추가 ping 테스트 가능: await get_os_client().ping()
            db_status["opensearch"] = "Connected (Client Available)"
        else:
            db_status["opensearch"] = "Disconnected"
    except Exception:
        db_status["opensearch"] = "Error checking status"

    try:
        # get_oracle_pool() 은 풀 객체를 반환. 실제 연결은 풀에서 acquire 시 이루어짐.
        # 여기서는 풀 객체 존재 여부만 확인
        if get_oracle_pool():
             db_status["oracle"] = "Connected (Pool Available)"
             # 간단한 테스트 쿼리로 실제 연결 확인 가능 (주의: 부하 발생)
             # try:
             #    async with get_oracle_pool().acquire() as conn:
             #        async with conn.cursor() as cursor:
             #            await cursor.execute("SELECT 1 FROM DUAL")
             #            await cursor.fetchone()
             #    db_status["oracle"] = "Connected (Pool Available & Ping OK)"
             # except Exception as e:
             #    logger.warning(f"Oracle pool ping failed: {e}")
             #    db_status["oracle"] = "Connected (Pool Available, Ping Failed)"
        else:
            db_status["oracle"] = "Disconnected"
    except Exception:
        db_status["oracle"] = "Error checking status"


    return {
        "message": "Recommendation System API is running.",
        "database_connections": db_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, log_config=LOGGING_CONFIG)
