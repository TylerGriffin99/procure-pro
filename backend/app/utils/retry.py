"""Generic async retry with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from app.schemas.common import RetryPolicy


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    should_retry: Callable[[Exception], bool],
) -> T:
    """Await ``fn()``; on an exception where ``should_retry`` is true and attempts remain,
    sleep ``delay + uniform(0, delay)`` (delay doubling from ``policy.base_delay``) and
    try again. Any other exception, or the final attempt's, is re-raised unchanged.

    The sleep happens inside the caller's concurrency slot on purpose: when an upstream
    is rate-limiting us, we must not launch more calls at it.
    """
    delay = policy.base_delay
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if attempt >= policy.max_attempts or not should_retry(exc):
                raise
            await asyncio.sleep(delay + random.uniform(0, delay))
            delay *= 2
    raise RuntimeError("unreachable: retry loop exhausted without returning or raising")
