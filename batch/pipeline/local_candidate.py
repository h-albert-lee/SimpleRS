# simplers/batch/pipeline/local_candidate.py
import logging
from dask import delayed, compute
from typing import List, Dict, Any, Set

# --- 규칙 클래스 직접 임포트 ---
from batch.rules.local_rules import (
    LocalMarketContentRule, LocalOwnedStockContentRule, LocalSectorContentRule
)
from batch.utils.data_loader import fetch_user_portfolio

logger = logging.getLogger(__name__)

def compute_local_candidates(user: Dict[str, Any], context: Dict[str, Any]) -> List[str]:  # context 인자 추가
    """개별 사용자 정보(user)와 컨텍스트(context)를 받아 로컬 후보를 생성합니다."""
    user_id = user.get('cust_no', 'UNKNOWN_USER')  # 사용자 식별자 (user 딕셔너리 내 필드 확인)
    log_prefix = f"[User: {user_id}]"
    logger.debug(f"{log_prefix} Computing local candidates...")
    all_candidates: Set[str] = set()

    # --- 사용자 포트폴리오 사전 로딩 ---
    portfolio_data = context.get('portfolio_data')
    if portfolio_data is None:
        portfolio_data = fetch_user_portfolio(user_id)
    user_context = dict(context)
    user_context['portfolio_data'] = portfolio_data

    # --- 1. 순차 실행이 필요한 규칙들 ---
    sequential_rules = [
        # 순차 실행이 필요한 규칙이 있다면 여기에 추가
    ]

    if sequential_rules:
        logger.debug(f"{log_prefix} Applying {len(sequential_rules)} sequential local rules...")
        for rule in sequential_rules:
            rule_name = getattr(rule, 'rule_name', type(rule).__name__)
            try:
                # 사용자 정보와 컨텍스트 전달
                rule_candidates = rule.apply(user, user_context)
                if isinstance(rule_candidates, list):
                    count = len(rule_candidates)
                    logger.debug(f"{log_prefix} Seq Rule '{rule_name}' generated {count} candidates.")
                    all_candidates.update(rule_candidates)
                else:
                    logger.warning(f"{log_prefix} Seq Rule '{rule_name}' did not return a list. Type: {type(rule_candidates)}")
            except Exception as e:
                logger.error(f"{log_prefix} Error applying sequential rule {rule_name}: {e}", exc_info=True)
        logger.debug(f"{log_prefix} Candidates after sequential rules: {len(all_candidates)}")
    else:
        logger.debug(f"{log_prefix} No sequential local rules to apply.")


    # --- 2. 병렬 실행이 가능한 규칙들 ---
    parallel_rules = [
        LocalMarketContentRule(),
        LocalOwnedStockContentRule(),
        LocalSectorContentRule(),
    ]

    if not parallel_rules:
        logger.debug(f"{log_prefix} No parallel local rules to apply.")
        # 순차 결과만 리스트로 변환하여 반환
        return list(all_candidates) if all_candidates else []

    logger.debug(f"{log_prefix} Applying {len(parallel_rules)} parallel local rules using dask.delayed...")
    delayed_results = []
    for rule in parallel_rules:
        # 사용자 정보와 컨텍스트 전달
        delayed_result = delayed(rule.apply)(user, user_context)
        delayed_results.append(delayed_result)

    # 병렬 실행 및 결과 취합
    try:
        results_tuple = compute(*delayed_results)
        logger.debug(f"{log_prefix} Parallel rules computation finished. Aggregating results...")

        for i, rule_candidates in enumerate(results_tuple):
            rule_name = getattr(parallel_rules[i], 'rule_name', type(parallel_rules[i]).__name__)
            if isinstance(rule_candidates, list):
                count = len(rule_candidates)
                logger.debug(f"{log_prefix} Parallel Rule '{rule_name}' generated {count} candidates.")
                all_candidates.update(rule_candidates)
            else:
                 logger.warning(f"{log_prefix} Parallel Rule '{rule_name}' did not return a list. Result type: {type(rule_candidates)}")

    except Exception as e:
        logger.error(f"{log_prefix} Error during parallel rule computation or aggregation: {e}", exc_info=True)

    final_candidate_list = list(all_candidates)
    logger.info(f"{log_prefix} Total local candidates generated: {len(final_candidate_list)}")
    return final_candidate_list