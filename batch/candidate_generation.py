# simplers/batch/candidate_generation.py
import logging
import pandas as pd
from dask import delayed, compute
from typing import Dict, Any, List
import sys
import traceback
from datetime import datetime
import signal
import os

# 데이터 로딩 및 DB 관리 함수
from batch.utils.db_manager import (
    load_users, load_contents, save_results,
    get_mongo_db, get_os_client, get_oracle_pool,
    close_mongo, close_opensearch, close_oracle,
    MongoDBError, OpenSearchError, DataIntegrityError
)
# 로깅 설정
from batch.utils.logging_setup import setup_logging
from batch.utils.config_loader import MAX_CANDIDATES_PER_USER
# 파이프라인 함수
from batch.pipeline.global_candidate import compute_global_candidates
from batch.pipeline.final_candidate import generate_candidate_for_user
# 데이터 로더
from batch.utils.data_loader import load_user_interactions, APIConnectionError, DataValidationError

# --- 로깅 설정 ---
setup_logging()
logger = logging.getLogger(__name__)

class BatchProcessError(Exception):
    """배치 프로세스 관련 예외"""
    pass

class BatchInterruptedError(BatchProcessError):
    """배치 프로세스 중단 예외"""
    pass

# 전역 변수로 정리 작업 추적
cleanup_performed = False

def signal_handler(signum, frame):
    """시그널 핸들러 - 배치 프로세스 안전 종료"""
    global cleanup_performed
    
    logger.warning(f"Received signal {signum}. Initiating graceful shutdown...")
    
    if not cleanup_performed:
        cleanup_resources()
        cleanup_performed = True
    
    logger.info("Graceful shutdown completed.")
    sys.exit(1)

def cleanup_resources():
    """리소스 정리 함수"""
    try:
        logger.info("Cleaning up database connections...")
        close_mongo()
        close_opensearch() 
        close_oracle()
        logger.info("Resource cleanup completed.")
    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")

def validate_environment():
    """실행 환경 검증"""
    logger.info("Validating execution environment...")
    
    # 필수 환경 변수 체크
    required_env_vars = []  # 필요시 추가
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        raise BatchProcessError(f"Missing required environment variables: {missing_vars}")
    
    # 메모리 체크 (간단한 체크)
    try:
        import psutil
        memory = psutil.virtual_memory()
        if memory.available < 1024 * 1024 * 1024:  # 1GB 미만
            logger.warning(f"Low available memory: {memory.available / (1024**3):.2f}GB")
    except ImportError:
        logger.debug("psutil not available for memory check")
    
    logger.info("Environment validation completed.")

