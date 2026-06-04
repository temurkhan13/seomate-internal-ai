"""Competitive analysis , you vs N competitors.

A separate product surface from the site audit. The audit assesses one site's
intrinsic, fixable health; this COMPARES the site against competitors across
visibility, keyword positioning, and (when backlink data is available) authority.
It is deliberately not part of the 224-variable audit , competitive standing is
an insight, not a pass/fail site-health item.

Uses the DataForSEO Labs endpoints already in the adapter (ranked_keywords,
domain_rank_overview) plus competitors_domain for optional auto-discovery. The
caller should pass the user's REAL business competitors for a meaningful result;
auto-discovery (keyword-overlap) is a fallback starting set.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any
from uuid import uuid4

from seomate.adapters import AdapterContext, DataForSEOAdapter
from seomate.utils.cost_tracker import CostTracker
from seomate.utils.html_fetch import fetch_html_pages

UK_LOCATION = 2826
_BIG = 10**6  # sentinel for "not ranking" when comparing positions


def _ctx() -> AdapterContext:
    return AdapterContext(
        audit_id=uuid4(),
        cost_tracker=CostTracker(cap_gbp=10.0, warn_fraction=0.8),
        taxonomy_version="competitive",
    )


def _norm(domain: str | None) -> str:
    d = (domain or "").strip().lower()
    for p in ("https://", "http://"):
        if d.startswith(p):
            d = d[len(p):]
    return d.removeprefix("www.").rstrip("/")


def _overview_metrics(resp: dict) -> dict[str, Any]:
    """organic keyword count + estimated traffic + domain rank from domain_rank_overview."""
    try:
        item = resp["tasks"][0]["result"][0]["items"][0]
    except (KeyError, IndexError, TypeError):
        return {"organic_keywords": 0, "organic_traffic": 0, "domain_rank": None}
    organic = (item.get("metrics") or {}).get("organic") or {}
    return {
        "organic_keywords": int(organic.get("count") or 0),
        "organic_traffic": round(float(organic.get("etv") or 0)),  # estimated traffic value
        "domain_rank": item.get("rank") or item.get("domain_rank"),
    }


def _ranked_map(resp: dict) -> dict[str, dict[str, Any]]:
    """keyword -> {volume, position, url} from ranked_keywords."""
    out: dict[str, dict[str, Any]] = {}
    try:
        items = resp["tasks"][0]["result"][0]["items"] or []
    except (KeyError, IndexError, TypeError):
        return out
    for it in items:
        kd = it.get("keyword_data") or {}
        keyword = kd.get("keyword")
        if not keyword:
            continue
        info = kd.get("keyword_info") or {}
        serp = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
        out[keyword] = {
            "volume": int(info.get("search_volume") or 0),
            "position": serp.get("rank_absolute") or serp.get("rank_group"),
            "url": serp.get("relative_url") or serp.get("url"),
        }
    return out


def _pos(v: Any) -> int:
    return int(v) if isinstance(v, (int, float)) and v else _BIG


# Giant aggregators / platforms / directories that rank for everything , they
# are never the target's real business competitors, so they're filtered out of
# keyword-intelligence discovery.
_AGGREGATOR_DENYLIST = {
    "youtube.com", "reddit.com", "wikipedia.org", "linkedin.com", "medium.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "pinterest.com",
    "quora.com", "github.com", "amazon.com", "google.com", "microsoft.com",
    "apple.com", "yelp.com", "glassdoor.com", "indeed.com", "trustpilot.com",
    "g2.com", "capterra.com", "clutch.co", "goodfirms.co", "designrush.com",
    "upwork.com", "fiverr.com", "stackoverflow.com", "w3schools.com",
    "geeksforgeeks.org", "tutorialspoint.com", "wikihow.com", "forbes.com",
    "techcrunch.com", "gartner.com", "statista.com", "hubspot.com",
    "wordpress.com", "wix.com", "shopify.com", "bbc.co.uk", "bbc.com",
}


def _is_denied(domain: str) -> bool:
    return any(domain == x or domain.endswith(f".{x}") for x in _AGGREGATOR_DENYLIST)


def _serp_domains(resp: dict) -> list[str]:
    out: list[str] = []
    try:
        items = resp["tasks"][0]["result"][0]["items"] or []
    except (KeyError, IndexError, TypeError):
        return out
    for it in items:
        if it.get("type") != "organic":
            continue
        d = _norm(it.get("domain") or it.get("url"))
        if d:
            out.append(d)
    return out


# Generic homepage section labels that are not services , dropped from the
# content-derived competitor queries.
_GENERIC_HEADINGS = frozenset({
    "home", "about", "about us", "contact", "contact us", "services",
    "our services", "what we do", "who we are", "why choose us", "why us",
    "our work", "portfolio", "our portfolio", "case studies", "testimonials",
    "reviews", "clients", "our clients", "blog", "news", "insights", "careers",
    "team", "our team", "faq", "faqs", "get started", "get a quote",
    "request a quote", "get in touch", "read more", "learn more", "subscribe",
    "newsletter", "pricing", "our process", "how it works", "privacy policy",
    "terms", "menu", "search", "login", "sign up", "follow us", "quick links",
    "useful links", "latest posts", "recent posts", "our mission", "our vision",
    "what our clients say", "frequently asked questions",
})
# Business-entity words; if a service phrase already has one, we don't append
# "company" when forming the competitor search query.
_BUSINESS_ENTITY = ("company", "companies", "agency", "agencies", "studio",
                    "consultancy", "consultants", "firm")


def _service_queries_from_html(html: str, target: str) -> list[str]:
    """Derive 'what this business does' search queries from the site's OWN
    homepage content (title + headings).

    Competitor discovery should be grounded in what the site IS, not the
    keywords it happens to rank for. A services business describes its services
    in its title and section headings ("Blockchain Development", "Mobile App
    Development"); SERPing those finds businesses offering the same services.
    Generic section labels (About / Contact / Blog ...) and the brand name are
    dropped. Bare service phrases get "company" appended so the SERP returns
    competitors rather than tutorials.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    brand_tokens = set(re.findall(r"[a-z]+", target.split(".")[0].lower()))
    raw: list[str] = []
    if soup.title and soup.title.get_text(strip=True):
        raw.extend(
            re.split(r"[|\-–—:·•]", soup.title.get_text(" ", strip=True))
        )
    for tag in soup.find_all(["h1", "h2", "h3"]):
        raw.append(tag.get_text(" ", strip=True))

    out: list[str] = []
    seen: set[str] = set()
    for c in raw:
        p = re.sub(r"\s+", " ", (c or "")).strip().strip(" .,:;|-–—").lower()
        if not p or p in _GENERIC_HEADINGS:
            continue
        words = p.split()
        if len(words) < 2 or len(words) > 6:
            continue
        if set(words) <= brand_tokens:  # the phrase is just the brand name
            continue
        if p in seen:
            continue
        seen.add(p)
        q = p if any(e in words for e in _BUSINESS_ENTITY) else f"{p} company"
        out.append(q)
    return out


async def _discover_competitors(
    dfs: DataForSEOAdapter,
    target: str,
    *,
    location_code: int,
    language_code: str,
    max_queries: int = 6,
    top_n: int = 5,
) -> tuple[list[str], str]:
    """Content-based competitor discovery , find who offers the same SERVICES.

    Reads the target's own homepage (title + headings) to learn what the
    business actually does, SERPs those service queries, and collects the
    domains that recur , minus aggregators. Those are real competitors offering
    the same services (a research database or a SaaS product never ranks for
    "software development company", so giants drop out by construction).

    Falls back to the site's ranked keywords only when the homepage can't be
    read (e.g. a JS-only shell). Returns ``(competitors, discovery_method)``.
    """
    queries: list[str] = []
    method = "content_services"
    try:
        primary = f"https://{target}/"
        pages = await fetch_html_pages([primary], concurrency=2, timeout_seconds=15)
        page = pages.get(primary)
        if page and page.fetch_error is None and page.status_code < 400 and page.html:
            queries = _service_queries_from_html(page.html, target)[:max_queries]
    except Exception:  # noqa: BLE001 - discovery must never crash the run
        queries = []

    if not queries:
        # Fallback: the site's own ranked keywords. Weak for low-footprint sites
        # (this is what surfaced giants like sciencedirect/atlassian before).
        method = "ranked_keywords_fallback"
        try:
            rk = await dfs.ranked_keywords(
                target, location_code=location_code, language_code=language_code, limit=50
            )
            kw_map = _ranked_map(rk)
            queries = sorted(
                kw_map, key=lambda k: kw_map[k]["volume"], reverse=True
            )[:max_queries]
        except Exception:  # noqa: BLE001
            queries = []

    freq: Counter[str] = Counter()
    for q in queries:
        try:
            serp = await dfs.serp_google_organic(
                q, location_code=location_code, language_code=language_code, depth=20
            )
        except Exception:  # noqa: BLE001 - one bad SERP shouldn't sink discovery
            continue
        for d in set(_serp_domains(serp)):
            if d == target or _is_denied(d):
                continue
            freq[d] += 1
    return [d for d, _ in freq.most_common(top_n)], method


async def run_competitive(
    target: str,
    competitors: list[str] | None = None,
    *,
    location_code: int = UK_LOCATION,
    language_code: str = "en",
    keyword_limit: int = 200,
    gap_top: int = 25,
) -> dict[str, Any]:
    """Compare ``target`` against ``competitors`` (auto-discovered if not given).

    Returns a structured report: per-domain visibility, and per-competitor the
    keyword gaps (they rank, we don't), shared keywords where they out-rank us,
    and how many shared keywords we win. Sorted by search volume.
    """
    target = _norm(target)
    provided = [c for c in (_norm(x) for x in (competitors or [])) if c and c != target]
    auto_discovered = False
    discovery_method = "user_provided"

    async with DataForSEOAdapter(_ctx()) as dfs:
        if not provided:
            # Primary: content-based discovery (who offers the same services the
            # site describes on its homepage, minus aggregators) , real peers.
            provided, discovery_method = await _discover_competitors(
                dfs, target, location_code=location_code, language_code=language_code
            )
            if not provided:
                # Last-resort fallback: keyword-overlap (weak; giants dominate).
                discovery_method = "keyword_overlap_fallback"
                disc = await dfs.competitors_domain(
                    target, location_code=location_code, language_code=language_code, limit=8
                )
                try:
                    items = disc["tasks"][0]["result"][0]["items"] or []
                except (KeyError, IndexError, TypeError):
                    items = []
                provided = [
                    d for d in (_norm(i.get("domain")) for i in items)
                    if d and d != target
                ][:5]
            auto_discovered = True

        # Pass 1: visibility (the cheap overview) for the target + all candidates.
        overview: dict[str, dict[str, Any]] = {}
        for d in [target, *provided]:
            ov = await dfs.domain_rank_overview(
                d, location_code=location_code, language_code=language_code
            )
            m = _overview_metrics(ov)
            m.update({"domain": d, "is_target": d == target})
            overview[d] = m

        # Drop auto-discovered competitors with no organic presence. A domain that
        # ranked for one stray keyword (often an academic / edu page) but has zero
        # ranked keywords overall is not a real business competitor , it only adds
        # an empty 0/0 row. User-supplied competitors are always kept.
        if auto_discovered:
            provided = [c for c in provided if overview[c]["organic_keywords"] > 0]

        domains = [target, *provided]
        visibility: list[dict[str, Any]] = [overview[d] for d in domains]

        # Pass 2: ranked keywords for the survivors only.
        ranked: dict[str, dict[str, dict[str, Any]]] = {}
        for d in domains:
            rk = await dfs.ranked_keywords(
                d, location_code=location_code, language_code=language_code, limit=keyword_limit
            )
            ranked[d] = _ranked_map(rk)

    our = ranked.get(target, {})
    our_kw = set(our)
    per_competitor: list[dict[str, Any]] = []
    for c in provided:
        their = ranked.get(c, {})
        their_kw = set(their)
        gaps = sorted(
            (
                {
                    "keyword": k,
                    "volume": their[k]["volume"],
                    "their_position": their[k]["position"],
                    "their_url": their[k]["url"],
                }
                for k in (their_kw - our_kw)
            ),
            key=lambda x: x["volume"],
            reverse=True,
        )
        shared = their_kw & our_kw
        losing = sorted(
            (
                {
                    "keyword": k,
                    "volume": their[k]["volume"],
                    "our_position": our[k]["position"],
                    "their_position": their[k]["position"],
                }
                for k in shared
                if _pos(our[k]["position"]) > _pos(their[k]["position"])
            ),
            key=lambda x: x["volume"],
            reverse=True,
        )
        we_win = sum(1 for k in shared if _pos(our[k]["position"]) < _pos(their[k]["position"]))
        per_competitor.append(
            {
                "domain": c,
                "gap_count": len(their_kw - our_kw),
                "shared_count": len(shared),
                "we_win_shared": we_win,
                "they_win_shared": len(losing),
                "top_keyword_gaps": gaps[:gap_top],
                "top_losing_keywords": losing[:gap_top],
            }
        )

    return {
        "target": target,
        "competitors": provided,
        "auto_discovered": auto_discovered,
        "discovery_method": discovery_method,
        "location_code": location_code,
        "language_code": language_code,
        "visibility": visibility,
        "per_competitor": per_competitor,
    }
