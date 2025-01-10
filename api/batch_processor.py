# api/batch_processor.py
import asyncio
from typing import Tuple
from fastapi.concurrency import run_in_threadpool
from api.services.ranking import rank_candidates
from api.services.candidate_fetcher import fetch_candidates

# 요청 큐: (user_id, asyncio.Future) 튜플
request_queue: asyncio.Queue[Tuple[str, asyncio.Future]] = asyncio.Queue()

async def batch_processor():
    """
    1초마다 큐에 있는 요청들을 처리하여 배치로 응답하는 백그라운드 태스크.
    """
    while True:
        await asyncio.sleep(1)  # 1초 주기로 배치 처리
        
        batch = []
        # 큐에서 모든 요청 가져오기
        while not request_queue.empty():
            batch.append(await request_queue.get())

        if not batch:
            continue

        # 각 요청 처리
        for user_id, response_future in batch:
            try:
                # CF 및 Ranking 작업을 스레드 풀에서 실행
                candidates = await run_in_threadpool(fetch_candidates, user_id)
                if not candidates:
                    response_future.set_exception(Exception("No candidates found."))
                    continue
                ranked = await run_in_threadpool(rank_candidates, candidates, user_id)
                response_future.set_result({"user_id": user_id, "recommendations": ranked})
            except Exception as e:
                response_future.set_exception(e)
