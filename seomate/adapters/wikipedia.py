"""Wikipedia (MediaWiki API) adapter.

Free public API, no auth required. Used by P6-11 entity coverage
and P6-30 Wikipedia article quality.

The MediaWiki action API is used for article metadata:
``https://{lang}.wikipedia.org/w/api.php``. Default language is
English; multilingual lookups are supported when needed.

API reference: https://www.mediawiki.org/wiki/API:Main_page
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
class WikipediaArticle:
    """Trimmed view of a Wikipedia article's metadata."""

    title: str
    page_id: int
    url: str
    language: str
    is_redirect: bool
    is_disambiguation: bool
    length_bytes: int                    # bytes of wikitext
    last_edited: str | None              # ISO 8601
    pageprops: dict[str, str]            # raw pageprops (e.g. wikibase_item, defaultsort)
    templates: tuple[str, ...]           # template names invoked (subset; see fetch limit)
    categories: tuple[str, ...]          # category names (subset)


@dataclass(frozen=True)
class WikipediaSearchHit:
    title: str
    snippet: str
    page_id: int


class WikipediaAdapter(BaseAdapter):
    name: ClassVar[str] = "wikipedia"
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        rps: float | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self._lookup_cache: dict[str, WikipediaArticle | None] = {}
        self._search_cache: dict[str, list[WikipediaSearchHit]] = {}

    async def __aenter__(self) -> "WikipediaAdapter":
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)",
            },
        )
        return self

    @rate_limited
    @retry_transient()
    @tracked("mediawiki.search")
    async def search(
        self,
        query: str,
        *,
        language: str = "en",
        limit: int = 5,
    ) -> list[WikipediaSearchHit]:
        """Full-text search Wikipedia for the given query."""
        cache_key = f"{language}|{query}|{limit}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
        }
        response = await self.client.get(
            f"https://{language}.wikipedia.org/w/api.php",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        hits: list[WikipediaSearchHit] = []
        for h in (data.get("query") or {}).get("search") or []:
            hits.append(
                WikipediaSearchHit(
                    title=h.get("title", ""),
                    snippet=h.get("snippet", ""),
                    page_id=int(h.get("pageid") or 0),
                )
            )
        self._search_cache[cache_key] = hits
        return hits

    @rate_limited
    @retry_transient()
    @tracked("mediawiki.exturlusage")
    async def external_url_usage(
        self,
        domain: str,
        *,
        language: str = "en",
        limit: int = 50,
        protocol: str = "https",
    ) -> list[dict[str, Any]]:
        """Find Wikipedia articles that externally link to a given domain.

        Uses the MediaWiki ``list=exturlusage`` query. Returns a list of
        article records — each with ``title``, ``pageid``, and the
        actual external ``url`` referenced. An empty list means no
        Wikipedia article on this language edition cites the domain.

        Tries both http and https variants implicitly (MediaWiki's
        ``euprotocol`` constrains the match, and many citations use
        https now).
        """
        params = {
            "action": "query",
            "format": "json",
            "list": "exturlusage",
            "euquery": domain,
            "eulimit": limit,
            "euprotocol": protocol,
            "euprop": "title|url|ids",
        }
        response = await self.client.get(
            f"https://{language}.wikipedia.org/w/api.php",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        items = (data.get("query") or {}).get("exturlusage") or []
        return list(items)

    @rate_limited
    @retry_transient()
    @tracked("mediawiki.get_article")
    async def get_article(
        self,
        title: str,
        *,
        language: str = "en",
    ) -> WikipediaArticle | None:
        """Fetch metadata for an article by title.

        Resolves redirects automatically. Returns ``None`` when the
        title doesn't exist or is a missing page. Cached per
        (title, language) to keep quota usage bounded.
        """
        cache_key = f"{language}|{title}"
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "redirects": 1,
            "prop": "info|pageprops|templates|categories",
            "inprop": "url",
            "tllimit": 100,
            "cllimit": 100,
        }
        response = await self.client.get(
            f"https://{language}.wikipedia.org/w/api.php",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        pages = ((data.get("query") or {}).get("pages") or {})
        if not pages:
            self._lookup_cache[cache_key] = None
            return None

        # The API returns a dict keyed by page_id; we just want the first entry.
        _, page = next(iter(pages.items()))
        if page.get("missing") is not None:
            self._lookup_cache[cache_key] = None
            return None

        templates = tuple(t.get("title", "") for t in page.get("templates") or [])
        categories = tuple(c.get("title", "") for c in page.get("categories") or [])
        pageprops = page.get("pageprops") or {}
        article = WikipediaArticle(
            title=page.get("title", title),
            page_id=int(page.get("pageid") or 0),
            url=page.get("fullurl", ""),
            language=language,
            is_redirect=bool(
                (data.get("query") or {}).get("redirects")
            ),
            is_disambiguation="disambiguation" in pageprops,
            length_bytes=int(page.get("length") or 0),
            last_edited=page.get("touched"),
            pageprops={k: str(v) for k, v in pageprops.items()},
            templates=templates,
            categories=categories,
        )
        self._lookup_cache[cache_key] = article
        return article
