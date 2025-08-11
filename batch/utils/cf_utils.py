import logging
from typing import Dict, List, Set, Optional
from collections import defaultdict
from itertools import combinations

import pandas as pd

from .config_loader import (
    CF_MIN_CO_OCCURRENCE,
    CF_USER_HISTORY_LIMIT,
)

logger = logging.getLogger(__name__)


class CFModel:
    """Simple item-to-item collaborative filtering model."""

    def __init__(self) -> None:
        self.similarity_matrix: Optional[pd.DataFrame] = None
        self.item_id_map: Optional[Dict[str, int]] = None
        self.item_index_map: Optional[Dict[int, str]] = None
        self.is_ready: bool = False

    def build(self, user_interactions: Dict[str, List[str]]) -> None:
        """Build item similarity matrix using Jaccard similarity."""

        logger.info("Building Item-Item Jaccard similarity matrix...")
        start_time = pd.Timestamp.now()

        if not user_interactions:
            logger.warning(
                "Cannot build item similarity: user_interactions data is empty."
            )
            return

        item_user_sets: Dict[str, Set[str]] = defaultdict(set)
        for user_id, items in user_interactions.items():
            for item_id in set(items):
                item_user_sets[item_id].add(user_id)

        all_items = sorted(item_user_sets.keys())
        self.item_id_map = {item: i for i, item in enumerate(all_items)}
        self.item_index_map = {i: item for i, item in enumerate(all_items)}

        similarity_data = []
        for item1, item2 in combinations(all_items, 2):
            users1 = item_user_sets[item1]
            users2 = item_user_sets[item2]
            intersection_count = len(users1.intersection(users2))

            if intersection_count >= CF_MIN_CO_OCCURRENCE:
                union_count = len(users1.union(users2))
                if union_count > 0:
                    jaccard_sim = intersection_count / union_count
                    similarity_data.append((item1, item2, jaccard_sim))

        if not similarity_data:
            logger.warning(
                "No item pairs met the co-occurrence threshold. Similarity matrix is empty."
            )
            self.similarity_matrix = pd.DataFrame()
            self.is_ready = True
            return

        sim_df = pd.DataFrame(similarity_data, columns=["item1", "item2", "similarity"])
        sim_df_symmetric = pd.concat(
            [sim_df, sim_df.rename(columns={"item1": "item2", "item2": "item1"})]
        )
        self.similarity_matrix = (
            sim_df_symmetric.pivot_table(
                index="item1", columns="item2", values="similarity"
            ).fillna(0)
        )

        self.is_ready = True
        duration = (pd.Timestamp.now() - start_time).total_seconds()
        logger.info(
            "Item similarity matrix built. Shape: %s. Took %.2fs.",
            self.similarity_matrix.shape,
            duration,
        )

    def get_scores(
        self, user_history: List[str], candidate_ids: Set[str]
    ) -> Dict[str, float]:
        """Compute CF scores for candidate items."""

        scores: Dict[str, float] = defaultdict(float)
        if (
            not self.is_ready
            or self.similarity_matrix is None
            or self.similarity_matrix.empty
        ):
            return dict(scores)

        if not user_history or not candidate_ids:
            return dict(scores)

        recent_history = user_history[-CF_USER_HISTORY_LIMIT:]
        valid_history = [item for item in recent_history if item in self.similarity_matrix.index]
        if not valid_history:
            return dict(scores)

        valid_candidates = [
            cand for cand in candidate_ids if cand in self.similarity_matrix.columns
        ]
        if not valid_candidates:
            return dict(scores)

        sim_submatrix = self.similarity_matrix.loc[valid_history, valid_candidates]
        total_similarities = sim_submatrix.sum(axis=0)
        return total_similarities.to_dict()

