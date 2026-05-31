"""Wikidata API adapter.

Free public API. Used by P6-11 entity coverage. We use the
``wbsearchentities`` action for entity search and ``wbgetentities``
for fetching property details.

API reference: https://www.wikidata.org/w/api.php
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from seomate.adapters._base import (
    AdapterContext,
    BaseAdapter,
    rate_limited,
    retry_transient,
    tracked,
)


@dataclass(frozen=True)
class WikidataEntity:
    """Trimmed view of a Wikidata entity."""

    qid: str
    label: str | None
    description: str | None
    aliases: tuple[str, ...]
    instance_of: tuple[str, ...]         # Q-ids the entity is an instance of (P31)
    sitelinks_count: int                 # number of language Wikipedia versions
    has_official_website: bool           # True iff P856 set
    has_image: bool                      # True iff P18 set
    sample_sitelinks: tuple[str, ...]    # e.g. enwiki, dewiki, ... (capped)


class WikidataAdapter(BaseAdapter):
    name: ClassVar[str] = "wikidata"
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        rps: float | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self._search_cache: dict[str, list[str]] = {}
        self._entity_cache: dict[str, WikidataEntity | None] = {}

    async def __aenter__(self) -> "WikidataAdapter":
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            base_url="https://www.wikidata.org",
            headers={
                "Accept": "application/json",
                "User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)",
            },
        )
        return self

    @rate_limited
    @retry_transient()
    @tracked("wikidata.search_entities")
    async def search(
        self,
        query: str,
        *,
        language: str = "en",
        limit: int = 5,
    ) -> list[str]:
        """Search Wikidata for Q-ids matching ``query``.

        Returns Q-ids only; the caller may then ``get_entity`` for any
        candidate it wants to inspect in detail. Cached per query.
        """
        cache_key = f"{language}|{query}|{limit}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        params = {
            "action": "wbsearchentities",
            "format": "json",
            "search": query,
            "language": language,
            "limit": limit,
            "type": "item",
        }
        response = await self.client.get("/w/api.php", params=params)
        response.raise_for_status()
        data = response.json()
        qids = [
            r.get("id", "")
            for r in (data.get("search") or [])
            if r.get("id")
        ]
        self._search_cache[cache_key] = qids
        return qids

    @rate_limited
    @retry_transient()
    @tracked("wikidata.get_entities")
    async def get_entity(
        self,
        qid: str,
        *,
        language: str = "en",
    ) -> WikidataEntity | None:
        """Fetch entity properties + sitelinks summary for one Q-id."""
        if qid in self._entity_cache:
            return self._entity_cache[qid]

        params = {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "labels|descriptions|aliases|claims|sitelinks",
            "languages": language,
            "sitefilter": "enwiki|dewiki|frwiki|eswiki|jawiki|zhwiki",
        }
        response = await self.client.get("/w/api.php", params=params)
        response.raise_for_status()
        data = response.json()
        ent = (data.get("entities") or {}).get(qid)
        if not ent or ent.get("missing") is not None:
            self._entity_cache[qid] = None
            return None

        labels = ent.get("labels") or {}
        descriptions = ent.get("descriptions") or {}
        aliases_lang = (ent.get("aliases") or {}).get(language) or []
        claims = ent.get("claims") or {}
        sitelinks = ent.get("sitelinks") or {}

        instance_of_qids: list[str] = []
        for c in claims.get("P31") or []:
            mainsnak = c.get("mainsnak") or {}
            datavalue = mainsnak.get("datavalue") or {}
            value = datavalue.get("value") or {}
            if isinstance(value, dict) and value.get("id"):
                instance_of_qids.append(value["id"])

        entity = WikidataEntity(
            qid=qid,
            label=(labels.get(language) or {}).get("value"),
            description=(descriptions.get(language) or {}).get("value"),
            aliases=tuple(a.get("value", "") for a in aliases_lang),
            instance_of=tuple(instance_of_qids),
            sitelinks_count=len(sitelinks),
            has_official_website=bool(claims.get("P856")),
            has_image=bool(claims.get("P18")),
            sample_sitelinks=tuple(sorted(sitelinks)[:6]),
        )
        self._entity_cache[qid] = entity
        return entity
