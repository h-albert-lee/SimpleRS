from batch.utils.db_manager import DBManager

def fetch_candidates(user_id):
    db = DBManager()
    return db.get_candidates_for_user(user_id)
