"""Gemini Embeddings adapter.

Wraps Google's Gemini embeddings API (``text-embedding-004`` by
default; configurable via env). Used by H1b composition layer for
topic clustering, anchor-text relevance, content uniqueness, and
similarity-driven content gap detection.

Graceful degradation: when ``GEMINI_API_KEY`` is unset the adapter
still opens but every embed call raises ``EmbeddingsNotConfigured``;
extractors catch that and report ``unmeasurable`` rather than
crashing the audit. Same pattern as the Knowledge Graph adapter.

API reference:
- https://ai.google.dev/api/embeddings
- Endpoint: POST {base}/models/{model}:embedContent

Pricing notes (May 2026):
- text-embedding-004: free tier up to 1500 RPM; paid £0.000005 / 1k chars
- gemini-embedding-001: paid £0.000010 / 1k input chars
For SEOMATE-scale audits (~50–500 pages × ~2k chars main text), one
audit pass embedding every page costs well under £0.01.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import httpx
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


class EmbeddingsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    GEMINI_API_KEY: str = ""
    # gemini-embedding-001 has the highest free-tier quota (100 RPM, 1500 RPD)
    # of the available embedding families. gemini-embedding-2 has much
    # tighter free-tier limits (~5–10 RPM) and is best on a paid plan.
    # Both return 3072-dim natively; we Matryoshka-truncate to 768 to fit
    # the pgvector schema and stay consistent with prior 768-dim work.
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_DIMENSIONS: int = 768


class EmbeddingsNotConfigured(RuntimeError):
    """Raised when the embeddings adapter is invoked without an API key."""


@dataclass(frozen=True)
class Embedding:
    """One vector + the input text snapshot used to produce it."""

    text: str
    vector: tuple[float, ...]
    model: str
    char_count: int


class EmbeddingsAdapter(BaseAdapter):
    name: ClassVar[str] = "gemini_embeddings"
    # gemini-embedding-001 paid tier supports >= 1000 RPM (16 RPS) per
    # the published Google Cloud quotas. The old 1 RPS cap was a
    # free-tier carry-over and caused a 58-page audit to take ~60s
    # of throttle-wait minimum, leaving no slack for retries when
    # transient 429s land. Default 8 RPS keeps comfortable headroom
    # under the paid quota while letting an audit's embedding pass
    # finish in ~7-10s. Override per-environment via the ``rps``
    # constructor arg.
    default_rps: ClassVar[float] = 8.0

    # Per-1000-character input cost; converted to the audit's £ via the
    # tracked decorator. Values reflect Gemini's published pricing for
    # text-embedding-004 paid tier as of May 2026.
    USD_PER_1K_CHARS: ClassVar[float] = 0.000005

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        settings: EmbeddingsSettings | None = None,
        rps: float | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.settings = settings or EmbeddingsSettings()
        self._cache: dict[str, Embedding] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.GEMINI_API_KEY)

    async def __aenter__(self) -> "EmbeddingsAdapter":
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            base_url="https://generativelanguage.googleapis.com",
            headers={"Content-Type": "application/json"},
        )
        return self

    @rate_limited
    # Embeddings retries are intentionally short — the orchestrator runs
    # multi-pass retry across the whole batch, with a long pause between
    # passes (60s) that comfortably covers any per-minute quota reset.
    # Stacking 5 in-adapter retries × 120s would multiply per-page
    # latency by 10×; we'd rather fail fast and let the outer pass handle
    # recovery.
    @retry_transient(max_attempts=2, max_wait=10.0)
    @tracked("gemini.embed_content")
    async def embed(
        self,
        text: str,
        *,
        task_type: str = "SEMANTIC_SIMILARITY",
    ) -> Embedding:
        """Embed one piece of text. Cached per (model, text) pair.

        ``task_type`` is one of Google's documented embedding task
        labels; SEMANTIC_SIMILARITY is the right default for
        page-to-page similarity work. Long inputs are truncated at
        ~8000 characters; that's well below the model's 2048-token
        context but keeps the cost bounded.
        """
        if not self.is_configured:
            raise EmbeddingsNotConfigured(
                "GEMINI_API_KEY not set; embeddings are unavailable."
            )

        # Bound the input to keep cost predictable. text-embedding-004
        # accepts up to 2048 tokens — ~8k chars is conservatively safe.
        normalised = text.strip()[:8000]
        if not normalised:
            return Embedding(
                text="",
                vector=tuple([0.0] * self.settings.GEMINI_EMBEDDING_DIMENSIONS),
                model=self.settings.GEMINI_EMBEDDING_MODEL,
                char_count=0,
            )

        cache_key = f"{self.settings.GEMINI_EMBEDDING_MODEL}|{normalised}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = f"/v1beta/models/{self.settings.GEMINI_EMBEDDING_MODEL}:embedContent"
        payload: dict[str, Any] = {
            "model": f"models/{self.settings.GEMINI_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": normalised}]},
            "taskType": task_type,
            "outputDimensionality": self.settings.GEMINI_EMBEDDING_DIMENSIONS,
        }
        response = await self.client.post(
            path,
            params={"key": self.settings.GEMINI_API_KEY},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        values = (data.get("embedding") or {}).get("values") or []
        embedding = Embedding(
            text=normalised,
            vector=tuple(float(v) for v in values),
            model=self.settings.GEMINI_EMBEDDING_MODEL,
            char_count=len(normalised),
        )
        self._cache[cache_key] = embedding
        return embedding


# ─── Pure-Python similarity helpers (no NumPy dep needed for 768-dim) ───────


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Cosine similarity of two vectors. Returns 0.0 if either is zero-length."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
