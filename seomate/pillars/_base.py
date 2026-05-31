"""Pillar extractor protocol and registry.

Each variable extractor is an async function with the signature::

    async def capture_<var_id>(
        ctx: AdapterContext,
        site: SiteData,
        *,
        dataforseo: DataForSEOAdapter,
        # ... future per-adapter dependencies
    ) -> CaptureRecord

Extractors register via ``@register_extractor("P1-01")``. The
orchestrator iterates the catalog in topological order and calls every
registered extractor whose id is in scope; unregistered ids are
silently skipped (we add them stage by stage).

``SiteData`` carries a pre-fetched cache of per-page audit data, so
many cheap-layer Pillar 1 / Pillar 2 extractors share one set of
DataForSEO Instant Pages calls instead of each making their own.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from seomate.adapters import (
        AdapterContext,
        DataForSEOAdapter,
        Embedding,
        PSIResult,
    )
    from seomate.data_contract import CaptureRecord
    from seomate.utils.html_fetch import FetchedHtml
    from seomate.utils.link_graph import LinkGraph
    from seomate.utils.llm_evaluation import LlmEvaluation
    from seomate.utils.structured_data import StructuredData
    from seomate.utils.text_extraction import PageText


@dataclass(frozen=True)
class PageAudit:
    """Normalised per-page audit data from DataForSEO Instant Pages.

    A trimmed view exposing only the fields H1a extractors consume.
    Add fields lazily as new extractors land — never include raw API
    response shape because that ties the extractor logic to a specific
    adapter version.
    """

    url: str
    status_code: int
    is_redirect: bool
    is_indexable: bool

    # ─── Title / description ────────────────────────────────────────────────
    title: str | None
    title_length: int                  # 0 if no title
    has_multiple_titles: bool
    description: str | None
    description_length: int            # 0 if no description

    # ─── Headings (bucketed by tag, not in document order) ──────────────────
    h1: tuple[str, ...]
    h2: tuple[str, ...]
    h3: tuple[str, ...]
    h4: tuple[str, ...]
    h5: tuple[str, ...]
    h6: tuple[str, ...]

    # ─── Indexing / canonical ───────────────────────────────────────────────
    canonical: str | None
    meta_robots: str | None            # e.g. "noindex, nofollow"

    # ─── URL shape ──────────────────────────────────────────────────────────
    url_length: int = 0
    relative_url_length: int = 0

    # ─── Link counts ────────────────────────────────────────────────────────
    external_links_count: int = 0
    internal_links_count: int = 0
    inbound_links_count: int = 0       # internal links pointing TO this page

    # ─── Asset counts and sizes ─────────────────────────────────────────────
    images_count: int = 0
    images_size_bytes: int = 0         # 0 unless load_resources=true
    scripts_count: int = 0
    stylesheets_count: int = 0
    render_blocking_scripts_count: int = 0
    render_blocking_stylesheets_count: int = 0
    page_size_bytes: int = 0
    total_dom_size: int = 0

    # ─── Content metrics ────────────────────────────────────────────────────
    plain_text_word_count: int = 0
    plain_text_size: int = 0
    flesch_kincaid: float | None = None
    coleman_liau: float | None = None
    dale_chall: float | None = None
    smog: float | None = None
    automated_readability: float | None = None
    title_to_content_consistency: float | None = None
    description_to_content_consistency: float | None = None

    # ─── Social tags (frozen tuples-of-pairs so PageAudit stays hashable) ───
    og_tags: tuple[tuple[str, str], ...] = ()
    twitter_tags: tuple[tuple[str, str], ...] = ()

    # ─── Spelling ───────────────────────────────────────────────────────────
    spell_language: str | None = None
    misspelled_words: tuple[str, ...] = ()

    # ─── Site-level flags (DataForSEO's own duplicate / breakage checks) ────
    duplicate_title_check: bool = False
    duplicate_description_check: bool = False
    duplicate_content_check: bool = False
    broken_links_check: bool = False
    no_image_alt_check: bool = False     # True iff DataForSEO flagged any
                                         # image on this page as missing alt
    broken_resources_check: bool = False

    # ─── Composite scores ───────────────────────────────────────────────────
    onpage_score: float | None = None
    click_depth: int = 0

    # ─── Failure marker ─────────────────────────────────────────────────────
    fetch_error: str | None = None


@dataclass(frozen=True)
class BrandIdentity:
    """The audited brand's identity and naming variants.

    Used by entity-recognition variables (P0-16, P6-11, P6-29) which
    need to query Knowledge Graph / Wikipedia / Wikidata against every
    plausible name the brand might be indexed under.
    """

    name: str
    aliases: tuple[str, ...] = ()
    legal_entities: tuple[str, ...] = ()

    @property
    def all_variants(self) -> tuple[str, ...]:
        """Deduplicated tuple of every form to query."""
        seen: set[str] = set()
        out: list[str] = []
        for v in (self.name, *self.aliases, *self.legal_entities):
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return tuple(out)


@dataclass
class SiteData:
    """The audited site's identity, URL inventory, and pre-fetched audits.

    Built once at audit start by the orchestrator. Passed to every
    extractor so site-level prep (sitemap fetch, page audits) happens
    once, not per-variable.
    """

    domain: str
    primary_url: str
    urls: list[str] = field(default_factory=list)
    page_audits: dict[str, PageAudit] = field(default_factory=dict)
    page_audit_errors: dict[str, str] = field(default_factory=dict)
    brand: BrandIdentity | None = None
    html_pages: dict[str, "FetchedHtml"] = field(default_factory=dict)
    structured_data: dict[str, "StructuredData"] = field(default_factory=dict)
    link_graph: "LinkGraph | None" = None
    text_content: dict[str, "PageText"] = field(default_factory=dict)
    embeddings: dict[str, "Embedding"] = field(default_factory=dict)
    embeddings_configured: bool = False
    ranked_keywords: list[dict] = field(default_factory=list)
    domain_rank_overview: dict | None = None
    brand_keyword_volumes: list[dict] = field(default_factory=list)
    psi_results: dict[str, "PSIResult"] = field(default_factory=dict)
    psi_configured: bool = False
    llm_evaluations: dict[str, dict[str, "LlmEvaluation"]] = field(default_factory=dict)
    llm_configured: bool = False
    llm_evaluations_skipped: bool = False  # True when --only mode skipped the LLM eval phase deliberately
    gbp_info: dict | None = None
    gbp_discovery_method: str = "not_attempted"  # 'configured_place_id' | 'brand_search' | 'not_found'
    competitors: list[str] = field(default_factory=list)  # Direct competitor domains, SERP-discovered
    competitor_discovery_method: str = "not_attempted"  # 'configured' | 'serp_overlap' | 'not_attempted'
    competitor_ranked_keywords: dict[str, list[dict]] = field(default_factory=dict)  # competitor_domain -> ranked_keywords list
    serp_results: dict[str, dict] = field(default_factory=dict)  # keyword -> DataForSEO SERP response items list
    business_reviews: list[dict] = field(default_factory=list)  # GBP review records from DataForSEO Business Data Reviews endpoint
    backlinks_summary: dict | None = None  # DataForSEO Backlinks Summary response (aggregate metrics)
    referring_domains: list[dict] = field(default_factory=list)  # Top-N referring domain records
    backlinks_anchors: list[dict] = field(default_factory=list)  # Top-N anchor text distribution records
    backlinks_timeseries: list[dict] = field(default_factory=list)  # Monthly profile snapshots over a 12-month window
    wikipedia_links: dict | None = None  # Wikipedia search results for brand name (for P3-28)
    bulk_pages_backlinks: list[dict] = field(default_factory=list)  # Per-URL rank + backlink count from /backlinks/bulk_pages_summary (P3-10)

    @property
    def successful_audits(self) -> list[PageAudit]:
        """All successfully-fetched page audits (no fetch_error)."""
        return [p for p in self.page_audits.values() if p.fetch_error is None]

    @property
    def successful_structured_data(self) -> list["StructuredData"]:
        """All pages with non-empty HTML where parsing succeeded."""
        return [
            sd
            for url, sd in self.structured_data.items()
            if (
                self.html_pages.get(url) is not None
                and self.html_pages[url].fetch_error is None
                and self.html_pages[url].status_code < 400
            )
        ]


def normalise_instant_page_response(response: dict[str, Any]) -> list[PageAudit]:
    """Walk a DataForSEO instant_pages response into PageAudit objects.

    DataForSEO instant_pages is single-URL-per-call in practice; in
    theory the response could carry multiple tasks, so we walk the
    full ``tasks[].result[].items[]`` structure and yield every page
    found. Returns an empty list if the response shape is malformed.
    """
    out: list[PageAudit] = []
    for task in response.get("tasks") or []:
        for result in task.get("result") or []:
            for item in result.get("items") or []:
                pa = _page_audit_from_item(item)
                if pa is not None:
                    out.append(pa)
    return out


def _page_audit_from_item(item: dict[str, Any]) -> PageAudit | None:
    url = item.get("url") or ""
    if not url:
        return None
    meta = item.get("meta") or {}
    content = meta.get("content") or {}
    checks = item.get("checks") or {}
    htags = meta.get("htags") or {}
    spell = meta.get("spell") or {}
    social = meta.get("social_media_tags") or {}

    status_code = item.get("status_code") or 0
    is_redirect = bool(checks.get("is_redirect", False))
    is_noindex = bool(
        checks.get("no_index_meta_tag", False)
        or checks.get("noindex_canonical_redirect", False)
    )
    is_indexable = (
        isinstance(status_code, int)
        and status_code == 200
        and not is_redirect
        and not is_noindex
    )
    title = meta.get("title")
    description = meta.get("description")

    # Split social_media_tags into og:* and twitter:* groups.
    og_tags = tuple(
        sorted((k, str(v)) for k, v in social.items() if k.startswith("og:"))
    )
    twitter_tags = tuple(
        sorted(
            (k, str(v)) for k, v in social.items() if k.startswith("twitter:")
        )
    )

    misspelled = spell.get("misspelled") if isinstance(spell, dict) else None
    if isinstance(misspelled, list):
        misspelled_tuple = tuple(str(w) for w in misspelled)
    else:
        misspelled_tuple = ()

    return PageAudit(
        url=url,
        status_code=int(status_code) if isinstance(status_code, int) else 0,
        is_redirect=is_redirect,
        is_indexable=is_indexable,
        title=title,
        title_length=int(meta.get("title_length") or 0)
        or (len(title) if isinstance(title, str) else 0),
        has_multiple_titles=bool(checks.get("duplicate_title", False)),
        description=description,
        description_length=int(meta.get("description_length") or 0)
        or (len(description) if isinstance(description, str) else 0),
        h1=tuple(htags.get("h1") or ()),
        h2=tuple(htags.get("h2") or ()),
        h3=tuple(htags.get("h3") or ()),
        h4=tuple(htags.get("h4") or ()),
        h5=tuple(htags.get("h5") or ()),
        h6=tuple(htags.get("h6") or ()),
        canonical=meta.get("canonical"),
        meta_robots=_extract_robots_meta(meta),
        url_length=int(item.get("url_length") or 0),
        relative_url_length=int(item.get("relative_url_length") or 0),
        external_links_count=int(meta.get("external_links_count") or 0),
        internal_links_count=int(meta.get("internal_links_count") or 0),
        inbound_links_count=int(meta.get("inbound_links_count") or 0),
        images_count=int(meta.get("images_count") or 0),
        images_size_bytes=int(meta.get("images_size") or 0),
        scripts_count=int(meta.get("scripts_count") or 0),
        stylesheets_count=int(meta.get("stylesheets_count") or 0),
        render_blocking_scripts_count=int(
            meta.get("render_blocking_scripts_count") or 0
        ),
        render_blocking_stylesheets_count=int(
            meta.get("render_blocking_stylesheets_count") or 0
        ),
        page_size_bytes=int(item.get("size") or 0),
        total_dom_size=int(item.get("total_dom_size") or 0),
        plain_text_word_count=int(content.get("plain_text_word_count") or 0),
        plain_text_size=int(content.get("plain_text_size") or 0),
        flesch_kincaid=_as_float(content.get("flesch_kincaid_readability_index")),
        coleman_liau=_as_float(content.get("coleman_liau_readability_index")),
        dale_chall=_as_float(content.get("dale_chall_readability_index")),
        smog=_as_float(content.get("smog_readability_index")),
        automated_readability=_as_float(
            content.get("automated_readability_index")
        ),
        title_to_content_consistency=_as_float(
            content.get("title_to_content_consistency")
        ),
        description_to_content_consistency=_as_float(
            content.get("description_to_content_consistency")
        ),
        og_tags=og_tags,
        twitter_tags=twitter_tags,
        spell_language=spell.get("hunspell_language_code")
        if isinstance(spell, dict)
        else None,
        misspelled_words=misspelled_tuple,
        duplicate_title_check=bool(item.get("duplicate_title", False)),
        duplicate_description_check=bool(item.get("duplicate_description", False)),
        duplicate_content_check=bool(item.get("duplicate_content", False)),
        broken_links_check=bool(item.get("broken_links", False)),
        no_image_alt_check=bool(
            (item.get("checks") or {}).get("no_image_alt", False)
        ),
        broken_resources_check=bool(item.get("broken_resources", False)),
        onpage_score=_as_float(item.get("onpage_score")),
        click_depth=int(item.get("click_depth") or 0),
    )


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_robots_meta(meta: dict[str, Any]) -> str | None:
    """Best-effort extraction of the robots meta directive string."""
    if not isinstance(meta, dict):
        return None
    # DataForSEO surfaces robots in a few possible places depending on
    # the response variant; try the most common ones.
    for key in ("robots", "meta_robots", "robots_meta"):
        v = meta.get(key)
        if isinstance(v, str) and v:
            return v
    return None


class Extractor(Protocol):
    """Async callable shape for a variable extractor."""

    async def __call__(
        self,
        ctx: "AdapterContext",
        site: SiteData,
        *,
        dataforseo: "DataForSEOAdapter",
    ) -> "CaptureRecord": ...


# Registry: variable_id ("P1-01") -> extractor coroutine.
EXTRACTOR_REGISTRY: dict[str, Extractor] = {}


def register_extractor(
    variable_id: str,
) -> Callable[[Callable[..., Awaitable["CaptureRecord"]]], Callable[..., Awaitable["CaptureRecord"]]]:
    """Decorator that registers an extractor against a variable id."""

    def decorator(
        fn: Callable[..., Awaitable["CaptureRecord"]],
    ) -> Callable[..., Awaitable["CaptureRecord"]]:
        if variable_id in EXTRACTOR_REGISTRY:
            raise RuntimeError(f"Extractor already registered for {variable_id}")
        EXTRACTOR_REGISTRY[variable_id] = fn  # type: ignore[assignment]
        return fn

    return decorator
