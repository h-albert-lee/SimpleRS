import logging
from batch.utils.db_manager import DBManager
from batch.utils.logging_setup import setup_logging
from batch.rules import generate_global_candidates, generate_local_candidates_with_cf

setup_logging()
logger = logging.getLogger(__name__)

def candidate_generation():
    db = DBManager()

    # 글로벌 후보 생성
    logger.info("Generating Global Candidates...")
    try:
        global_candidates = generate_global_candidates(db)
        db.store_global_candidates(global_candidates)
        logger.info(f"Stored {len(global_candidates)} global candidates.")
    except Exception as e:
        logger.error(f"Error generating/storing global candidates: {e}")

    # 사용자별 로컬 후보 생성 (콘텐츠 기반 CF 활용)
    logger.info("Generating User-Specific Local Candidates with Content-Based CF...")
    try:
        user_ids = db.get_all_user_ids()
        for user_id in user_ids:
            local_candidates = generate_local_candidates_with_cf(db, user_id)
            db.store_local_candidates(user_id, local_candidates)
            logger.info(f"Stored {len(local_candidates)} local candidates for user {user_id}.")
    except Exception as e:
        logger.error(f"Error generating/storing local candidates: {e}")

if __name__ == "__main__":
    logger.info("Starting Candidate Generation Process...")
    candidate_generation()
    logger.info("Candidate Generation Completed.")
