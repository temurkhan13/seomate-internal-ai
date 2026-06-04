"""Competitive intelligence , you vs N competitors, decision-grade.

This is NOT the site audit (which scores one site's intrinsic, fixable health).
It profiles each competitor across the dimensions a business actually needs to
make decisions , traffic, keyword footprint, backlink authority, GEO/entity
presence , and surfaces THE GAPS:

  * Competitor gaps: the commercial, page-1/2 keywords rivals win that the
    target does not (brand terms, off-vertical noise, and dead positions
    filtered out, so the list is decisions, not noise).
  * Self-gap: where the target ranks for the WRONG things (a stray
    "<brand> photography" off a contact page) instead of its money keywords.

Deterministic platform layer only. Every number here comes from DataForSEO
(Labs + Backlinks), the Google Knowledge Graph, and a homepage crawl. The
strategic read , what to DO about the gaps , is authored by a Claude session and
attached to the saved run (the ``analysis`` field), never generated in this
service. Platform gives the information; the session gives the judgment.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any
from uuid import uuid4

from seomate.adapters import AdapterContext, DataForSEOAdapter
from seomate.adapters.knowledge_graph import KnowledgeGraphAdapter
from seomate.utils.cost_tracker import CostTracker
from seomate.utils.html_fetch import fetch_html_pages

UK_LOCATION = 2826
_BIG = 10**6  # sentinel for "not ranking" when comparing positions
_PAGE2 = 20  # pos <= 20 is Google page 1-2; a "gap" deeper than this is not one the competitor is winning
_COMMERCIAL_INTENT = {"commercial", "transactional"}


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


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #
def _overview_metrics(resp: dict) -> dict[str, Any]:
    """Traffic + keyword counts + position distribution from domain_rank_overview.

    The overview already carries the organic position buckets (pos_1, pos_2_3,
    pos_4_10 ...), so the whole "where do their rankings sit" distribution comes
    free with the visibility call , no extra request.
    """
    try:
        item = resp["tasks"][0]["result"][0]["items"][0]
    except (KeyError, IndexError, TypeError):
        item = {}
    metrics = item.get("metrics") or {}
    organic = metrics.get("organic") or {}
    paid = metrics.get("paid") or {}

    def _i(d: dict, k: str) -> int:
        return int(d.get(k) or 0)

    deep = sum(
        _i(organic, k)
        for k in (
            "pos_21_30", "pos_31_40", "pos_41_50", "pos_51_60",
            "pos_61_70", "pos_71_80", "pos_81_90", "pos_91_100",
        )
    )
    return {
        "organic_keywords": _i(organic, "count"),
        "organic_traffic": round(float(organic.get("etv") or 0)),
        "paid_keywords": _i(paid, "count"),
        "paid_traffic": round(float(paid.get("etv") or 0)),
        "domain_rank": item.get("rank") or item.get("domain_rank"),
        "position_distribution": {
            "top3": _i(organic, "pos_1") + _i(organic, "pos_2_3"),
            "pos_4_10": _i(organic, "pos_4_10"),
            "pos_11_20": _i(organic, "pos_11_20"),
            "pos_21_plus": deep,
        },
    }


def _ranked_map(resp: dict) -> dict[str, dict[str, Any]]:
    """keyword -> {volume, cpc, difficulty, intent, position, url} from ranked_keywords."""
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
        props = kd.get("keyword_properties") or {}
        intent = (kd.get("search_intent_info") or {}).get("main_intent")
        serp = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
        out[keyword] = {
            "volume": int(info.get("search_volume") or 0),
            "cpc": round(float(info.get("cpc") or 0), 2),
            "difficulty": props.get("keyword_difficulty"),
            "intent": (intent or "").lower() or None,
            "position": serp.get("rank_absolute") or serp.get("rank_group"),
            "url": serp.get("relative_url") or serp.get("url"),
        }
    return out


def _pos(v: Any) -> int:
    return int(v) if isinstance(v, (int, float)) and v else _BIG


# --------------------------------------------------------------------------- #
# Brand / intent classification (deterministic)
# --------------------------------------------------------------------------- #
def _brand_info(domain: str) -> dict[str, Any]:
    """Brand tokens + root for a domain, used to strip brand keywords.

    n-ix.com -> tokens {n, ix, nix}, root 'nix'
    itransition.com -> tokens {itransition}, root 'itransition'
    pixelettetech.com -> tokens {pixelettetech}, root 'pixelettetech'
    """
    root_raw = _norm(domain).split(".")[0].lower()
    parts = [p for p in re.split(r"[^a-z0-9]+", root_raw) if p]
    alpha = re.sub(r"[^a-z0-9]", "", root_raw)
    tokens = set(parts)
    # Only treat the joined form as a brand token when it's distinctive (>= 5
    # chars). Otherwise a hyphenated brand like "n-ix" collapses to "nix", which
    # collides with real entities (the Nix package manager) and the keyword
    # filters. Brand-keyword stripping still works off the individual parts.
    if alpha and len(alpha) >= 5:
        tokens.add(alpha)
    return {"tokens": tokens, "root": alpha}


def _is_brand_kw(keyword: str, brand: dict[str, Any]) -> bool:
    """True when the keyword is the brand's own name (or a clear variant).

    Catches pure-brand queries ("n-ix", "n ix") and brand-adjacent ones where a
    keyword token is a strong prefix of the brand root , so "pixelette
    photography" registers as branded against pixelettetech.com even though the
    domain root is the longer 'pixelettetech'.
    """
    words = [w for w in re.split(r"[^a-z0-9]+", keyword.lower()) if w]
    if not words:
        return False
    tokens = brand["tokens"]
    if set(words) <= tokens:  # every token is brand -> pure brand query
        return True
    root = brand["root"]
    for w in words:
        if len(w) < 5:
            continue
        if w in tokens or (root and (root.startswith(w) or w.startswith(root))):
            return True
    return False


def _commercial(kw: dict[str, Any]) -> bool:
    """A money keyword: buyer-stage search intent.

    Intent-first, not CPC-first, on purpose. Other companies' brand names
    ("opentext", "globant", "icabbi") and generic informational heads
    ("methodologies", "programming languages") all carry a CPC, so a CPC>0 test
    waved them through as "money keywords". DataForSEO labels them
    informational/navigational, which is what we filter on. CPC is only a
    fallback when intent is missing from the row.
    """
    intent = kw.get("intent")
    if intent:
        return intent in _COMMERCIAL_INTENT
    return (kw.get("cpc") or 0) > 0


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
# content-derived competitor queries and from the "what they sell" read.
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


def _site_offerings(html: str | None) -> list[str]:
    """What this site sells , its real, non-generic section headings (h1/h2)."""
    if not html:
        return []
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all(["h1", "h2"]):
        t = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
        tl = t.lower()
        if not t or tl in _GENERIC_HEADINGS or len(t) > 60:
            continue
        if 2 <= len(t.split()) <= 7 and tl not in seen:
            seen.add(tl)
            out.append(t)
    return out[:6]


def _has_structured_data(html: str | None) -> bool:
    return bool(re.search(r"application/ld\+json", html or "", re.I))


def _brand_query_from_html(html: str | None, fallback: str) -> str:
    """The real brand name from the homepage <title>, for entity lookup.

    Querying the Knowledge Graph with a domain token ("nix", "pixelettetech")
    rarely matches the company; the title's brand segment ("N-iX", "Pixelette
    Technologies", "Itransition") does. Picks the shortest title segment, which
    is almost always the brand rather than the tagline.
    """
    if not html:
        return fallback
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.get_text(strip=True):
            title = soup.title.get_text(" ", strip=True)
            parts = [p.strip() for p in re.split(r"[|\-–—:·•]", title) if p.strip()]
            if parts:
                cand = min(parts, key=len)
                if 3 <= len(cand) <= 40 and len(cand.split()) <= 5:
                    return cand
    except Exception:  # noqa: BLE001
        pass
    return fallback


# --------------------------------------------------------------------------- #
# Profile assembly
# --------------------------------------------------------------------------- #
def _keyword_profile(m: dict[str, dict[str, Any]], brand: dict[str, Any]) -> dict[str, Any]:
    """Classify a domain's ranked keywords: how many are branded vs commercial
    vs informational, where they sit, and the top money keywords it actually wins.
    """
    branded = commercial = 0
    top3 = p4_10 = p11_20 = deep = 0
    money: list[dict[str, Any]] = []
    for k, d in m.items():
        b = _is_brand_kw(k, brand)
        c = _commercial(d)
        if b:
            branded += 1
        if c:
            commercial += 1
        p = _pos(d["position"])
        if p <= 3:
            top3 += 1
        elif p <= 10:
            p4_10 += 1
        elif p <= 20:
            p11_20 += 1
        else:
            deep += 1
        if c and not b:
            money.append({"keyword": k, **d})
    money.sort(key=lambda x: x["volume"], reverse=True)
    total = len(m)
    return {
        "total": total,
        "branded": branded,
        "commercial": commercial,
        "informational": total - commercial,
        "position_buckets": {
            "top3": top3, "pos_4_10": p4_10, "pos_11_20": p11_20, "pos_21_plus": deep,
        },
        "top_commercial_keywords": money[:10],
    }


def _top_pages(m: dict[str, dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    """The domain's top pages by summed search volume of the keywords they rank."""
    agg: dict[str, dict[str, Any]] = {}
    for d in m.values():
        u = d.get("url") or "/"
        a = agg.setdefault(u, {"url": u, "keywords": 0, "volume": 0})
        a["keywords"] += 1
        a["volume"] += d.get("volume") or 0
    return sorted(agg.values(), key=lambda x: x["volume"], reverse=True)[:n]


