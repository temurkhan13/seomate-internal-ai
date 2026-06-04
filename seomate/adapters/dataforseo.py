"""DataForSEO adapter.

Handles authentication, rate limiting, retry, and cost tracking for
DataForSEO's REST API. The same credentials work against both the
sandbox (free, mock data) and the live API; the base URL switches via
``DATAFORSEO_USE_SANDBOX``.

Endpoints implemented (so far):

- ``user_data`` — confirms auth works and returns account balance.
- ``on_page_instant_pages`` — per-URL audit for up to 100 URLs in one
  call. The workhorse of Pillar 1 / Pillar 2 (~30 variables share its
  output).
- ``backlinks_summary`` — domain-level backlink counts and ratios.
- ``backlinks_anchors`` — anchor text distribution.
- ``backlinks_referring_domains`` — referring domain list with metrics.
- ``backlinks_history`` — 12-month backlink count history.
- ``domain_rank_overview`` — DataForSEO Labs domain rank + traffic estimate.

Cost handling: DataForSEO reports cost in USD on every task. The
adapter converts to GBP using a fixed rate constant (refresh manually
when the rate moves materially). The conversion is a TODO for live FX.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env path resolved from this file's location so env loading
# works regardless of the CWD the CLI is invoked from.
# adapters/dataforseo.py -> adapters -> seomate -> auditor -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_PATH = str(_REPO_ROOT / ".env")

from seomate.adapters._base import (
    AdapterContext,
    BaseAdapter,
    rate_limited,
    retry_transient,
    tracked,
)


# ─── Settings ───────────────────────────────────────────────────────────────


class DataForSEOSettings(BaseSettings):
    """Env-driven config for the DataForSEO adapter."""

    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATAFORSEO_LOGIN: str
    DATAFORSEO_PASSWORD: str
    DATAFORSEO_USE_SANDBOX: bool = True

    @property
    def base_url(self) -> str:
        return (
            "https://sandbox.dataforseo.com"
            if self.DATAFORSEO_USE_SANDBOX
            else "https://api.dataforseo.com"
        )


# Approximate GBP per USD. Refresh manually; FX precision doesn't matter at
# pence-per-call scale, but the cost_incurred_gbp field on captures should
# stay broadly accurate.
USD_TO_GBP = Decimal("0.79")


# ─── Cost calculators ───────────────────────────────────────────────────────


def _cost_from_dfs_response(result: dict, *_args: Any, **_kwargs: Any) -> Decimal:
    """Read DataForSEO's reported per-task cost (USD) and convert to GBP.

    DataForSEO's response shape: ``{ "cost": <total>, "tasks": [{"cost": ...}, ...] }``
    Tasks may also have null or zero cost on sandbox calls.
    """
    if not isinstance(result, dict):
        return Decimal("0")
    raw = result.get("cost", 0)
    try:
        usd = Decimal(str(raw or 0))
    except (TypeError, ArithmeticError):
        return Decimal("0")
    return usd * USD_TO_GBP


# ─── Adapter ────────────────────────────────────────────────────────────────


class DataForSEOAdapter(BaseAdapter):
    """DataForSEO REST API client.

    Use as an async context manager so the underlying ``httpx.AsyncClient``
    closes cleanly after each audit:

        async with DataForSEOAdapter(ctx) as dfs:
            user = await dfs.get_user_data()
            results = await dfs.on_page_instant_pages(["https://www.pixelettetech.com/"])
    """

    name: ClassVar[str] = "dataforseo"
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        settings: DataForSEOSettings | None = None,
        rps: float | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.settings = settings or DataForSEOSettings()
        self._auth = httpx.BasicAuth(
            self.settings.DATAFORSEO_LOGIN,
            self.settings.DATAFORSEO_PASSWORD,
        )

    async def __aenter__(self) -> DataForSEOAdapter:
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            base_url=self.settings.base_url,
            auth=self._auth,
            headers={"Content-Type": "application/json"},
        )
        return self

    # ─── Endpoints ──────────────────────────────────────────────────────────

    @rate_limited
    @retry_transient()
    @tracked("appendix.user_data")
    async def get_user_data(self) -> dict:
        """Return account info including balance, rate limits, and config.

        Useful as a low-cost auth/connectivity probe. Sandbox returns the
        same shape as live with mocked balance values.
        """
        response = await self.client.get("/v3/appendix/user_data")
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("on_page.instant_pages", cost_calculator=_cost_from_dfs_response)
    async def on_page_instant_pages(
        self,
        url: str,
        *,
        load_resources: bool = False,
        enable_javascript: bool = False,
    ) -> dict:
        """Audit a single URL and return per-URL audit data.

        DataForSEO's Instant Pages accepts a list of task configs in the
        body, but in practice it only returns full ``items`` data for
        roughly the first ~5 URLs per call (the rest come back with
        empty items, presumably hitting a per-call timeout). The
        reliable pattern is one URL per call, parallelised at the
        extractor layer with a semaphore.

        ``load_resources=True`` and ``enable_javascript=True`` give a
        more accurate render but add latency and cost. Default off so
        we get the raw HTML view first; specific Pillar 2 extractors
        can do a second pass with JS enabled when needed.

        Returns the raw DataForSEO response. Higher-level extractors
        consume the ``tasks[].result[].items[]`` path.
        """
        if not url:
            raise ValueError("on_page_instant_pages requires a URL")
        body = [
            {
                "url": url,
                "load_resources": load_resources,
                "enable_javascript": enable_javascript,
            }
        ]
        response = await self.client.post("/v3/on_page/instant_pages", json=body)
        response.raise_for_status()
        return response.json()

    # ─── Backlinks endpoints (P3 Off-Page) ──────────────────────────────────

    @rate_limited
    @retry_transient()
    @tracked("backlinks.summary", cost_calculator=_cost_from_dfs_response)
    async def backlinks_summary(self, target: str) -> dict:
        """Domain-level backlink summary: counts, ratios, distributions.

        Returns: total backlinks, referring domains, referring main_domains,
        referring IPs, dofollow/nofollow ratio, anchor distribution preview,
        gov/edu link counts, broken backlinks count, sitewide vs single-page
        link counts. ~$0.02/call on live tier.
        """
        body = [{"target": target, "internal_list_limit": 10, "backlinks_status_type": "live"}]
        response = await self.client.post("/v3/backlinks/summary/live", json=body)
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.anchors", cost_calculator=_cost_from_dfs_response)
    async def backlinks_anchors(self, target: str, *, limit: int = 100) -> dict:
        """Anchor text distribution for a domain. ~$0.02/call."""
        body = [
            {
                "target": target,
                "limit": limit,
                "order_by": ["backlinks,desc"],
                "backlinks_status_type": "live",
            }
        ]
        response = await self.client.post("/v3/backlinks/anchors/live", json=body)
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.referring_domains", cost_calculator=_cost_from_dfs_response)
    async def backlinks_referring_domains(self, target: str, *, limit: int = 100) -> dict:
        """List of referring domains with per-domain metrics. ~$0.02/call.

        Each domain row carries domain rank, total backlinks from that
        domain, dofollow/nofollow split, country/TLD, and first-seen date.
        """
        body = [
            {
                "target": target,
                "limit": limit,
                "order_by": ["rank,desc"],
                "backlinks_status_type": "live",
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/referring_domains/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.history", cost_calculator=_cost_from_dfs_response)
    async def backlinks_history(self, target: str) -> dict:
        """12-month monthly history of backlinks + referring domains. ~$0.02/call."""
        body = [{"target": target, "date_from": None}]
        response = await self.client.post("/v3/backlinks/history/live", json=body)
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("keywords_data.google_ads.search_volume", cost_calculator=_cost_from_dfs_response)
    async def keywords_search_volume(
        self,
        keywords: list[str],
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
    ) -> dict:
        """Search volume for an explicit list of keywords. ~$0.05/100 kw.

        Returns the 12-month-average search volume per keyword plus
        CPC and competition. Used by P0-15 (brand search volume) and
        any other variable that needs volume on a curated keyword set
        rather than the auto-discovered ranked_keywords list.
        """
        body = [
            {
                "keywords": keywords,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        response = await self.client.post(
            "/v3/keywords_data/google_ads/search_volume/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.summary", cost_calculator=_cost_from_dfs_response)
    async def backlinks_summary(
        self,
        target: str,
        *,
        include_subdomains: bool = True,
        backlinks_status_type: str = "live",
    ) -> dict:
        """Aggregate backlinks metrics for a target domain.

        Returns one row per target with: rank, main_domain_rank,
        backlinks total, referring_domains, referring_main_domains,
        referring_ips, referring_subnets, referring_pages, anchors,
        dofollow, nofollow, ugc, sponsored, image, redirect, canonical,
        and lots more. The primary entry point for the P3 pillar —
        most variables read directly from this single call.

        Cost: ~$0.005 per call. ``backlinks_status_type=live`` means
        only currently-live backlinks; ``all`` includes historical.
        """
        body = [
            {
                "target": target,
                "include_subdomains": include_subdomains,
                "backlinks_status_type": backlinks_status_type,
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/summary/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.referring_domains", cost_calculator=_cost_from_dfs_response)
    async def referring_domains(
        self,
        target: str,
        *,
        limit: int = 100,
        order_by: str = "rank,desc",
        include_subdomains: bool = True,
    ) -> dict:
        """Top-N referring domains for the target, ordered by rank.

        Each row carries: domain, rank (DataForSEO's DR equivalent
        0-100), first_seen / lost_date, backlinks count, dofollow/
        nofollow split, country, etc.
        """
        body = [
            {
                "target": target,
                "limit": limit,
                "order_by": [order_by],
                "include_subdomains": include_subdomains,
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/referring_domains/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.anchors", cost_calculator=_cost_from_dfs_response)
    async def backlinks_anchors(
        self,
        target: str,
        *,
        limit: int = 100,
        order_by: str = "backlinks,desc",
        include_subdomains: bool = True,
    ) -> dict:
        """Top-N anchor texts pointing at the target, with frequency."""
        body = [
            {
                "target": target,
                "limit": limit,
                "order_by": [order_by],
                "include_subdomains": include_subdomains,
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/anchors/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.backlinks", cost_calculator=_cost_from_dfs_response)
    async def backlinks_links(
        self,
        target: str,
        *,
        limit: int = 150,
        mode: str = "one_per_domain",
        order_by: str = "page_from_rank,desc",
        include_subdomains: bool = True,
        backlinks_status_type: str = "live",
    ) -> dict:
        """Individual backlink records for the target (one per domain by default).

        Each row carries the referring page URL (``url_from``), the
        ``anchor``, the text immediately before/after the anchor
        (``text_pre`` / ``text_post``, a snippet of the referrer's body),
        ``semantic_location``, ``dofollow``, ``page_from_rank``, and
        ``domain_from``. ``mode='one_per_domain'`` returns one
        representative link per referring domain: ideal for sampling
        diverse referrer pages to crawl (P3-20 link position, P3-27
        brand+topic co-occurrence).

        Cost: ~$0.02 per call from the Backlinks subscription.
        """
        body = [
            {
                "target": target,
                "limit": limit,
                "mode": mode,
                "order_by": [order_by],
                "include_subdomains": include_subdomains,
                "backlinks_status_type": backlinks_status_type,
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/backlinks/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.bulk_pages_summary", cost_calculator=_cost_from_dfs_response)
    async def bulk_pages_summary(
        self,
        targets: list[str],
    ) -> dict:
        """Per-URL backlinks + rank for up to 1000 URLs in one call.

        Returns one ``items`` row per submitted URL with: rank,
        main_domain_rank, backlinks count, referring_pages,
        referring_domains, broken_backlinks. Enables P3-10
        (page-level PageRank) by exposing per-URL rank for any page
        on the audited site.
        """
        body = [{"targets": targets}]
        response = await self.client.post(
            "/v3/backlinks/bulk_pages_summary/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("backlinks.timeseries_summary", cost_calculator=_cost_from_dfs_response)
    async def backlinks_timeseries_summary(
        self,
        target: str,
        *,
        date_from: str,
        date_to: str,
        group_range: str = "month",
        include_subdomains: bool = True,
    ) -> dict:
        """Monthly snapshots of backlink-profile metrics over a date range.

        Returns a list of `items`, one per period, each with `backlinks`,
        `referring_domains`, `referring_main_domains`, `referring_pages`,
        `referring_subnets`, `referring_ips`, `rank`, plus their nofollow
        counterparts. Enables velocity computation (gains and losses).
        """
        body = [
            {
                "target": target,
                "date_from": date_from,
                "date_to": date_to,
                "group_range": group_range,
                "include_subdomains": include_subdomains,
            }
        ]
        response = await self.client.post(
            "/v3/backlinks/timeseries_summary/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("business_data.google.reviews", cost_calculator=_cost_from_dfs_response)
    async def google_reviews(
        self,
        *,
        place_id: str | None = None,
        keyword: str | None = None,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
        depth: int = 50,
        poll_interval_s: float = 6.0,
        max_poll_attempts: int = 12,
    ) -> dict:
        """Fetch GBP reviews via the task-based business_data endpoint.

        Posts a reviews task (by place_id when known, else by keyword),
        polls task_get/advanced until the result is ready (or timeout),
        and returns the parsed JSON. Returns the LAST task_get response
        — its ``result[0].items[]`` array holds individual reviews
        with per-review timestamps, ratings, text, and owner-response
        records.

        Cost: ~$0.002 base + ~$0.0008 per review item. For depth=50 this
        is roughly ~$0.04 per call. Drawn from the main DataForSEO
        pay-as-you-go balance (no separate subscription needed for
        Business Data Reviews).
        """
        import asyncio

        if not place_id and not keyword:
            raise ValueError("google_reviews needs either place_id or keyword")

        body_inner: dict[str, Any] = {
            "location_code": location_code,
            "language_code": language_code,
            "depth": depth,
        }
        if place_id:
            body_inner["place_id"] = place_id
        else:
            body_inner["keyword"] = keyword
        body = [body_inner]

        # 1. POST the task
        post_resp = await self.client.post(
            "/v3/business_data/google/reviews/task_post", json=body
        )
        post_resp.raise_for_status()
        post_data = post_resp.json()
        tasks = post_data.get("tasks") or []
        if not tasks:
            return post_data
        task_id = tasks[0].get("id")
        if not task_id:
            return post_data

        # 2. Poll task_get/advanced until ready
        last_resp: dict[str, Any] = {}
        for _ in range(max_poll_attempts):
            await asyncio.sleep(poll_interval_s)
            get_resp = await self.client.get(
                f"/v3/business_data/google/reviews/task_get/{task_id}"
            )
            if get_resp.status_code != 200:
                continue
            last_resp = get_resp.json()
            get_tasks = last_resp.get("tasks") or []
            if not get_tasks:
                continue
            t = get_tasks[0]
            status_code = t.get("status_code")
            # 20000 = "Ok" with results; 40602 etc. = still processing
            if status_code == 20000 and t.get("result"):
                return last_resp

        # Timed out — return whatever we last got
        return last_resp

    @rate_limited
    @retry_transient()
    @tracked("business_data.google.my_business_info", cost_calculator=_cost_from_dfs_response)
    async def google_my_business_info(
        self,
        keyword: str,
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
    ) -> dict:
        """Google My Business profile lookup by brand-name search.

        Returns the top matching GBP profile with full field set: name,
        address, category, phone, rating, reviews count, attributes,
        photos, claimed status, lat/lng, related businesses.
        ~$0.01 per call.
        """
        body = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        response = await self.client.post(
            "/v3/business_data/google/my_business_info/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("serp.google.organic", cost_calculator=_cost_from_dfs_response)
    async def serp_google_organic(
        self,
        keyword: str,
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
        depth: int = 100,
    ) -> dict:
        """One Google SERP for ``keyword`` — ADVANCED tier, ~$0.002/call.

        We use ``/live/advanced`` rather than ``/live/regular`` because
        the regular tier returns only organic + paid items. The advanced
        tier additionally returns every SERP feature block when present:
        AI Overview, People Also Ask, Featured Snippet, Knowledge Graph,
        Top Stories, Videos, Local Pack, Image Pack, Shopping, etc.
        Each block is a separate item in ``items`` with ``type`` set.

        Cost difference is ~3.5x ($0.002 vs $0.0006) but the regular
        tier blinds us to AI Overview citations (P6-25), SERP feature
        inventory (P0-05), and most other GEO-relevant signals.
        """
        body = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "depth": depth,
            }
        ]
        response = await self.client.post(
            "/v3/serp/google/organic/live/advanced", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("dataforseo_labs.ranked_keywords", cost_calculator=_cost_from_dfs_response)
    async def ranked_keywords(
        self,
        target: str,
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
        limit: int = 100,
    ) -> dict:
        """Keywords the target domain currently ranks for in Google.

        Returns each keyword with: rank position, search volume,
        keyword difficulty (0-100), cpc (USD), search-intent classification,
        and the URL ranking for it. ~$0.05/call for limit=100.

        location_code defaults to UK (2826). For US use 2840.
        """
        body = [
            {
                "target": target,
                "location_code": location_code,
                "language_code": language_code,
                "limit": limit,
                "order_by": ["keyword_data.keyword_info.search_volume,desc"],
            }
        ]
        response = await self.client.post(
            "/v3/dataforseo_labs/google/ranked_keywords/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("dataforseo_labs.domain_rank_overview", cost_calculator=_cost_from_dfs_response)
    async def domain_rank_overview(
        self,
        target: str,
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
    ) -> dict:
        """Domain authority proxy + organic traffic estimate. ~$0.02/call.

        location_code defaults to UK (2826); for US use 2840. Returns
        organic keywords count, traffic estimate, paid keywords/traffic,
        and the proprietary domain rank score.
        """
        body = [
            {
                "target": target,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        response = await self.client.post(
            "/v3/dataforseo_labs/google/domain_rank_overview/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("dataforseo_labs.competitors_domain", cost_calculator=_cost_from_dfs_response)
    async def competitors_domain(
        self,
        target: str,
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
        limit: int = 10,
    ) -> dict:
        """SERP-overlap competitor domains for the target. ~$0.02/call.

        Returns domains that rank for the same keywords as the target, with
        intersection counts + average positions. Keyword-overlap-based, so it
        finds *search* competitors (which can differ from declared business
        competitors) , use as a starting set the user can refine.

        location_code defaults to UK (2826); for US use 2840.
        """
        body = [
            {
                "target": target,
                "location_code": location_code,
                "language_code": language_code,
                "limit": limit,
            }
        ]
        response = await self.client.post(
            "/v3/dataforseo_labs/google/competitors_domain/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("dataforseo_labs.keyword_ideas", cost_calculator=_cost_from_dfs_response)
    async def keyword_ideas(
        self,
        seed_keywords: list[str],
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
        limit: int = 300,
    ) -> dict:
        """Keyword ideas relevant to the seed keywords , the niche's broader keyword
        universe. ~$0.02/call.

        Seeds are the site's own ranked keywords; the response is the wider set of
        related keywords, each with search volume + competition (keyword_info) and
        keyword difficulty (keyword_properties). This is the idea-generation step
        that competitor-gap analysis alone does not give you.

        location_code defaults to UK (2826); for US use 2840.
        """
        body = [
            {
                "keywords": [k for k in seed_keywords if k][:200],
                "location_code": location_code,
                "language_code": language_code,
                "limit": limit,
                "order_by": ["keyword_info.search_volume,desc"],
            }
        ]
        response = await self.client.post(
            "/v3/dataforseo_labs/google/keyword_ideas/live", json=body
        )
        response.raise_for_status()
        return response.json()

    @rate_limited
    @retry_transient()
    @tracked("dataforseo_labs.bulk_keyword_difficulty", cost_calculator=_cost_from_dfs_response)
    async def bulk_keyword_difficulty(
        self,
        keywords: list[str],
        *,
        location_code: int = 2826,  # United Kingdom
        language_code: str = "en",
    ) -> dict:
        """Keyword difficulty (0-100) for up to 1000 keywords in one call. ~$0.01.

        Difficulty estimates how hard it is to reach Google page 1 for the keyword
        (higher = harder). Paired with search volume, it separates winnable targets
        from the ones a low-authority site cannot realistically rank for yet.

        location_code defaults to UK (2826); for US use 2840.
        """
        body = [
            {
                "keywords": [k for k in keywords if k][:1000],
                "location_code": location_code,
                "language_code": language_code,
            }
        ]
        response = await self.client.post(
            "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live", json=body
        )
        response.raise_for_status()
        return response.json()
