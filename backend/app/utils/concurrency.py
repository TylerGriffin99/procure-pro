from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence


async def bounded_gather[T, R](items: Sequence[T], fn: Callable[[T], Awaitable[R]], *, limit: int) -> list[R]:
    """Run ``fn`` over ``items`` with at most ``limit`` coroutines in flight.

    Results come back in input order. The first exception cancels the remaining calls and
    propagates as itself (not as a one-member ExceptionGroup); the semaphore wraps the whole per-item call.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    semaphore = asyncio.Semaphore(limit)
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(run_with_semaphore(semaphore, fn, item)) for item in items]
    except ExceptionGroup as failures:
        if len(failures.exceptions) == 1:
            raise failures.exceptions[0] from None
        raise
    return [task.result() for task in tasks]


async def run_with_semaphore[T, R](semaphore: asyncio.Semaphore, fn: Callable[[T], Awaitable[R]], item: T) -> R:
    async with semaphore:
        return await fn(item)
