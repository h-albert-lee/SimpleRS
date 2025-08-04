# simplers/batch/rules/cluster_rules.py
import logging
from typing import List, Dict, Any # 추가
from .base import BaseClusterRule

# --- 레지스트리 및 데코레이터 정의 (유지) ---
CLUSTER_RULE_REGISTRY = {}

def register_cluster_rule(rule_name):
    def decorator(rule_class):
        CLUSTER_RULE_REGISTRY[rule_name] = rule_class()
        return rule_class
    return decorator

logger = logging.getLogger(__name__)

@register_cluster_rule("cluster_interest")
class ClusterInterestRule(BaseClusterRule):
    rule_name = "ClusterInterestRule"

    def apply(self, cluster_users: List[Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
        # cluster_id = context.get('current_cluster_id', 'UNKNOWN') # 컨텍스트에서 클러스터 ID 가져오기 (선택)
        logger.debug(f"Applying rule: {self.rule_name} for cluster") # 클러스터 ID 로깅 추가 가능
        contents_list = context.get('contents_list', [])
        if not contents_list or not cluster_users:
            return []

        candidate_set = set()
        try:
            # 클러스터 내 사용자들의 선호 카테고리 집계 (예시 로직)
            preferred_categories = set()
            for user in cluster_users:
                # 사용자 데이터에서 선호 카테고리 필드 확인 필요 (예: 'preferred_category')
                pref_cat = user.get('preferred_category') # 필드명은 user 스키마에 따라 달라짐
                if pref_cat:
                    preferred_categories.add(pref_cat)

            if not preferred_categories:
                logger.debug(f"{self.rule_name}: No preferred categories found for this cluster.")
                return []

            logger.debug(f"{self.rule_name}: Target preferred categories for cluster: {preferred_categories}")

            # 콘텐츠 목록에서 해당 카테고리 필터링
            for content in contents_list:
                # 콘텐츠의 카테고리 필드 확인 필요 (예: 'category', 'btopic')
                content_category = content.get('category') # 필드명은 curation 스키마에 따라 달라짐
                if content_category in preferred_categories:
                    candidate_set.add(content.get("id"))

            candidate_list = list(candidate_set)
            logger.info(f"{self.rule_name}: Found {len(candidate_list)} candidates for cluster.")
            return candidate_list

        except Exception as e:
            logger.error(f"{self.rule_name}: Error during processing for cluster: {e}", exc_info=True)
            return []