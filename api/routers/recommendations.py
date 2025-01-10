from fastapi import APIRouter, HTTPException
from api.services.candidate_fetcher import fetch_candidates
from api.services.ranking import rank_candidates

router = APIRouter()

@router.get("/")
def get_recommendations(user_id: str):
    # 후보 콘텐츠 가져오기
    candidates = fetch_candidates(user_id)
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates found.")
    
    # 순위화
    ranked_candidates = rank_candidates(candidates)
    return {"user_id": user_id, "recommendations": ranked_candidates}
