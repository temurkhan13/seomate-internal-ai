"""Regression tests for the shared ``@retry_transient`` decorator in _base.

Guards the fix for the dead-filter bug. Before the fix, the decorator used
``retry=retry_if_exception_type(Exception)`` together with an inner try/except
whose two branches both re-raised identically — so ``is_transient`` had no
effect and EVERY exception was retried ``max_attempts`` times. That meant 4xx
caller errors (400 invalid_grant, 401) and even plain ``TypeError``s from our
own bugs were hammered with exponential backoff before surfacing.

The fix moves filtering into the retry predicate (``retry_if_exception(
is_transient)``): transient errors retry, everything else fails fast on the
first attempt. These tests pin that behaviour down.

No network — the decorated function raises constructed exceptions directly.
Backoff is set to zero so the retries don't sleep.
"""
from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from seomate.adapters._base import retry_transient


def _http_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://token.test")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(f"HTTP {status}", request=req, response=resp)


def _decorated(raiser: Callable[[int], BaseException | None]):
    """Build a call-counting @retry_transient function.

    ``raiser(n)`` receives the 1-based attempt number and returns the exception
    to raise on that attempt, or ``None`` to succeed (returning the sentinel
    ``"ok"``). Zero backoff keeps the test fast.
    """
    calls = {"n": 0}

    @retry_transient(max_attempts=4, multiplier=0.0, min_wait=0.0, max_wait=0.0)
    async def fn() -> str:
        calls["n"] += 1
        exc = raiser(calls["n"])
        if exc is not None:
            raise exc
        return "ok"

    return fn, calls


@pytest.mark.asyncio
async def test_4xx_fails_fast_not_retried() -> None:
    """A 400 is a caller error — surfaced on the first attempt, never retried."""
    fn, calls = _decorated(lambda n: _http_error(400))
    with pytest.raises(httpx.HTTPStatusError):
        await fn()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_401_fails_fast_not_retried() -> None:
    """401 (auth) is also non-transient — retrying a bad credential is pointless."""
    fn, calls = _decorated(lambda n: _http_error(401))
    with pytest.raises(httpx.HTTPStatusError):
        await fn()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_own_bug_typeerror_fails_fast() -> None:
    """A plain TypeError from our own code is not transient — fail fast rather
    than hammer it 4x (the concrete symptom of the old dead filter)."""
    fn, calls = _decorated(lambda n: TypeError("bug in our own code"))
    with pytest.raises(TypeError):
        await fn()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_5xx_is_retried_then_succeeds() -> None:
    """A 503 is transient — retried, and the eventual success is returned."""
    fn, calls = _decorated(lambda n: _http_error(503) if n == 1 else None)
    assert await fn() == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_429_is_retried() -> None:
    """429 rate-limit is transient and retried until it clears."""
    fn, calls = _decorated(lambda n: _http_error(429) if n < 3 else None)
    assert await fn() == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_network_error_is_retried_then_succeeds() -> None:
    """A network drop (httpx.RequestError subclass) is transient."""

    def raiser(n: int) -> BaseException | None:
        return httpx.ConnectError("connection refused") if n == 1 else None

    fn, calls = _decorated(raiser)
    assert await fn() == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_persistent_transient_exhausts_and_reraises() -> None:
    """A transient that never clears exhausts max_attempts, then reraises the
    underlying exception (reraise=True) rather than a tenacity RetryError."""
    fn, calls = _decorated(lambda n: _http_error(503))
    with pytest.raises(httpx.HTTPStatusError):
        await fn()
    assert calls["n"] == 4  # max_attempts, not 1 (still retried) and not wrapped
