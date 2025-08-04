import logging
from dask import delayed, compute
import pandas as pd
from typing import List, Dict, Any, Set, Tuple # Tuple 추가

# --- 규칙 클래스 직접 임포트 ---
from batch.rules.cluster_rules import ClusterInterestRule

logger = logging.getLogger(__name__)

def compute_candidates_for_single_cluster(
    cluster_id: Any,
    cluster_users: List[Dict[str, Any]],
    base_context: Dict[str, Any]
) -> Tuple[Any, List[str]]: # 반환 타입을 튜플로 변경 (클러스터 ID 포함)
    """단일 클러스터에 대해 규칙을 적용하여 후보군 생성 (병렬 처리 대상 함수)"""

    log_prefix = f"[Cluster: {cluster_id}]"
    logger.debug(f"{log_prefix} Computing candidates for {len(cluster_users)} users...")
    all_candidates: Set[str] = set()

    # --- 클러스터 레벨 컨텍스트 생성 (base_context 복사 후 수정) ---
    # 클러스터별로 컨텍스트를 약간 수정해야 할 경우 사용
    context = base_context.copy()
    context['current_cluster_id'] = cluster_id # 현재 처리 중인 클러스터 ID 추가
    # context['cluster_users'] = cluster_users # 필요시 사용자 목록도 컨텍스트에 추가

    # --- 1. 순차 실행 규칙 (클러스터 레벨) ---
    sequential_rules = [
        # 필요시 순차 실행 클러스터 규칙 인스턴스 추가
    ]

    if sequential_rules:
        logger.debug(f"{log_prefix} Applying {len(sequential_rules)} sequential cluster rules...")
        for rule in sequential_rules:
            rule_name = getattr(rule, 'rule_name', type(rule).__name__)
            try:
                # 클러스터 사용자 목록과 컨텍스트 전달
                rule_candidates = rule.apply(cluster_users, context)
                if isinstance(rule_candidates, list):
                    count = len(rule_candidates)
                    logger.debug(f"{log_prefix} Seq Rule '{rule_name}' generated {count} candidates.")
                    all_candidates.update(rule_candidates)
                else:
                    logger.warning(f"{log_prefix} Seq Rule '{rule_name}' did not return a list. Type: {type(rule_candidates)}")
            except Exception as e:
                 logger.error(f"{log_prefix} Error applying seq cluster rule {rule_name}: {e}", exc_info=True)
        logger.debug(f"{log_prefix} Candidates after seq rules: {len(all_candidates)}")
    else:
         logger.debug(f"{log_prefix} No sequential cluster rules to apply.")


    # --- 2. 병렬 실행 규칙 (클러스터 레벨) ---
    parallel_rules = [
        ClusterInterestRule(),
        # 다른 병렬 실행 가능 클러스터 규칙 추가
    ]

    if not parallel_rules:
         logger.warning(f"{log_prefix} No parallel cluster rules found!")
         # 클러스터 ID와 현재까지의 후보 리스트 반환
         return cluster_id, list(all_candidates)

    logger.debug(f"{log_prefix} Applying {len(parallel_rules)} parallel cluster rules...")
    # 클러스터 레벨에서는 규칙 수가 적으면 dask 오버헤드가 클 수 있으므로 순차 실행 유지 (이전과 동일)
    for rule in parallel_rules:
        rule_name = getattr(rule, 'rule_name', type(rule).__name__)
        try:
            # 클러스터 사용자 목록과 컨텍스트 전달
            rule_candidates = rule.apply(cluster_users, context)
            if isinstance(rule_candidates, list):
                count = len(rule_candidates)
                logger.debug(f"{log_prefix} Parallel Rule '{rule_name}' generated {count} candidates (executed sequentially).")
                all_candidates.update(rule_candidates)
            else:
                logger.warning(f"{log_prefix} Parallel Rule '{rule_name}' did not return a list. Type: {type(rule_candidates)}")
        except Exception as e:
            logger.error(f"{log_prefix} Error applying parallel cluster rule {rule_name}: {e}", exc_info=True)


    final_candidate_list = list(all_candidates)
    logger.info(f"{log_prefix} Total cluster candidates generated: {len(final_candidate_list)}")
    # 클러스터 ID와 최종 후보 리스트 반환
    return cluster_id, final_candidate_list


def compute_cluster_candidates(users_pd: pd.DataFrame, base_context: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    사용자 데이터를 클러스터별로 그룹화하고, 각 클러스터 후보 생성을 병렬 처리.
    base_context를 각 클러스터 처리 함수에 전달합니다.
    """
    logger.info("Computing cluster candidates for all clusters...")
    if 'cluster_id' not in users_pd.columns:
        logger.error("'cluster_id' column not found in users DataFrame. Cannot compute cluster candidates.")
        return {}

    grouped = users_pd.groupby('cluster_id')
    delayed_cluster_results = []

    logger.info(f"Processing {len(grouped)} clusters in parallel using dask.delayed...")
    for cluster_id, group in grouped:
        cluster_users = [row.to_dict() for _, row in group.iterrows()]
        # 각 클러스터별 후보 생성 함수에 base_context 전달
        delayed_result = delayed(compute_candidates_for_single_cluster)(
            cluster_id, cluster_users, base_context
        )
        delayed_cluster_results.append(delayed_result)

    if not delayed_cluster_results:
        logger.warning("No clusters found to process.")
        return {}

    final_cluster_candidates: Dict[str, List[str]] = {} # 타입 명시
    try:
        # compute 결과는 (cluster_id, candidate_list) 튜플의 리스트
        results_list_of_tuples = compute(*delayed_cluster_results)
        logger.info("Cluster candidate computation finished. Aggregating results...")

        # 각 클러스터 결과 (튜플) 를 최종 딕셔너리에 통합
        for result_tuple in results_list_of_tuples:
            if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                cluster_id, candidate_list = result_tuple
                # 클러스터 ID를 문자열 키로 사용 (JSON 호환성 등)
                final_cluster_candidates[str(cluster_id)] = candidate_list
            else:
                logger.warning(f"Unexpected result type from cluster computation: {type(result_tuple)}")

    except Exception as e:
        logger.error(f"Error during parallel cluster computation or aggregation: {e}", exc_info=True)

    total_candidates = sum(len(cands) for cands in final_cluster_candidates.values())
    logger.info(f"Finished computing cluster candidates for {len(final_cluster_candidates)} clusters. Total candidates generated: {total_candidates}")
    return final_cluster_candidates