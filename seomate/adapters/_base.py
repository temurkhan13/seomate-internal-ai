"""Adapter base class and method decorators.

Every external service adapter inherits from :class:`BaseAdapter` and
decorates its public methods with the building blocks here:

- ``@rate_limited`` — acquire a token from the adapter's per-instance
  ``aiolimiter.AsyncLimiter`` before executing.
- ``@retry_transient`` — retry on transient HTTP errors (timeout,
  network, 429, 5xx). Authn / 4xx fail fast.
- ``@tracked(endpoint, cost_calculator=...)`` — time the call, compute
  £ cost via the supplied calculator (or default to 0), record an
  :class:`AdapterCallRecord` into the adapter context.

Persistence of recorded calls into the ``adapter_calls`` table happens
in the orchestrator at the end of each capture so that adapter-call
rows can be linked to the resulting capture_id.
"""
from __future__ import annotations

import time
from abc import ABC
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Any, ClassVar, ParamSpec, TypeVar
from uuid import UUID

import httpx
import structlog
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from tenacity import RetryCallState  # noqa: F401 - re-export for type hint clarity

from seomate.utils.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class AdapterCallRecord:
    """One adapter call's telemetry. Persisted to ``adapter_calls`` table."""

    adapter: str
    endpoint: str
    started_at: datetime
    duration_ms: int
    cost_gbp: Decimal
    status_code: int | None = None
    error: str | None = None


@dataclass
class AdapterContext:
    """Per-audit shared state injected into adapters and extractors.

    The orchestrator owns one AdapterContext per audit and passes it
    into each adapter constructor and each extractor invocation.
    Adapters write call records here; the orchestrator drains them
    after each capture and persists.
    """

    audit_id: UUID
    cost_tracker: CostTracker
    taxonomy_version: str = "unknown"
    _calls: list[AdapterCallRecord] = field(default_factory=list)

    def record_call(self, record: AdapterCallRecord) -> None:
        self._calls.append(record)
        self.cost_tracker.record(record.adapter, record.cost_gbp)

    def drain_calls(self) -> list[AdapterCallRecord]:
        out = self._calls[:]
        self._calls.clear()
        return out


class BaseAdapter(ABC):
    """Base class for every external service adapter.

    Subclasses set:

    - ``name``: ClassVar[str]   — adapter identifier (e.g. ``"dataforseo"``)
    - ``default_rps``: ClassVar[float] — default rate limit if not overridden

    Use as an async context manager so the underlying ``httpx.AsyncClient``
    is opened and closed cleanly:

        async with DataForSEOAdapter(ctx) as dfs:
            result = await dfs.on_page_titles(urls)
    """

    name: ClassVar[str] = ""
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        rps: float | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not self.name:
            raise TypeError(f"{type(self).__name__} must set class attribute `name`")
        self.ctx = ctx
        self.timeout_seconds = timeout_seconds
        self._limiter = AsyncLimiter(rps or self.default_rps, time_period=1.0)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> BaseAdapter:
        self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as an async context manager"
            )
        return self._client


# ─── Decorators ──────────────────────────────────────────────────────────────


