import asyncio
import logging
from collections.abc import Awaitable
from typing import List, Optional, TypeVar, Tuple

T = TypeVar("T")


async def gather_limited(
    awaitables: List[Awaitable[T]],
    limit: int,
    *,
    logger: Optional[logging.Logger] = None,
) -> List[T]:
    if not awaitables:
        return []

    concurrency = min(len(awaitables), max(1, limit))
    queue: asyncio.Queue[Tuple[int, Awaitable[T]]] = asyncio.Queue()
    results: List[Optional[T]] = [None] * len(awaitables)
    errors: List[BaseException] = []

    for index, awaitable in enumerate(awaitables):
        queue.put_nowait((index, awaitable))

    async def worker(worker_id: int) -> None:
        while True:
            try:
                index, awaitable = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                results[index] = await awaitable
            except Exception as exc:
                if logger is not None:
                    logger.warning(
                        "gather_limited worker %s failed at index %s: %s",
                        worker_id,
                        index,
                        exc,
                        exc_info=True,
                    )
                errors.append(exc)
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker(worker_id)) for worker_id in range(concurrency)]
    try:
        await queue.join()
    finally:
        await asyncio.gather(*workers, return_exceptions=True)

    if errors:
        raise errors[0]

    return results 