def _backlink_profile(
    summary: dict | None, refdoms: list[dict], anchors: list[dict]
) -> dict[str, Any] | None:
    """Authority profile from backlinks_summary + referring_domains + anchors.

    None when the backlinks subscription returns nothing (the call failed or is
    off) , the FE renders that as "not measured" rather than zeros.
    """
    if not summary:
        return None
    backlinks = int(summary.get("backlinks") or 0)
    dofollow = int(summary.get("dofollow") or summary.get("backlinks_dofollow") or 0)
    return {
        "rank": summary.get("rank"),
        "backlinks": backlinks,
        "referring_domains": int(summary.get("referring_domains") or 0),
        "referring_main_domains": int(summary.get("referring_main_domains") or 0),
        "dofollow": dofollow,
        "dofollow_ratio": round(dofollow / backlinks, 3) if backlinks else None,
        "broken": int(summary.get("broken_backlinks") or 0),
        "spam_score": summary.get("backlinks_spam_score"),
        "top_referring_domains": [
            {
                "domain": d.get("domain"),
                "rank": d.get("rank"),
                "backlinks": d.get("backlinks"),
            }
            for d in (refdoms or [])[:10]
            if d.get("domain")
        ],
        "top_anchors": [
            {
                "anchor": a.get("anchor"),
                "backlinks": a.get("backlinks"),
                "referring_domains": a.get("referring_domains"),
            }
            for a in (anchors or [])[:8]
            if a.get("anchor")
        ],
    }


