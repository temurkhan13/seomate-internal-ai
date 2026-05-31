"""Anthropic Claude adapter for LLM-driven evaluation (H1c).

Used by the H1c evaluation layer to answer nuanced rules that
deterministic extractors can't reliably handle: schema-vs-visible
content match, hidden-info detection, content originality, headline
accuracy, etc.

Design constraints (per Humza's 2Connect experience):

- **Batching is mandatory.** A single Claude call evaluates N pages at
  once. Sending one call per page truncates / oversimplifies / costs
  more / runs slower. Every evaluator here ships with a batched prompt
  that takes a list of items and returns a parallel list of results.

- **Structured output only.** Every prompt requests JSON output with
  a fixed schema. We parse responses with strict JSON and reject
  malformed batches rather than coercing.

- **Graceful degradation.** If ``ANTHROPIC_API_KEY`` is unset, the
  adapter still opens but every call raises ``LlmNotConfigured``.
  Evaluators catch this and the dependent rules report ``deferred``
  rather than crashing the audit.

Model selection:
- ``claude-haiku-4-5`` is the default — fast, cheap, plenty smart for
  these per-page evaluation tasks (~£0.05–0.10 per audit at 58 pages).
- ``claude-sonnet-4-6`` is available for evals where Haiku produces
  inconsistent output (set ``ANTHROPIC_EVAL_MODEL`` env var).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from anthropic import AsyncAnthropic
from pydantic_settings import BaseSettings, SettingsConfigDict

from seomate.adapters._base import (
    AdapterContext,
    BaseAdapter,
    rate_limited,
    retry_transient,
    tracked,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_PATH = str(_REPO_ROOT / ".env")


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    ANTHROPIC_API_KEY: str = ""
    # Default to Haiku 4.5 — fast and inexpensive for batched per-page evals.
    ANTHROPIC_EVAL_MODEL: str = "claude-haiku-4-5"


class LlmNotConfigured(RuntimeError):
    """Raised when the LLM adapter is invoked without an API key."""


@dataclass(frozen=True)
class LlmBatchResult:
    """One Claude batch call's raw output.

    Evaluators parse ``raw_text`` into per-item results. We keep the
    raw text around for debugging when JSON parsing fails.
    """

    raw_text: str
    parsed: list[dict[str, Any]] | None
    input_tokens: int
    output_tokens: int
    model: str
    error: str | None = None


class LlmAdapter(BaseAdapter):
    name: ClassVar[str] = "anthropic_llm"
    # Free tier on Anthropic is 50 RPM for Haiku. Paid tier starts at
    # 4000 RPM. Cap to 4 RPS so we don't hit the free-tier ceiling
    # even on a very-large-site audit.
    default_rps: ClassVar[float] = 4.0

    # Approximate Haiku 4.5 pricing in USD per 1M tokens (May 2026).
    # Output is more expensive, but our prompts produce small JSON
    # responses so output cost is a fraction of input cost.
    PRICE_USD_PER_M_INPUT: ClassVar[float] = 0.80
    PRICE_USD_PER_M_OUTPUT: ClassVar[float] = 4.00

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        settings: LlmSettings | None = None,
        rps: float | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.settings = settings or LlmSettings()
        self._client: AsyncAnthropic | None = None
        # Sticky flag: when the account hits "credit balance too low"
        # (or any other auth/billing 400), every subsequent call would
        # also 400. Set the flag on first occurrence and short-circuit
        # the rest of the audit's LLM batches with LlmNotConfigured so
        # they don't grind through ~130 wasted API calls.
        self._billing_blocked: bool = False
        self._billing_block_reason: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.ANTHROPIC_API_KEY) and not self._billing_blocked

    async def __aenter__(self) -> "LlmAdapter":
        if self.is_configured:
            self._client = AsyncAnthropic(
                api_key=self.settings.ANTHROPIC_API_KEY,
                timeout=self.timeout_seconds,
            )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            # AsyncAnthropic uses an httpx client under the hood; close it.
            await self._client.close()
            self._client = None

    @rate_limited
    @retry_transient()
    @tracked("anthropic.messages.create")
    async def batch_evaluate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> LlmBatchResult:
        """Run one Claude evaluation call and parse the JSON response.

        Returns ``LlmBatchResult`` with the parsed list and token
        accounting for cost tracking. Errors (network / parse / JSON)
        are recorded in ``error`` and ``parsed`` stays None.
        """
        if self._billing_blocked:
            raise LlmNotConfigured(
                f"LLM disabled for this audit (billing block): "
                f"{self._billing_block_reason}"
            )
        if not self.is_configured or self._client is None:
            raise LlmNotConfigured(
                "ANTHROPIC_API_KEY not set; LLM evaluation is unavailable."
            )

        try:
            response = await self._client.messages.create(
                model=self.settings.ANTHROPIC_EVAL_MODEL,
                max_tokens=max_tokens,
                # temperature=0 makes the output deterministic for evaluations.
                # Per-page verdicts must be reproducible across audit runs;
                # default temperature 1.0 would let identical inputs produce
                # different pass/fail labels run-to-run, which silently
                # invalidates the audit's reliability story.
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:  # noqa: BLE001
            # Sticky-flag any 400-class error that means every call in
            # this audit will fail the same way: credit-balance-too-low,
            # auth, model-not-found, permission. Without this short-
            # circuit, a single audit burns ~130 wasted calls.
            msg = str(exc).lower()
            if any(
                signal in msg
                for signal in (
                    "credit balance is too low",
                    "credit_balance_too_low",
                    "authentication",
                    "invalid x-api-key",
                    "permission",
                    "model_not_found",
                )
            ):
                self._billing_blocked = True
                self._billing_block_reason = str(exc)[:200]
            raise

        # Concatenate any text blocks in the response.
        raw_chunks: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw_chunks.append(block.text)
        raw_text = "".join(raw_chunks).strip()

        parsed: list[dict[str, Any]] | None = None
        error: str | None = None
        try:
            parsed_any = _extract_json_array(raw_text)
            if isinstance(parsed_any, list):
                parsed = [item for item in parsed_any if isinstance(item, dict)]
            else:
                error = f"expected JSON array, got {type(parsed_any).__name__}"
        except json.JSONDecodeError as exc:
            error = f"JSON parse failed: {exc}"

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0

        return LlmBatchResult(
            raw_text=raw_text,
            parsed=parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.settings.ANTHROPIC_EVAL_MODEL,
            error=error,
        )


def _extract_json_array(text: str) -> Any:
    """Pull a JSON array out of Claude's response text.

    Claude sometimes wraps the array in prose ("Here is the result:
    [...]") or in markdown code fences. We strip both shapes before
    parsing. Raises ``json.JSONDecodeError`` when no parseable
    array is found.
    """
    s = text.strip()

    # Strip ```json ... ``` fences if present.
    if s.startswith("```"):
        # Drop the opening fence + optional language tag.
        first_newline = s.find("\n")
        if first_newline != -1:
            s = s[first_newline + 1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

    # Try a clean parse first.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Locate the outermost [...] and parse just that.
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("no JSON array found", s, 0)
    return json.loads(s[start : end + 1])
