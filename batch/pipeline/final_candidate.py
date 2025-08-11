import logging
from collections import defaultdict
from typing import Any, Dict, List, Set

import pandas as pd

from batch.pipeline.local_candidate import compute_local_candidates
from batch.utils.config_loader import (
    SOURCE_WEIGHTS,
    CF_WEIGHT,
    MIN_SCORE_THRESHOLD,
    MAX_CANDIDATES_PER_USER,
)

logger = logging.getLogger(__name__)


def calculate_hybrid_scores(
    user_id: str,
    context: Dict[str, Any],
    global_ids: Set[str],
    local_ids: Set[str],
    other_ids: Set[str],
) -> Dict[str, float]:
    """Combine rule-based weights and CF scores."""

    log_prefix = f"[User: {user_id}][Scoring]"
    final_scores: Dict[str, float] = defaultdict(float)

    all_candidate_ids = global_ids.union(local_ids).union(other_ids)
    if not all_candidate_ids:
        return {}

    cf_model = context.get("cf_model")
    user_interactions = context.get("user_interactions", {})
    user_history = user_interactions.get(user_id, [])

    cf_scores: Dict[str, float] = {}
    if cf_model and getattr(cf_model, "is_ready", False) and user_history:
        cf_scores = cf_model.get_scores(user_history, all_candidate_ids)

    w_global = SOURCE_WEIGHTS.get("global", 0.0)
    w_local = SOURCE_WEIGHTS.get("local", 0.0)
    w_other = SOURCE_WEIGHTS.get("other", 0.0)

    for item_id in all_candidate_ids:
        score = 0.0
        if item_id in global_ids:
            score += w_global
        if item_id in local_ids:
            score += w_local
        if item_id in other_ids:
            score += w_other
        if item_id in cf_scores:
            score += cf_scores[item_id] * CF_WEIGHT

        if score >= MIN_SCORE_THRESHOLD:
            final_scores[item_id] = score

    if len(final_scores) > MAX_CANDIDATES_PER_USER:
        ranked_items = sorted(
            final_scores.items(), key=lambda item: item[1], reverse=True
        )
        top_n_scores = dict(ranked_items[:MAX_CANDIDATES_PER_USER])
        logger.info(
            f"{log_prefix} Calculated final scores for {len(top_n_scores)} items (Top {MAX_CANDIDATES_PER_USER})."
        )
        return top_n_scores
    else:
        logger.info(
            f"{log_prefix} Calculated final scores for {len(final_scores)} items."
        )
        return dict(final_scores)


def generate_candidate_for_user(
    user: Dict[str, Any],
    global_candidates: List[str],
    other_candidates: List[str],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate final candidate document with hybrid scoring."""

    user_id = user.get("cust_no", "UNKNOWN_USER")
    log_prefix = f"[User: {user_id}]"
    logger.debug(f"{log_prefix} Generating final candidates and scores...")

    local_candidates = compute_local_candidates(user, context)

    final_scores = calculate_hybrid_scores(
        user_id,
        context,
        set(global_candidates),
        set(local_candidates),
        set(other_candidates),
    )

    if not final_scores:
        logger.warning(f"{log_prefix} No candidates with scores generated.")
        return {}

    curation_list = [
        {"curation_id": str(cid), "score": float(s)}
        for cid, s in final_scores.items()
    ]
    curation_list.sort(key=lambda x: x["score"], reverse=True)

    result_doc = {
        "cust_no": user_id,
        "curation_list": curation_list,
        "create_dt": pd.Timestamp.now(),
        "modi_dt": pd.Timestamp.now(),
    }
    logger.info(
        f"{log_prefix} Generated final document with {len(curation_list)} scored candidates."
    )
    return result_doc