def rate_limited(method: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Acquire one token from the adapter's rate limiter before executing."""

    @wraps(method)
    async def wrapper(self: BaseAdapter, *args: P.args, **kwargs: P.kwargs) -> R:
        async with self._limiter:
            return await method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def retry_transient(
    *,
    max_attempts: int = 5,
    multiplier: float = 1.0,
    min_wait: float = 1.0,
    max_wait: float = 120.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Retry the method on transient errors with exponential backoff.

    Retries on:
    - ``httpx.RequestError`` (network errors, timeouts, DNS, getaddrinfo)
    - ``httpx.HTTPStatusError`` for 429, 500, 502, 503, 504
    - ``anthropic`` and ``google`` API SDK 429 errors when re-raised
      through their own exception types

    Does NOT retry 4xx other than 429 — those are caller errors that
    won't fix themselves.

    Special handling: when a 429 response carries a ``Retry-After``
    header (seconds or HTTP-date), waits at least that long before the
    next attempt instead of using the exponential schedule. Honouring
    Retry-After is the difference between recovering from a 60-second
    quota reset and giving up after 4s of polite backoff.
    """

    def is_transient(exc: BaseException) -> bool:
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {429, 500, 502, 503, 504}
        # Catch anthropic / SDK rate-limit exceptions by class name
        # to avoid hard-importing every SDK that might raise here.
        cls_name = type(exc).__name__
        if cls_name in {"RateLimitError", "APIStatusError", "ResourceExhausted"}:
            return True
        return False

    def _retry_after_seconds(exc: BaseException) -> float | None:
        """Extract Retry-After seconds from a 429 if present, else None."""
        if not isinstance(exc, httpx.HTTPStatusError):
            return None
        if exc.response.status_code != 429:
            return None
        header = exc.response.headers.get("retry-after")
        if not header:
            return None
        # Retry-After is either an integer count of seconds or an HTTP-date.
        try:
            return float(header)
        except ValueError:
            return None  # HTTP-date form ignored for simplicity

    def _wait_strategy(retry_state: Any) -> float:
        """Wait the larger of (server's Retry-After) and (exp backoff)."""
        exp = wait_exponential(
            multiplier=multiplier, min=min_wait, max=max_wait
        )(retry_state)
        last_exc = (
            retry_state.outcome.exception()
            if retry_state.outcome and retry_state.outcome.failed
            else None
        )
        retry_after = _retry_after_seconds(last_exc) if last_exc else None
        if retry_after is not None:
            # Clamp to max_wait so a malicious server can't pin us forever,
            # but otherwise honour the server's request.
            return min(retry_after, max_wait)
        return exp

    def decorator(method: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(method)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=_wait_strategy,
                # The predicate does the filtering: transient errors retry,
                # everything else (4xx caller errors, our own TypeErrors)
                # fails fast on the first attempt.
                retry=retry_if_exception(is_transient),
                reraise=True,
            ):
                with attempt:
                    return await method(*args, **kwargs)
            # Unreachable — AsyncRetrying always returns or raises
            raise RuntimeError("retry loop exited without result")

        return wrapper

    return decorator


def tracked(
    endpoint: str,
    *,
    cost_calculator: Callable[..., Decimal] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Time the method, compute £ cost, append an AdapterCallRecord.

    ``cost_calculator`` receives ``(result, *args, **kwargs)`` and returns
    a Decimal in £. If omitted, the call is recorded with cost £0 (good
    default for free APIs).
    """

    def decorator(method: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(method)
        async def wrapper(self: BaseAdapter, *args: P.args, **kwargs: P.kwargs) -> R:
            started_dt = datetime.now(timezone.utc)
            started_mono = time.monotonic()
            cost = Decimal("0")
            status_code: int | None = None
            error: str | None = None
            result: R | None = None
            try:
                result = await method(self, *args, **kwargs)
                if cost_calculator is not None:
                    cost = cost_calculator(result, *args, **kwargs)
                # Success path: default to 200 since the method returned
                # cleanly without raising. Without this, the completeness
                # gate has no way to count successful calls. SDK calls
                # (anthropic, mediawiki) that surface non-200s via
                # exceptions are already covered by the except branches.
                status_code = 200
                return result
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error = f"{type(exc).__name__}: HTTP {status_code}"
                raise
            except Exception as exc:
                # Anthropic / google SDK errors expose status_code as an
                # attribute. Inspect lightly so we can distinguish a 400
                # billing-fail from a transport error.
                sdk_status = getattr(exc, "status_code", None)
                if isinstance(sdk_status, int):
                    status_code = sdk_status
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                duration_ms = int((time.monotonic() - started_mono) * 1000)
                self.ctx.record_call(
                    AdapterCallRecord(
                        adapter=self.name,
                        endpoint=endpoint,
                        started_at=started_dt,
                        duration_ms=duration_ms,
                        cost_gbp=cost,
                        status_code=status_code,
                        error=error,
                    )
                )

        return wrapper  # type: ignore[return-value]

    return decorator


# ─── Context manager helpers ─────────────────────────────────────────────────


@asynccontextmanager
async def open_adapter(adapter: BaseAdapter):
    """Convenience: ``async with open_adapter(adapter) as a: ...``."""
    async with adapter as a:
        yield a
