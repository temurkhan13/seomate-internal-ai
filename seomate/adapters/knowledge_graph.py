"""Google Knowledge Graph Search API adapter.

Free Google API (100k requests/day default quota). Used by entity
recognition variables (P0-16 brand entity, P6-11 entity coverage,
P6-29 KG entity completeness).

Requires ``GOOGLE_KG_API_KEY`` in env. If the key is missing the
adapter still opens but every call raises ``KGNotConfigured``;
extractors are expected to catch that and report ``unmeasurable``
with a clear note rather than crashing the audit.

API reference: https://developers.google.com/knowledge-graph
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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


class KGSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    GOOGLE_KG_API_KEY: str = ""


class KGNotConfigured(RuntimeError):
    """Raised when the KG adapter is invoked without an API key."""


@dataclass(frozen=True)
class KGSearchHit:
    """One entity returned by the KG Search API."""

    name: str | None
    description: str | None
    detailed_description: str | None
    types: tuple[str, ...]
    image_url: str | None
    url: str | None
    kg_id: str | None
    same_as: tuple[str, ...]   # mid:/m/... and other identifiers
    result_score: float


class KnowledgeGraphAdapter(BaseAdapter):
    name: ClassVar[str] = "google_kg"
    default_rps: ClassVar[float] = 10.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        settings: KGSettings | None = None,
        rps: float | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.settings = settings or KGSettings()
        self._lookup_cache: dict[str, list[KGSearchHit]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.GOOGLE_KG_API_KEY)

    async def __aenter__(self) -> "KnowledgeGraphAdapter":
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            base_url="https://kgsearch.googleapis.com",
            headers={"Accept": "application/json"},
        )
        return self

    @rate_limited
    @retry_transient()
    @tracked("kgsearch.entities_search")
    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[KGSearchHit]:
        """Search Knowledge Graph for entities matching ``query``.

        Returns a list of hits sorted by ``result_score`` descending.
        Empty list when there's no match. Cached per (query, limit) so
        multiple extractors that ask for the same brand don't burn
        quota.
        """
        if not self.is_configured:
            raise KGNotConfigured(
                "GOOGLE_KG_API_KEY not set; entity recognition is unavailable."
            )
        cache_key = f"{query}|{limit}|{','.join(sorted(types or []))}"
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "key": self.settings.GOOGLE_KG_API_KEY,
            "indent": "false",
        }
        if types:
            for t in types:
                params.setdefault("types", []).append(t)
        if languages:
            params["languages"] = ",".join(languages)

        response = await self.client.get("/v1/entities:search", params=params)
        response.raise_for_status()
        data = response.json()

        hits: list[KGSearchHit] = []
        for el in data.get("itemListElement", []) or []:
            result = el.get("result") or {}
            score = float(el.get("resultScore") or 0)
            hits.append(_hit_from_result(result, score))
        self._lookup_cache[cache_key] = hits
        return hits


def _hit_from_result(result: dict, score: float) -> KGSearchHit:
    desc = result.get("description")
    detailed = result.get("detailedDescription") or {}
    detailed_text = detailed.get("articleBody") if isinstance(detailed, dict) else None
    image = result.get("image") or {}
    image_url = image.get("contentUrl") if isinstance(image, dict) else None
    types = tuple(result.get("@type") or ())
    same_as = tuple(result.get("sameAs") or ())
    return KGSearchHit(
        name=result.get("name"),
        description=desc,
        detailed_description=detailed_text,
        types=types,
        image_url=image_url,
        url=result.get("url"),
        kg_id=result.get("@id"),
        same_as=same_as,
        result_score=score,
    )
