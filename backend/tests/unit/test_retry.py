import pytest

from app.schemas.common import RetryPolicy
from app.utils import retry as retry_module
from app.utils.retry import retry_async


class Boom(Exception):
    pass


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        calls.append(delay)

    monkeypatch.setattr(retry_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(retry_module.random, "uniform", lambda a, b: 0.0)
    return calls


async def test_returns_value_without_retry(sleeps):
    async def ok():
        return 42

    assert await retry_async(ok, policy=RetryPolicy(), should_retry=lambda e: True) == 42
    assert sleeps == []


async def test_retries_while_predicate_true_then_succeeds(sleeps):
    n = {"calls": 0}

    async def flaky():
        n["calls"] += 1
        if n["calls"] < 3:
            raise Boom()
        return "ok"

    out = await retry_async(flaky, policy=RetryPolicy(max_attempts=4, base_delay=0.5), should_retry=lambda e: True)
    assert out == "ok"
    assert n["calls"] == 3
    assert sleeps == [0.5, 1.0]  # exponential, jitter zeroed by the fixture


async def test_reraises_immediately_when_predicate_false(sleeps):
    n = {"calls": 0}

    async def fatal():
        n["calls"] += 1
        raise Boom()

    with pytest.raises(Boom):
        await retry_async(fatal, policy=RetryPolicy(), should_retry=lambda e: False)
    assert n["calls"] == 1
    assert sleeps == []


async def test_gives_up_after_max_attempts(sleeps):
    n = {"calls": 0}

    async def always():
        n["calls"] += 1
        raise Boom()

    with pytest.raises(Boom):
        await retry_async(always, policy=RetryPolicy(max_attempts=4), should_retry=lambda e: True)
    assert n["calls"] == 4
    assert len(sleeps) == 3


def test_retry_policy_is_strict():
    with pytest.raises(Exception):
        RetryPolicy(max_attempts=4, bogus=1)  # type: ignore[call-arg]
    with pytest.raises(Exception):
        RetryPolicy(max_attempts=0)
