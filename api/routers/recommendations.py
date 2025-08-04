# simplers/api/routers/recommendations.py
from fastapi import APIRouter, HTTPException, Path, Request, status, Security, Depends # Security, Depends 추가
from fastapi.security import APIKeyHeader # APIKeyHeader 추가
from typing import List
# 응답 모델 임포트 수정
from api.models.user_request import ProductionRecommendationResponse, RecommendationItemScore, AnonymousRecommendationResponse
# 서비스 임포트 수정
from api.services import recommendation_service
from api.config_loader import SECRET_API_KEY # 설정에서 로드한 API 키 임포트
import asyncio
import logging
import time
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# --- API 키 검증 설정 ---
API_KEY_NAME = "X-API-Key" # 클라이언트가 API 키를 전달할 헤더 이름
api_key_header_auth = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header_auth)):
    """API 키 헤더를 검증하는 의존성 함수"""
    if not SECRET_API_KEY:
        # 설정 파일에 키가 없으면 인증 건너뛰기 (또는 에러 발생) - 정책에 따라 결정
        logger.warning("API Key validation skipped because SECRET_API_KEY is not set in config.")
        return api_key_header # 실제 키 검증은 하지 않음

    if api_key_header == SECRET_API_KEY:
        return api_key_header
    else:
        logger.warning(f"Invalid API Key received: {api_key_header[:5]}...") # 로그에는 키 일부만 남김
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

# --- 실시간 규칙 기반 추천 엔드포인트 (보안 적용) ---
@router.get("/user/{cust_no}", # 엔드포인트 경로 변경 (예시)
            response_model=ProductionRecommendationResponse, # 새 응답 모델 사용
            summary="Get Production Recommendations",
            description="Provides rule-based recommendations with scores for a given customer number.",
            # --- 보안 의존성 추가 ---
            dependencies=[Depends(get_api_key)])
async def get_production_recommendations_endpoint(
    request: Request,
    cust_no: int = Path(..., title="Customer Number", ge=1)
    # api_key: str = Security(get_api_key) # 의존성을 파라미터로 받을 수도 있음
):
    """
    사용자 번호(cust_no)를 받아 규칙 기반 추천 로직을 수행하고,
    콘텐츠 ID와 최종 점수 목록을 반환합니다.
    """
    start_time = time.perf_counter()
    log_prefix = f"[cust_no={cust_no}] [pid={os.getpid()}]"
    client_host = request.client.host if request.client else "Unknown"

    logger.info(f"{log_prefix} Request received for production recommendations from {client_host}")

    response_data = None
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR # 기본 상태 코드

    try:
        # 서비스 함수 호출 (결과는 List[Tuple[str, float]])
        recommendations_with_scores = await recommendation_service.get_live_recommendations(cust_no)

        # 응답 모델 형식으로 변환
        recommendation_items = [
            RecommendationItemScore(item_id=item_id, score=score)
            for item_id, score in recommendations_with_scores
        ]

        response_data = ProductionRecommendationResponse(
            cust_no=cust_no,
            recommendations=recommendation_items
        )
        http_status_code = status.HTTP_200_OK # 성공

        # 결과가 없을 경우 200 OK와 빈 리스트 반환 (API 정책에 따라 204 No Content 등 고려 가능)
        if not recommendation_items:
            logger.info(f"{log_prefix} No recommendations generated, returning empty list.")

        return response_data

    except RuntimeError as e:
        # DB 클라이언트 연결 실패 등
        http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"{log_prefix} Request failed due to runtime error (DB connection?) after {duration_ms:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=http_status_code, detail=f"Service temporarily unavailable: {e}")

    except Exception as e:
        # 기타 예외
        http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"{log_prefix} Request failed due to unexpected error after {duration_ms:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=http_status_code, detail=f"Internal server error while processing recommendations for customer {cust_no}")

    finally:
        # 요청 처리 시간 로깅
        duration_ms = (time.perf_counter() - start_time) * 1000
        # response_data가 정의되지 않았을 수 있으므로 확인 추가
        recommend_count = len(response_data.recommendations) if response_data and http_status_code == 200 else 0
        logger.info(f"{log_prefix} Request completed with status {http_status_code} in {duration_ms:.2f}ms. Recommendations returned: {recommend_count}")


# --- 비로그인 사용자 추천 엔드포인트 (보안 적용) ---
@router.get("/anonymous",
            response_model=AnonymousRecommendationResponse,
            summary="Get Anonymous Recommendations",
            description="Provides shuffled recommendations for non-logged-in users based on general popularity or curation.",
            # --- 보안 의존성 추가 ---
            dependencies=[Depends(get_api_key)])
async def get_anonymous_recommendations_endpoint(request: Request):
    """
    비로그인 사용자를 위한 추천 엔드포인트입니다.
    미리 정의된 콘텐츠 목록을 무작위로 섞어 반환합니다.
    """
    start_time = time.perf_counter()
    log_prefix = f"[Anonymous] [pid={os.getpid()}]"
    client_host = request.client.host if request.client else "Unknown"

    logger.info(f"{log_prefix} Request received for anonymous recommendations from {client_host}")

    response_data = None
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    try:
        # 비로그인 추천 서비스 함수 호출
        shuffled_ids = await recommendation_service.get_anonymous_recommendations()

        response_data = AnonymousRecommendationResponse(recommendations=shuffled_ids)
        http_status_code = status.HTTP_200_OK

        if not shuffled_ids:
             logger.info(f"{log_prefix} No anonymous recommendations generated, returning empty list.")

        return response_data

    except Exception as e:
        # 서비스 로직 내에서 에러 로깅은 이미 처리됨
        http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        duration_ms = (time.perf_counter() - start_time) * 1000 # 에러 발생 시점 시간 로깅
        logger.error(f"{log_prefix} Request failed due to unexpected error after {duration_ms:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=http_status_code, detail="Internal server error while processing anonymous recommendations")

    finally:
        # 요청 처리 시간 로깅
        duration_ms = (time.perf_counter() - start_time) * 1000
        # response_data가 정의되지 않았을 수 있으므로 확인 추가
        recommend_count = len(response_data.recommendations) if response_data and http_status_code == 200 else 0
        logger.info(f"{log_prefix} Request completed with status {http_status_code} in {duration_ms:.2f}ms. Recommendations returned: {recommend_count}")