def _geo_signal(entity: Any, html: str | None) -> dict[str, Any]:
    """GEO / LLM-readiness signal: is the domain a recognised entity, and is its
    content machine-extractable (structured data present)?
    """
    return {
        "entity_recognized": entity is not None,
        "entity_name": getattr(entity, "name", None),
        "entity_types": [
            t for t in (getattr(entity, "types", None) or ())
            if t != "Thing"
        ][:4],
        "entity_description": getattr(entity, "description", None),
        "entity_score": round(getattr(entity, "result_score", 0) or 0, 1) if entity else None,
        "has_structured_data": _has_structured_data(html),
    }


def _match_entity(hits: list, brand: dict[str, Any], domain: str) -> Any:
    """Pick a Knowledge Graph hit only if it plausibly IS this brand.

    KG search is fuzzy and returns something for almost any query, so we only
    accept a hit whose name shares a brand token, or whose url / sameAs points
    at the domain. Prevents a random same-spelling entity being reported as "you
    are a recognised entity".
    """
    root = brand["root"]
    dom_root = domain.split(".")[0].lower() if domain else ""
    for h in hits or []:
        name = (h.name or "").lower()
        name_alpha = re.sub(r"[^a-z0-9]", "", name)
        name_tokens = {w for w in re.split(r"[^a-z0-9]+", name) if w}
        # Exact brand-token overlap (itransition == itransition).
        if name_tokens & brand["tokens"]:
            return h
        # Strong prefix match only when the root is long enough that a prefix is
        # meaningful: "pixelettetech" prefixes "pixelettetechnologiesltd", but a
        # 3-letter root like "nix" must NOT match "nixie".
        if root and len(root) >= 5 and (
            name_alpha.startswith(root)
            or (len(name_alpha) >= 5 and root.startswith(name_alpha))
        ):
            return h
        # The entity explicitly points back at the domain (url / sameAs).
        urls = " ".join([h.url or "", *(h.same_as or [])]).lower()
        if domain and (domain in urls or (dom_root and f"/{dom_root}" in urls)):
            return h
    return None


