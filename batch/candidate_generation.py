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
from batch.pipeline.cluster_candidate import compute_cluster_candidates
from batch.pipeline.final_candidate import generate_candidate_for_user
# CB/CF 유틸리티 및 데이터 로더
from batch.utils.cb_utils import build_tfidf_vectors
from batch.utils.cf_utils import build_item_similarity
from batch.utils.data_loader import load_user_interactions # 사용자 상호작용 로더 (신규 필요)

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

        # --- CF/CB 위한 데이터 준비 ---
        logger.info("Preparing data for CF/CB...")
        # 1. 사용자 상호작용 데이터 로드 (예: MongoDB curation-logs)
        #    data_loader 모듈에 함수 구현 필요
        #    반환 형태: {user_id: [item_id1, item_id2, ...]}
        user_interactions = load_user_interactions(db, users_pd['id'].tolist()) # 예시 호출
        logger.info(f"Loaded interactions for {len(user_interactions)} users.")

        # 2. CB: TF-IDF 벡터 생성
        cb_ready = build_tfidf_vectors(contents_list)
        if not cb_ready:
            logger.warning("CB features (TF-IDF) could not be built. CB scoring will be skipped.")

        # 3. CF: Item-Item 유사도 계산
        cf_ready = build_item_similarity(user_interactions, all_content_ids)
        if not cf_ready:
             logger.warning("CF features (Item Similarity) could not be built. CF scoring will be skipped.")

        # --- 초기 컨텍스트 생성 ---
        logger.info("Creating base context...")
        base_context: Dict[str, Any] = {
            'contents_list': contents_list, # CB 등에서 사용 가능
            'content_meta_map': {c['id']: c for c in contents_list}, # ID로 메타데이터 빠른 조회용
            'user_interactions': user_interactions, # CB, CF 에서 사용
            # CB/CF 계산 결과는 utils 모듈 전역 변수에 저장되었으므로 context에 넣지 않아도 됨
            # 필요시 명시적으로 전달하려면 여기에 추가:
            # 'tfidf_vectorizer': cb_utils.tfidf_vectorizer,
            # 'item_tfidf_vectors': cb_utils.item_tfidf_vectors,
            # 'item_id_to_index_cb': cb_utils.item_id_to_index,
            # 'item_similarity_matrix': cf_utils.item_similarity_matrix,
            # 'item_id_map_cf': cf_utils.item_id_map_cf,
            'mongo_db': db,
            'os_client': os_client,
            'oracle_pool': oracle_pool,
        }
        logger.info("Base context created.")

        # --- 글로벌 후보 생성 ---
        global_candidates = compute_global_candidates(base_context)

        # --- 클러스터 후보 생성 ---
        cluster_candidates_map = compute_cluster_candidates(users_pd, base_context)

        # --- 사용자별 최종 후보 생성 (병렬 처리) ---
        logger.info(f"Generating final candidates and scores for {len(users_pd)} users...")
        delayed_results = []
        for _, user_row in users_pd.iterrows():
            user_dict = user_row.to_dict()
            delayed_result = delayed(generate_candidate_for_user)(
                user_dict, global_candidates, cluster_candidates_map, base_context
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
            save_results(final_results_to_save, db, collection_name="user_candidate_prod")
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
    # --- 신규 필요한 모듈 임포트 ---
    import pandas as pd
    # 사용자 상호작용 로더 구현 필요 (예시)
    # 아래 함수는 별도 파일(예: batch/utils/data_loader.py)에 구현 필요
    def load_user_interactions(db, user_ids: List[str]) -> Dict[str, List[str]]:
        logger.info(f"Loading user interactions for {len(user_ids)} users...")
        interactions = defaultdict(list)
        try:
            # 예시: MongoDB의 curation_logs 컬렉션에서 조회 (최근 N일 등 필터링 필요)
            # 실제 구현 시 날짜 범위, 사용자 ID $in 쿼리 등 사용
            # logs_collection = db['curation_logs'] # 컬렉션 이름 확인 필요
            # cursor = logs_collection.find({"user_id": {"$in": user_ids}}, {"user_id": 1, "item_id": 1, "timestamp": 1}).sort("timestamp", -1)
            # for log in cursor:
            #     interactions[log['user_id']].append(log['item_id'])

            # --- 임시 더미 데이터 ---
            logger.warning("Using dummy user interaction data for CF/CB!")
            items = [f'item_{i}' for i in range(100)]
            for i, user_id in enumerate(user_ids):
                 if i < 10: # 일부 유저에게만 기록 부여
                     interactions[user_id] = np.random.choice(items, size=20, replace=False).tolist()

        except Exception as e:
            logger.error(f"Error loading user interactions: {e}", exc_info=True)
        return interactions

    main()