# simplers/batch/candidate_generation.py
import logging
import pandas as pd
from dask import delayed, compute
from typing import Dict, Any, List # List 추가

# 데이터 로딩 및 DB 관리 함수
from batch.utils.db_manager import (
    load_users, load_contents, save_results,
    get_mongo_db, get_os_client, get_oracle_pool,
    close_mongo, close_opensearch, close_oracle
)
# 로깅 설정
from batch.utils.logging_setup import setup_logging
# 파이프라인 함수
from batch.pipeline.global_candidate import compute_global_candidates
from batch.pipeline.final_candidate import generate_candidate_for_user
# 데이터 로더
from batch.utils.data_loader import load_user_interactions

# --- 로깅 설정 ---
setup_logging()
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting candidate generation batch process...")
    start_time = pd.Timestamp.now()

    db = None
    final_results_to_save = []

    try:
        # --- DB 연결 ---
        db = get_mongo_db()
        os_client = get_os_client()
        oracle_pool = get_oracle_pool()
        logger.info("Database connections established.")

        # --- 기본 데이터 로딩 ---
        users_ddf = load_users(db)
        contents_ddf = load_contents(db)

        # --- 데이터 변환 및 리스트 생성 ---
        logger.info("Computing base data to Pandas...")
        users_pd = users_ddf.compute()
        contents_list = contents_ddf.compute().to_dict('records')
        all_content_ids = [c['id'] for c in contents_list] # 전체 콘텐츠 ID 목록
        logger.info(f"Loaded {len(users_pd)} users and {len(contents_list)} contents into memory.")

        # --- 초기 컨텍스트 생성 ---
        logger.info("Creating base context...")
        base_context: Dict[str, Any] = {
            'contents_list': contents_list,
            'content_meta_map': {c.get('_id', c.get('id')): c for c in contents_list},
            'mongo_db': db,
            'os_client': os_client,
            'oracle_pool': oracle_pool,
            'max_candidates_per_user': 100,
        }
        logger.info("Base context created.")

        # --- 글로벌 후보 생성 (실시간 시세 상승률 top 10) ---
        global_candidates = compute_global_candidates(base_context)

        # --- 기타 후보 생성 (liked_users가 높은 컨텐츠) ---
        # GlobalTopLikedContentRule을 직접 사용
        from batch.rules.global_rules import GlobalTopLikedContentRule
        other_rule = GlobalTopLikedContentRule()
        other_candidates = other_rule.apply(base_context)

        # --- 사용자별 최종 후보 생성 (병렬 처리) ---
        logger.info(f"Generating final candidates and scores for {len(users_pd)} users...")
        delayed_results = []
        for _, user_row in users_pd.iterrows():
            user_dict = user_row.to_dict()
            delayed_result = delayed(generate_candidate_for_user)(
                user_dict, global_candidates, other_candidates, base_context
            )
            delayed_results.append(delayed_result)

        if delayed_results:
            computed_results = compute(*delayed_results)
            final_results_to_save = [res for res in computed_results if res and res.get('curation_list')]
            logger.info(f"Computed results for {len(computed_results)} users. Saving {len(final_results_to_save)} valid results.")
        else:
            logger.warning("No users to process for final candidate generation.")

        # --- 결과 저장 ---
        if final_results_to_save:
            save_results(final_results_to_save, db, collection_name="user_candidate")
        else:
            logger.warning("No final results generated to save.")

    except Exception as e:
        logger.critical(f"An error occurred during the candidate generation process: {e}", exc_info=True)

    finally:
        # --- DB 연결 종료 ---
        logger.info("Closing database connections...")
        close_mongo()
        close_opensearch()
        close_oracle()
        logger.info("Database connections closed.")

        end_time = pd.Timestamp.now()
        total_duration = (end_time - start_time).total_seconds()
        logger.info(f"Candidate generation batch process finished. Total duration: {total_duration:.2f} seconds.")

if __name__ == '__main__':
    main()