import asyncio

import pytest

from app.utils.concurrency import bounded_gather


async def test_results_in_input_order_regardless_of_completion_order():
    async def slow_for_small(n: int) -> int:
        await asyncio.sleep(0.01 * (5 - n))
        return n * 10

    assert await bounded_gather([1, 2, 3, 4], slow_for_small, limit=4) == [10, 20, 30, 40]


async def test_never_exceeds_limit():
    in_flight = {"now": 0, "max": 0}

    async def track(_: int) -> None:
        in_flight["now"] += 1
        in_flight["max"] = max(in_flight["max"], in_flight["now"])
        await asyncio.sleep(0.005)
        in_flight["now"] -= 1

    await bounded_gather(list(range(10)), track, limit=3)
    assert in_flight["max"] == 3


async def test_empty_input_returns_empty_list():
    async def never(_: int) -> int:
        raise AssertionError("must not be called")

    assert await bounded_gather([], never, limit=2) == []


async def test_exception_propagates():
    async def boom(n: int) -> int:
        if n == 2:
            raise ValueError("two")
        return n

    with pytest.raises(ValueError, match="two"):
        await bounded_gather([1, 2, 3], boom, limit=2)


async def test_first_exception_cancels_the_remaining_calls():
    finished: list[int] = []

    async def fail_fast_or_finish_slowly(n: int) -> int:
        if n == 0:
            raise ValueError("zero")
        await asyncio.sleep(0.05)
        finished.append(n)
        return n

    with pytest.raises(ValueError, match="zero") as exc_info:
        await bounded_gather([0, 1, 2], fail_fast_or_finish_slowly, limit=3)
    assert not isinstance(exc_info.value, ExceptionGroup)
    await asyncio.sleep(0.1)
    assert finished == []


async def test_simultaneous_failures_surface_as_an_exception_group():
    async def boom(n: int) -> int:
        raise ValueError(str(n))

    with pytest.raises(ExceptionGroup) as exc_info:
        await bounded_gather([1, 2], boom, limit=2)
    assert len(exc_info.value.exceptions) == 2


async def test_limit_must_be_positive():
    async def ident(n: int) -> int:
        return n

    with pytest.raises(ValueError, match="limit"):
        await bounded_gather([1], ident, limit=0)
