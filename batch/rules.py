def generate_global_candidates(db):
    """
    Generate global candidates based on predefined rules.
    :param db: Instance of DBManager to fetch required data.
    :return: List of global candidates.
    """
    # Rule 1: Popular content
    popular_content = db.get_popular_content(limit=50)

    # Rule 2: Recent content
    recent_content = db.get_recent_content(limit=50)

    # Combine and remove duplicates
    global_candidates = list({content['id']: content for content in (popular_content + recent_content)}.values())
    return global_candidates


def generate_local_candidates(db, user_id):
    """
    Generate user-specific local candidates based on predefined rules.
    :param db: Instance of DBManager to fetch required data.
    :param user_id: ID of the user for whom local candidates are generated.
    :return: List of local candidates.
    """
    # Rule 1: Content related to user's owned stocks
    owned_stocks = db.get_user_owned_stocks(user_id)
    stock_related_content = db.get_content_by_stocks(owned_stocks)

    # Rule 2: User's recent interactions
    user_recent_interactions = db.get_recent_interactions(user_id)
    interaction_related_content = db.get_content_by_ids(user_recent_interactions)

    # Combine and remove duplicates
    local_candidates = list({content['id']: content for content in (stock_related_content + interaction_related_content)}.values())
    return local_candidates
