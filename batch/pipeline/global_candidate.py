# simplers/batch/pipeline/global_candidate.py
import logging
from dask import delayed, compute
from typing import List, Dict, Any, Set

# DB 클라이언트/풀 가져오는 함수 (컨텍스트 생성 시 필요)
from batch.utils.db_manager import get_mongo_db, get_os_client, get_oracle_pool
# 공통 데이터 로딩 함수 (필요시 정의)
# from batch.utils.data_loader import fetch_latest_stock_data # 예시

# --- 규칙 클래스 직접 임포트 ---
from batch.rules.global_rules import GlobalStockTopReturnRule, GlobalTopLikeContentRule

logger = logging.getLogger(__name__)

def compute_global_candidates(context: Dict[str, Any]) -> List[str]:
    """
    컨텍스트를 받아 글로벌 후보를 생성합니다. (규칙은 컨텍스트를 사용)
    """
    logger.info("Computing global candidates...")
    all_candidates: Set[str] = set()
    # 컨텍스트에서 필요한 정보 추출 (contents_list는 필수적)
    # contents_list = context.get('contents_list', []) # 필요시 사용

    # --- 1. 순차 실행 규칙 ---
    sequential_rules = [
        # 필요시 순차 실행 규칙 인스턴스 추가
    ]

    if sequential_rules:
        logger.debug(f"Applying {len(sequential_rules)} sequential global rules...")
        for rule in sequential_rules:
            rule_name = getattr(rule, 'rule_name', type(rule).__name__) # 규칙 이름 가져오기
            try:
                # 컨텍스트 객체 전달
                rule_candidates = rule.apply(context)
                if isinstance(rule_candidates, list):
                    count = len(rule_candidates)
                    logger.debug(f"Seq Rule '{rule_name}' generated {count} candidates.")
                    all_candidates.update(rule_candidates)
                else:
                     logger.warning(f"Seq Rule '{rule_name}' did not return a list. Type: {type(rule_candidates)}")
            except Exception as e:
                logger.error(f"Error applying sequential global rule {rule_name}: {e}", exc_info=True)
        logger.debug(f"Candidates after sequential global rules: {len(all_candidates)}")
    else:
        logger.debug("No sequential global rules to apply.")


    # --- 2. 병렬 실행 규칙 ---
    parallel_rules = [
        GlobalStockTopReturnRule(),
        GlobalTopLikeContentRule(),
    ]

    if not parallel_rules:
        logger.warning("No parallel global rules found!")
        # 순차 결과만 반환 (있다면)
        return list(all_candidates) if all_candidates else []

    logger.debug(f"Applying {len(parallel_rules)} parallel global rules using dask.delayed...")
    delayed_results = []
    for rule in parallel_rules:
        # 컨텍스트 객체 전달
        delayed_result = delayed(rule.apply)(context)
        delayed_results.append(delayed_result)

    # 병렬 실행 및 결과 취합
    try:
        results_tuple = compute(*delayed_results)
        logger.debug("Parallel global rules computation finished. Aggregating results...")

        for i, rule_candidates in enumerate(results_tuple):
            rule_name = getattr(parallel_rules[i], 'rule_name', type(parallel_rules[i]).__name__)
            if isinstance(rule_candidates, list):
                count = len(rule_candidates)
                logger.debug(f"Parallel Rule '{rule_name}' generated {count} candidates.")
                all_candidates.update(rule_candidates)
            else:
                 logger.warning(f"Parallel Global Rule '{rule_name}' did not return a list. Result type: {type(rule_candidates)}")

    except Exception as e:
        logger.error(f"Error during parallel global rule computation or aggregation: {e}", exc_info=True)

    final_candidate_list = list(all_candidates)
    logger.info(f"Total global candidates generated: {len(final_candidate_list)}")
    return final_candidate_list