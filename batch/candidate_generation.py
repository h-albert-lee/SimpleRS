import logging
from batch.utils.db_manager import DBManager
from batch.utils.logging_setup import setup_logging
from batch.rules import generate_global_candidates, generate_local_candidates_with_cf
from models.collaborative_filtering import CollaborativeFilteringModel

setup_logging()
logger = logging.getLogger(__name__)

def candidate_generation():
    """
    글로벌 및 사용자별 후보 콘텐츠를 생성하여 저장하는 프로세스.
    여기서는 협업 필터링을 활용해 사용자별 후보를 보완함.
    """
    db = DBManager()

    # Step 1: Generate Global Candidates
    logger.info("Generating Global Candidates...")
    try:
        global_candidates = generate_global_candidates(db)
        db.store_global_candidates(global_candidates)
        logger.info(f"Stored {len(global_candidates)} global candidates.")
    except Exception as e:
        logger.error(f"Error generating/storing global candidates: {e}")

    # Step 2: 협업 필터링 모델 초기화 (학습된 모델 로드 혹은 미리 학습된 모델 사용)
    cf_model = CollaborativeFilteringModel(num_users=1000, num_items=1000, embedding_dim=50)
    # cf_model.load("path/to/pretrained/model.pth")  # 미리 학습된 모델 로드, 필요시 사용

    # Step 3: Generate Local Candidates with CF for Each User
    logger.info("Generating User-Specific Local Candidates with CF...")
    try:
        user_ids = db.get_all_user_ids()
        for user_id in user_ids:
            # 기존 로컬 후보 생성
            local_candidates = generate_local_candidates_with_cf(db, user_id, cf_model)
            db.store_local_candidates(user_id, local_candidates)
            logger.info(f"Stored {len(local_candidates)} local candidates for user {user_id}.")
    except Exception as e:
        logger.error(f"Error generating/storing local candidates: {e}")

if __name__ == "__main__":
    logger.info("Starting Candidate Generation Process...")
    candidate_generation()
    logger.info("Candidate Generation Completed.")
