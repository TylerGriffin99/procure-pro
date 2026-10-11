"""Bounded fan-out for async work."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence


async def bounded_gather[T, R](items: Sequence[T], fn: Callable[[T], Awaitable[R]], *, limit: int) -> list[R]:
    """Run ``fn`` over ``items`` with at most ``limit`` coroutines in flight.

    Results come back in input order. The first exception propagates, as with
    ``asyncio.gather`` defaults; the semaphore wraps the whole per-item call.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    semaphore = asyncio.Semaphore(limit)
    return list(await asyncio.gather(*(run_with_semaphore(semaphore, fn, item) for item in items)))


async def run_with_semaphore[T, R](semaphore: asyncio.Semaphore, fn: Callable[[T], Awaitable[R]], item: T) -> R:
    async with semaphore:
        return await fn(item)