def main():
    """메인 배치 프로세스 함수"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 80)
    logger.info("Starting candidate generation batch process...")
    logger.info(f"Process started at: {datetime.now()}")
    logger.info("=" * 80)
    
    start_time = pd.Timestamp.now()
    db = None
    final_results_to_save = []
    success = False

    try:
        # 환경 검증
        validate_environment()
        
        # --- DB 연결 ---
        logger.info("Establishing database connections...")
        try:
            db = get_mongo_db()
            os_client = get_os_client()
            oracle_pool = get_oracle_pool()
            logger.info("All database connections established successfully.")
        except (MongoDBError, OpenSearchError) as e:
            logger.error(f"Database connection failed: {e}")
            raise BatchProcessError(f"Failed to establish database connections: {e}")

        # --- 기본 데이터 로딩 ---
        logger.info("Loading base data from MongoDB...")
        try:
            users_ddf = load_users(db)
            contents_ddf = load_contents(db)
        except Exception as e:
            logger.error(f"Failed to load base data: {e}")
            raise BatchProcessError(f"Base data loading failed: {e}")

        # --- 데이터 변환 및 검증 ---
        logger.info("Computing base data to Pandas...")
        try:
            users_pd = users_ddf.compute()
            contents_list = contents_ddf.compute().to_dict('records')
            
            if users_pd.empty:
                raise BatchProcessError("No users found in database")
            
            if not contents_list:
                raise BatchProcessError("No contents found in database")
                
            all_content_ids = [c['id'] for c in contents_list]
            logger.info(f"Loaded {len(users_pd)} users and {len(contents_list)} contents into memory.")
            
        except Exception as e:
            logger.error(f"Data computation failed: {e}")
            raise BatchProcessError(f"Failed to compute base data: {e}")

        # --- 초기 컨텍스트 생성 ---
        logger.info("Creating base context...")
        try:
            base_context: Dict[str, Any] = {
                'contents_list': contents_list,
                'content_meta_map': {c.get('_id', c.get('id')): c for c in contents_list},
                'mongo_db': db,
                'os_client': os_client,
                'oracle_pool': oracle_pool,
                'max_candidates_per_user': MAX_CANDIDATES_PER_USER,
            }
            logger.info("Base context created successfully.")
        except Exception as e:
            logger.error(f"Context creation failed: {e}")
            raise BatchProcessError(f"Failed to create base context: {e}")

        # --- 글로벌 후보 생성 ---
        logger.info("Generating global candidates...")
        try:
            global_candidates = compute_global_candidates(base_context)
            logger.info(f"Generated {len(global_candidates)} global candidates")
        except Exception as e:
            logger.error(f"Global candidate generation failed: {e}")
            # 글로벌 후보 실패는 치명적이지 않음
            global_candidates = []
            logger.warning("Continuing with empty global candidates")

        # --- 기타 후보 생성 ---
        logger.info("Generating other candidates...")
        try:
            from batch.rules.global_rules import GlobalTopLikedContentRule
            other_rule = GlobalTopLikedContentRule()
            other_candidates = other_rule.apply(base_context)
            logger.info(f"Generated {len(other_candidates)} other candidates")
        except Exception as e:
            logger.error(f"Other candidate generation failed: {e}")
            # 기타 후보 실패는 치명적이지 않음
            other_candidates = []
            logger.warning("Continuing with empty other candidates")

        # --- 사용자별 최종 후보 생성 ---
        logger.info(f"Generating final candidates and scores for {len(users_pd)} users...")
        try:
            delayed_results = []
            for _, user_row in users_pd.iterrows():
                user_dict = user_row.to_dict()
                delayed_result = delayed(generate_candidate_for_user)(
                    user_dict, global_candidates, other_candidates, base_context
                )
                delayed_results.append(delayed_result)

            if delayed_results:
                logger.info("Computing delayed results...")
                computed_results = compute(*delayed_results)
                final_results_to_save = [res for res in computed_results if res and res.get('curation_list')]
                logger.info(f"Computed results for {len(computed_results)} users. "
                          f"Found {len(final_results_to_save)} users with valid candidates.")
            else:
                logger.warning("No users to process for final candidate generation.")
                final_results_to_save = []
                
        except Exception as e:
            logger.error(f"Final candidate generation failed: {e}")
            raise BatchProcessError(f"Failed to generate final candidates: {e}")

        # --- 결과 저장 ---
        logger.info("Saving final results...")
        if final_results_to_save:
            try:
                save_success = save_results(final_results_to_save, db, collection_name="user_candidate")
                if save_success:
                    success = True
                    logger.info("Results saved successfully to MongoDB")
                else:
                    logger.warning("Results saved to fallback file only")
            except (MongoDBError, DataIntegrityError) as e:
                logger.error(f"Failed to save results: {e}")
                raise BatchProcessError(f"Result saving failed: {e}")
        else:
            logger.warning("No final results generated to save.")
            success = True  # 결과가 없는 것도 성공으로 간주

    except BatchProcessError as e:
        logger.critical(f"Batch process error: {e}")
        success = False
        
    except (MongoDBError, OpenSearchError, DataIntegrityError) as e:
        logger.critical(f"Database error: {e}")
        success = False
        
    except (APIConnectionError, DataValidationError) as e:
        logger.critical(f"External API error: {e}")
        success = False
        
    except KeyboardInterrupt:
        logger.warning("Batch process interrupted by user")
        success = False
        
    except Exception as e:
        logger.critical(f"Unexpected error during candidate generation process: {e}", exc_info=True)
        success = False

    finally:
        # --- 리소스 정리 ---
        if not cleanup_performed:
            cleanup_resources()

        # --- 최종 결과 로깅 ---
        end_time = pd.Timestamp.now()
        total_duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 80)
        if success:
            logger.info("✅ BATCH PROCESS COMPLETED SUCCESSFULLY")
            logger.info(f"📊 Processed {len(final_results_to_save)} users with candidates")
        else:
            logger.error("❌ BATCH PROCESS FAILED")
            
        logger.info(f"⏱️  Total duration: {total_duration:.2f} seconds")
        logger.info(f"🕐 Process ended at: {datetime.now()}")
        logger.info("=" * 80)
        
        # 실패 시 exit code 1로 종료
        if not success:
            sys.exit(1)

if __name__ == '__main__':
    main()
