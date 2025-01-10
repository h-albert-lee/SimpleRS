def rank_candidates(candidates):
    # 간단한 Rule-Based 순위화
    return sorted(candidates, key=lambda x: x.get("popularity_score", 0), reverse=True)
