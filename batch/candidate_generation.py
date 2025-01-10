import logging
from batch.utils.db_manager import DBManager
from batch.utils.logging import setup_logging
from batch.rules import generate_global_candidates, generate_local_candidates

setup_logging()
logger = logging.getLogger(__name__)

def candidate_generation():
    """
    Generate both global and user-specific local candidates based on rules,
    and store them in KeyDB.
    """
    db = DBManager()

    # Step 1: Generate Global Candidates
    logger.info("Generating Global Candidates...")
    global_candidates = generate_global_candidates(db)
    db.store_global_candidates(global_candidates)
    logger.info(f"Stored {len(global_candidates)} global candidates in KeyDB.")

    # Step 2: Generate Local Candidates for Each User
    logger.info("Generating User-Specific Local Candidates...")
    user_ids = db.get_all_user_ids()
    
    for user_id in user_ids:
        local_candidates = generate_local_candidates(db, user_id)
        db.store_local_candidates(user_id, local_candidates)
        logger.info(f"Stored {len(local_candidates)} local candidates for user {user_id}.")

if __name__ == "__main__":
    logger.info("Starting Candidate Generation Process...")
    candidate_generation()
    logger.info("Candidate Generation Completed.")
