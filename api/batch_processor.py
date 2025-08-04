# # api/batch_processor.py
# import asyncio
# from typing import Tuple
# from fastapi.concurrency import run_in_threadpool
# from api.services.ranking import batch_rank_candidates
# from api.services.candidate_fetcher import fetch_candidates

# # 비동기 큐 정의
# request_queue: asyncio.Queue[Tuple[str, asyncio.Future]] = asyncio.Queue()

# async def batch_processor():
#     """
#     1초마다 큐에 있는 요청들을 모아 배치로 처리하는 백그라운드 태스크.
#     """
#     while True:
#         await asyncio.sleep(1)  # 1초 주기로 배치 처리
        
#         current_batch = []
#         # 큐에서 모든 요청 가져오기
#         while not request_queue.empty():
#             request = await request_queue.get()
#             current_batch.append(request)

#         if not current_batch:
#             continue

#         user_ids = []
#         futures = []
#         all_candidates = []

#         # 각 요청에 대해 개별적으로 후보 추출
#         for user_id, response_future in current_batch:
#             try:
#                 candidates = await run_in_threadpool(fetch_candidates, user_id)
#             except Exception as e:
#                 response_future.set_exception(e)
#                 continue

#             if not candidates:
#                 response_future.set_exception(Exception("No candidates found."))
#                 continue

#             user_ids.append(user_id)
#             futures.append(response_future)
#             all_candidates.append(candidates)

#         # 배치 순위화 수행
#         if all_candidates:
#             try:
#                 ranked_results = await run_in_threadpool(batch_rank_candidates, all_candidates, user_ids)
#                 # 각 요청별로 결과 설정
#                 for future, user_id, ranked in zip(futures, user_ids, ranked_results):
#                     future.set_result({"user_id": user_id, "recommendations": ranked})
#             except Exception as e:
#                 for future in futures:
#                     if not future.done():
#                         future.set_exception(e)