def _clean_gaps(
    their: dict[str, dict[str, Any]],
    our_kw: set[str],
    comp_brand: dict[str, Any],
    target_brand: dict[str, Any],
    *,
    top: int,
) -> list[dict[str, Any]]:
    """Commercial, page-1/2 keyword gaps , the decisions, with the noise removed.

    Drops: keywords we already rank for; deep positions the competitor isn't
    winning either (pos > 20); non-commercial/informational terms; and brand
    queries (theirs or ours). What survives is "money keywords this competitor
    wins on page 1-2 that you don't have".
    """
    gaps: list[dict[str, Any]] = []
    for k, d in their.items():
        if k in our_kw:
            continue
        if _pos(d["position"]) > _PAGE2:
            continue
        if not _commercial(d):
            continue
        if _is_brand_kw(k, comp_brand) or _is_brand_kw(k, target_brand):
            continue
        gaps.append({
            "keyword": k,
            "volume": d["volume"],
            "cpc": d["cpc"],
            "difficulty": d["difficulty"],
            "intent": d["intent"],
            "their_position": d["position"],
            "their_url": d["url"],
        })
    gaps.sort(key=lambda x: x["volume"], reverse=True)
    return gaps[:top]


def _self_audit(
    target: str,
    our: dict[str, dict[str, Any]],
    brand: dict[str, Any],
    money_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    """The self-gap: what the target ACTUALLY ranks for vs what it should.

    Surfaces the target's real keyword reality so misalignment is visible , the
    brand-adjacent, non-commercial junk (a stray "<brand> photography") gets
    flagged, and the count of genuine money keywords is laid bare next to the
    commercial keywords competitors win that the target is missing.
    """
    ranked: list[dict[str, Any]] = []
    off_profile: list[dict[str, Any]] = []
    money_owned = 0
    page1 = 0
    for k, d in sorted(our.items(), key=lambda kv: kv[1]["volume"], reverse=True):
        b = _is_brand_kw(k, brand)
        c = _commercial(d)
        p = _pos(d["position"])
        row = {
            "keyword": k,
            "volume": d["volume"],
            "position": d["position"],
            "intent": d["intent"],
            "cpc": d["cpc"],
            "branded": b,
            "commercial": c,
        }
        ranked.append(row)
        # "Owned" means it actually works: a commercial keyword ranking on page 1.
        # A commercial term sitting at position 80 drives nothing, so it does not
        # count , that's the honest self-gap (0 page-1 money keywords for a site
        # whose whole footprint is page 5+).
        if p <= 10:
            page1 += 1
            if c and not b:
                money_owned += 1
        # Brand-adjacent but non-commercial == ranking for the wrong thing
        # (the "<brand> photography" case): you own it, but it sells nothing.
        if b and not c and len(k.split()) >= 2:
            off_profile.append(row)
    return {
        "total_ranked": len(our),
        "money_keywords_owned": money_owned,
        "page1_keywords": page1,
        "branded": sum(1 for r in ranked if r["branded"]),
        "informational": sum(1 for r in ranked if not r["commercial"]),
        "ranked_keywords": ranked[:40],
        "off_profile_keywords": off_profile[:15],
        "missing_money_keywords": money_gaps,
    }


# --------------------------------------------------------------------------- #
# Competitor discovery (deterministic fallback when none supplied)
# --------------------------------------------------------------------------- #
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
    domains that recur , minus aggregators. Falls back to ranked keywords when
    the homepage can't be read. Returns ``(competitors, discovery_method)``.

    NOTE: deterministic discovery is a weak best-effort for low-footprint sites.
    The right competitor set is the one a session/user supplies; this only seeds
    the page when nothing was passed.
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


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
async def run_competitive(
    target: str,
    competitors: list[str] | None = None,
    *,
    location_code: int = UK_LOCATION,
    language_code: str = "en",
    keyword_limit: int = 200,
    gap_top: int = 15,
) -> dict[str, Any]:
    """Decision-grade competitor intelligence for ``target`` vs ``competitors``.

    For the target and each competitor, builds a full profile (traffic, keyword
    profile, backlink authority, GEO/entity, what they sell, top pages), then
    the gaps: clean commercial keyword gaps per competitor and the target's
    self-gap (what it ranks for vs what it should). ``analysis`` is left None ,
    a Claude session fills it on the saved snapshot.
    """
    target = _norm(target)
    target_brand = _brand_info(target)
    provided = [c for c in (_norm(x) for x in (competitors or [])) if c and c != target]
    auto_discovered = False
    discovery_method = "user_provided"

    async with DataForSEOAdapter(_ctx()) as dfs, KnowledgeGraphAdapter(_ctx()) as kg:
        if not provided:
            provided, discovery_method = await _discover_competitors(
                dfs, target, location_code=location_code, language_code=language_code
            )
            if not provided:
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

        # Pass 1: visibility overview (cheap) for the target + all candidates.
        overview: dict[str, dict[str, Any]] = {}
        for d in [target, *provided]:
            ov = await dfs.domain_rank_overview(
                d, location_code=location_code, language_code=language_code
            )
            overview[d] = _overview_metrics(ov)

        # Drop auto-discovered competitors with no organic presence (an academic
        # page that ranked once is not a competitor). User-supplied stay.
        if auto_discovered:
            provided = [c for c in provided if overview[c]["organic_keywords"] > 0]

        domains = [target, *provided]

        # Homepage crawl (one batch) , for "what they sell" + structured-data GEO.
        urls = [f"https://{d}/" for d in domains]
        try:
            pages = await fetch_html_pages(urls, concurrency=4, timeout_seconds=15)
        except Exception:  # noqa: BLE001
            pages = {}
        html_for: dict[str, str | None] = {}
        for d in domains:
            pg = pages.get(f"https://{d}/")
            html_for[d] = pg.html if (pg and pg.fetch_error is None and pg.html) else None

        # Pass 2: ranked keywords for each domain.
        ranked: dict[str, dict[str, dict[str, Any]]] = {}
        for d in domains:
            rk = await dfs.ranked_keywords(
                d, location_code=location_code, language_code=language_code, limit=keyword_limit
            )
            ranked[d] = _ranked_map(rk)

        # Pass 3: backlink authority for each domain (fail-soft per call).
        backlinks: dict[str, dict[str, Any] | None] = {}
        for d in domains:
            summary = None
            refdoms: list[dict] = []
            anchors: list[dict] = []
            try:
                resp = await dfs.backlinks_summary(d)
                res = (resp.get("tasks") or [{}])[0].get("result") or []
                if res and isinstance(res[0], dict):
                    summary = res[0]
            except Exception:  # noqa: BLE001
                summary = None
            try:
                resp = await dfs.referring_domains(d, limit=25)
                res = (resp.get("tasks") or [{}])[0].get("result") or []
                if res and isinstance(res[0], dict):
                    refdoms = res[0].get("items") or []
            except Exception:  # noqa: BLE001
                refdoms = []
            try:
                resp = await dfs.backlinks_anchors(d, limit=25)
                res = (resp.get("tasks") or [{}])[0].get("result") or []
                if res and isinstance(res[0], dict):
                    anchors = res[0].get("items") or []
            except Exception:  # noqa: BLE001
                anchors = []
            backlinks[d] = _backlink_profile(summary, refdoms, anchors)

        # GEO entity recognition (fail-soft; skipped entirely if KG unconfigured).
        entity_for: dict[str, Any] = {d: None for d in domains}
        if getattr(kg, "is_configured", False):
            for d in domains:
                brand = _brand_info(d)
                fallback = (brand["tokens"] and max(brand["tokens"], key=len)) or d
                query = _brand_query_from_html(html_for[d], fallback)
                try:
                    hits = await kg.search(query, limit=5)
                    entity_for[d] = _match_entity(hits, brand, d)
                except Exception:  # noqa: BLE001
                    entity_for[d] = None

    # ---- assemble profiles -------------------------------------------------
    profiles: list[dict[str, Any]] = []
    visibility: list[dict[str, Any]] = []
    for d in domains:
        ov = overview[d]
        brand = target_brand if d == target else _brand_info(d)
        kp = _keyword_profile(ranked[d], brand)
        bl = backlinks[d]
        profiles.append({
            "domain": d,
            "is_target": d == target,
            "traffic": {
                "organic_keywords": ov["organic_keywords"],
                "organic_traffic": ov["organic_traffic"],
                "paid_keywords": ov["paid_keywords"],
                "paid_traffic": ov["paid_traffic"],
                "domain_rank": ov["domain_rank"],
            },
            "position_distribution": ov["position_distribution"],
            "keyword_profile": kp,
            "backlinks": bl,
            "geo": _geo_signal(entity_for[d], html_for[d]),
            "site": {
                "offerings": _site_offerings(html_for[d]),
                "top_pages": _top_pages(ranked[d]),
            },
        })
        visibility.append({
            "domain": d,
            "is_target": d == target,
            "organic_keywords": ov["organic_keywords"],
            "organic_traffic": ov["organic_traffic"],
            "domain_rank": ov["domain_rank"],
            "backlink_rank": (bl or {}).get("rank"),
            "referring_domains": (bl or {}).get("referring_domains"),
            "entity_recognized": bool(entity_for[d]),
        })

    # ---- gaps --------------------------------------------------------------
    our = ranked.get(target, {})
    our_kw = set(our)
    per_competitor: list[dict[str, Any]] = []
    all_money_gaps: dict[str, dict[str, Any]] = {}
    for c in provided:
        their = ranked.get(c, {})
        their_kw = set(their)
        comp_brand = _brand_info(c)
        clean = _clean_gaps(their, our_kw, comp_brand, target_brand, top=gap_top)
        for g in clean:
            prev = all_money_gaps.get(g["keyword"])
            if not prev or g["volume"] > prev["volume"]:
                all_money_gaps[g["keyword"]] = g
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
        per_competitor.append({
            "domain": c,
            "gap_count_raw": len(their_kw - our_kw),
            "gap_count_clean": len(clean),
            "shared_count": len(shared),
            "we_win_shared": we_win,
            "they_win_shared": len(losing),
            "money_gaps": clean,
            "top_losing_keywords": losing[:gap_top],
        })

    money_gaps_sorted = sorted(
        all_money_gaps.values(), key=lambda x: x["volume"], reverse=True
    )[:25]
    self_audit = _self_audit(target, our, target_brand, money_gaps_sorted)

    return {
        "target": target,
        "competitors": provided,
        "auto_discovered": auto_discovered,
        "discovery_method": discovery_method,
        "location_code": location_code,
        "language_code": language_code,
        "profiles": profiles,
        "visibility": visibility,
        "per_competitor": per_competitor,
        "self_audit": self_audit,
        "analysis": None,  # filled by a Claude session on the saved snapshot
    }
