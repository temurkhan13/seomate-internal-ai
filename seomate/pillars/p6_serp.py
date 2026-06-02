"""SERP-driven GEO outcome metrics (P6).

These extractors run live SERP queries against the site's keyword
universe and parse the SERP feature blocks to compute outcome KPIs.
The headline variable here is **P6-25 AI Overview inclusion frequency**
— the metric most stakeholders care about.

Universe is auto-discovered: until P0-13 (curated keyword list) lands,
we use the keywords the domain already ranks for (from
``site.ranked_keywords``). This is conservative — adding bigger
intent-discovery queries later would broaden the universe.

Cost note: SERP queries on the live regular tier are ~£0.012 each
(reported by DataForSEO). For a 18-keyword universe that's ~£0.22
per audit. We expose the ``MAX_SERP_QUERIES`` cap so the orchestrator
can never burn through balance unexpectedly.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from seomate.adapters import AdapterContext, DataForSEOAdapter
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor


# ─── Tunables ───────────────────────────────────────────────────────────────

# Hard cap so a curated keyword set of 1,000 doesn't accidentally cost £12
# per audit. Configurable later via SeoMateConfig if we need to scale up.
MAX_SERP_QUERIES = 30

# Concurrency cap for the SERP fan-out. DataForSEO live-regular handles
# parallel posts comfortably; 5 keeps us under any reasonable RPS limits.
SERP_CONCURRENCY = 5

# Inclusion-rate benchmark for emerging brands per the variable's rule 3.
INCLUSION_RATE_FLOOR_PCT = 5.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_record(
    *,
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    captured_at: datetime,
    status: CaptureStatus,
    value: dict[str, Any] | None,
    rules: list[RuleResult] | None,
    evidence_weight: EvidenceWeight,
    data_sources: list[str],
    cost_gbp: float = 0.0,
    errors: list[str] | None = None,
    subject_type: SubjectType = SubjectType.SITE,
    subject_id: str | None = None,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar="P6",
        captured_at=captured_at,
        taxonomy_version=getattr(ctx, "taxonomy_version", "unknown"),
        subject_type=subject_type,
        subject_id=subject_id or site.domain,
        status=status,
        value=value,
        rules=rules,
        evidence_weight=evidence_weight,
        data_sources_used=data_sources,
        cost_incurred_gbp=cost_gbp,
        errors=errors,
    )


def _domain_of(url: str) -> str:
    return (urlsplit(url).netloc or "").lower().removeprefix("www.")


# ─── SERP feature parsers ───────────────────────────────────────────────────


def _parse_ai_overview_block(item: dict) -> dict[str, Any] | None:
    """Pluck cited URLs + presence flag from an AI Overview SERP item.

    DataForSEO returns the AI Overview block as a single item with
    ``type == 'ai_overview'``. The ``items`` (or ``references`` in
    newer responses) array carries the cited sources.
    """
    if item.get("type") != "ai_overview":
        return None
    references = (
        item.get("references")
        or item.get("items")
        or []
    )
    cited_urls: list[str] = []
    for ref in references:
        if isinstance(ref, dict):
            url = ref.get("url") or ref.get("link") or ref.get("source")
            if isinstance(url, str):
                cited_urls.append(url)
    return {
        "present": True,
        "cited_url_count": len(cited_urls),
        "cited_urls": cited_urls,
    }


def _ai_overview_for(serp_response: dict) -> dict[str, Any] | None:
    """Walk a SERP response for an ai_overview block."""
    tasks = serp_response.get("tasks") or []
    for task in tasks:
        results = task.get("result") or []
        for result in results:
            for item in result.get("items") or []:
                parsed = _parse_ai_overview_block(item)
                if parsed:
                    return parsed
    return None


# ─── P6-25 — AI Overview inclusion frequency ────────────────────────────────


@register_extractor("P6-25")
async def capture_p6_25(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,
) -> CaptureRecord:
    """P6-25 — AI Overview inclusion frequency (Consensus, SERP-driven).

    For each keyword in the universe (auto-discovered from
    ``ranked_keywords`` until P0-13 lands), fetch a live SERP and
    check whether Google returned an AI Overview block. If yes, parse
    the cited sources and check whether any URL belongs to the
    audited domain.

    Hard-capped at ``MAX_SERP_QUERIES`` to bound cost. The cap is
    surfaced in the capture value so reviewers know whether the
    universe was sampled.
    """
    captured_at = _now()
    items = site.ranked_keywords
    if not items:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-25",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no keyword universe available; ranked_keywords empty",
                "method": "P0-13 curated list not yet implemented",
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["serp.google.organic"],
            errors=["site.ranked_keywords is empty"],
        )

    # Build the universe — distinct keyword strings, ordered by search volume desc.
    seen: set[str] = set()
    universe: list[str] = []
    for it in items:
        kw = ((it.get("keyword_data") or {}).get("keyword") or "").strip()
        if kw and kw not in seen:
            seen.add(kw)
            universe.append(kw)
    # Prefer the orchestrator's shared SERP prefetch — same dataset
    # used by P0-05 and P1-10, no duplicate API cost. Fall back to
    # live fetches only when prefetch is empty (e.g. legacy audits
    # where the orchestrator step didn't run).
    sampled: list[str]
    use_shared_prefetch = bool(site.serp_results)
    if use_shared_prefetch:
        sampled = list(site.serp_results.keys())
    else:
        sampled = universe[:MAX_SERP_QUERIES]

    domain = site.domain.lower().removeprefix("www.")
    results: list[dict[str, Any]] = []
    api_errors: list[str] = []

    def _process_serp_result(keyword: str, raw_result: dict | None, error: str | None = None) -> None:
        """Extract AI-Overview presence + brand citation from a single SERP result."""
        if error or raw_result is None:
            results.append({"keyword": keyword, "error": error or "no result"})
            return
        # Build a faux-resp shape that _ai_overview_for() expects, OR just
        # walk items directly. site.serp_results already stores the inner
        # result object (tasks[0].result[0]); _ai_overview_for() expects
        # the full response. Walk items directly.
        items = raw_result.get("items") or []
        ai_overview_block = None
        for it in items:
            if it.get("type") in ("ai_overview", "ai_mode"):
                ai_overview_block = it
                break
        if ai_overview_block is None:
            results.append({"keyword": keyword, "ai_overview_present": False})
            return
        # Extract cited URLs / domains from the AI Overview block
        refs = (
            ai_overview_block.get("references")
            or ai_overview_block.get("items")
            or ai_overview_block.get("links")
            or []
        )
        cited_urls: list[str] = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            url = ref.get("url") or ref.get("source_url") or ref.get("link") or ""
            if url:
                cited_urls.append(url)
        cited_domains = [_domain_of(u) for u in cited_urls]
        brand_cited = any(domain in d for d in cited_domains)
        brand_position: int | None = None
        for pos, d in enumerate(cited_domains, start=1):
            if domain in d:
                brand_position = pos
                break
        results.append(
            {
                "keyword": keyword,
                "ai_overview_present": True,
                "cited_url_count": len(cited_urls),
                "brand_cited": brand_cited,
                "brand_position": brand_position,
                "cited_domains_sample": cited_domains[:5],
            }
        )

    if use_shared_prefetch:
        for kw, result in site.serp_results.items():
            _process_serp_result(kw, result)
    else:
        sem = asyncio.Semaphore(SERP_CONCURRENCY)
        async def _one(keyword: str) -> None:
            async with sem:
                try:
                    resp = await dataforseo.serp_google_organic(
                        keyword, depth=10
                    )
                except Exception as exc:  # noqa: BLE001
                    api_errors.append(f"{keyword}: {type(exc).__name__}: {exc}")
                    _process_serp_result(keyword, None, error=str(exc))
                    return
            ai_overview = _ai_overview_for(resp)
            if ai_overview is None:
                results.append({"keyword": keyword, "ai_overview_present": False})
                return
            cited_domains = [_domain_of(u) for u in ai_overview["cited_urls"]]
            brand_cited = any(domain in d for d in cited_domains)
            brand_position: int | None = None
            for pos, d in enumerate(cited_domains, start=1):
                if domain in d:
                    brand_position = pos
                    break
            results.append(
                {
                    "keyword": keyword,
                    "ai_overview_present": True,
                    "cited_url_count": ai_overview["cited_url_count"],
                    "brand_cited": brand_cited,
                    "brand_position": brand_position,
                    "cited_domains_sample": cited_domains[:5],
                }
            )
        await asyncio.gather(*[_one(kw) for kw in sampled])

    queries_total = len(sampled)
    queries_with_ai_overview = sum(1 for r in results if r.get("ai_overview_present"))
    brand_citations = sum(1 for r in results if r.get("brand_cited"))
    inclusion_rate_pct = (
        (brand_citations / queries_with_ai_overview * 100.0)
        if queries_with_ai_overview else 0.0
    )
    top_3_citations = sum(
        1 for r in results
        if r.get("brand_cited") and r.get("brand_position") in (1, 2, 3)
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Target keyword universe defined (>= 1 keyword); using auto-discovered ranked-keywords",
        passed=queries_total >= 1,
        evidence={
            "universe_size": len(universe),
            "queries_run": queries_total,
            "max_serp_queries_cap": MAX_SERP_QUERIES,
            "method": "auto_discovered_from_ranked_keywords",
        },
        notes=(
            "Universe is the ranked-keywords list, capped at "
            f"{MAX_SERP_QUERIES}. P0-13 will replace this with a curated set."
        ),
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one queried keyword triggered an AI Overview block",
        passed=queries_with_ai_overview > 0,
        evidence={
            "queries_with_ai_overview": queries_with_ai_overview,
            "queries_total": queries_total,
            "ai_overview_trigger_pct": (
                round(queries_with_ai_overview / queries_total * 100, 1)
                if queries_total else 0
            ),
        },
        notes=(
            "AI Overview rollout is geo + topic dependent; absence "
            "isn't a brand failure but does cap the upside."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text=f"Inclusion rate >= {INCLUSION_RATE_FLOOR_PCT}% of AI-Overview-present queries",
        passed=(
            inclusion_rate_pct >= INCLUSION_RATE_FLOOR_PCT
            if queries_with_ai_overview else False
        ),
        evidence={
            "inclusion_rate_pct": round(inclusion_rate_pct, 1),
            "brand_citations": brand_citations,
            "ai_overview_query_count": queries_with_ai_overview,
            "floor_pct": INCLUSION_RATE_FLOOR_PCT,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Brand citations land in the top 3 cited sources where present",
        passed=top_3_citations == brand_citations if brand_citations else True,
        evidence={
            "top_3_citations": top_3_citations,
            "brand_citations": brand_citations,
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Citation context positivity (DEFERRED — needs LLM eval of cited sentence)",
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_evaluation"},
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="Inclusion stability over weeks (DEFERRED — needs longitudinal audit)",
        passed=True,
        evidence={"method": "deferred_to_longitudinal_audit_history"},
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-25",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "queries_run": queries_total,
            "universe_size": len(universe),
            "queries_with_ai_overview": queries_with_ai_overview,
            "brand_citations": brand_citations,
            "inclusion_rate_pct": round(inclusion_rate_pct, 1),
            "top_3_citations": top_3_citations,
            "max_serp_queries_cap": MAX_SERP_QUERIES,
            "universe_provenance": "auto_discovered_from_ranked_keywords",
            "per_query_results": results[:50],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "serp.google.organic",
            "composition.ai_overview_parse",
        ],
        errors=api_errors or None,
    )


# ─── P6-24 — Citation diversity in source URL pool ─────────────────────────


# Source-type taxonomy mapping. Patterns matched in lower-cased domain.
# Each domain is assigned to the FIRST matching type. Order matters —
# Wikipedia must precede the generic "wiki" pattern, etc.
_SOURCE_TYPE_PATTERNS = (
    ("wikipedia", ("wikipedia.org",)),
    ("government", (".gov", ".gov.uk", ".gov.au", ".mil")),
    ("academic", (".edu", ".ac.uk", ".ac.in", ".ac.jp")),
    ("forum", (
        "reddit.com", "quora.com", "stackexchange.com",
        "stackoverflow.com", "ycombinator.com", "discord.com",
    )),
    ("social", (
        "linkedin.com", "twitter.com", "x.com", "facebook.com",
        "instagram.com", "youtube.com", "tiktok.com", "threads.net",
    )),
    ("press_release", (
        "prnewswire", "prweb", "businesswire", "newswire",
        "pressrelease", "openpr", "einnews", "globenewswire",
        "accesswire", "issuewire", "marketwatch",
    )),
    ("news_media", (
        "bbc.", "nytimes.com", "wsj.com", "ft.com", "guardian.co",
        "theguardian.com", "telegraph.co.uk", "independent.co.uk",
        "reuters.com", "bloomberg.com", "cnn.com", "forbes.com",
        "techcrunch.com", "venturebeat.com", "wired.com",
        "theverge.com", "engadget.com", "arstechnica.com",
        "businessinsider.com", "techbullion.com",
    )),
    ("industry_publication", (
        "searchengineland.com", "searchenginejournal.com",
        "ahrefs.com", "semrush.com", "moz.com", "neilpatel.com",
        "hubspot.com", "marketingland.com", "growthhackers.com",
        "smashingmagazine.com", "css-tricks.com", "dev.to",
        "medium.com", "hackernoon.com",
    )),
    ("directory_review", (
        "clutch.co", "goodfirms.co", "designrush.com", "techreviewer.co",
        "vendry.io", "g2.com", "trustpilot.com", "capterra.com",
        "yelp.com", "yell.com",
    )),
)


def _classify_source_type(domain: str) -> str:
    """Map a referring domain to one of the source-type buckets.

    Returns 'other' for domains that don't match any pattern. This is
    a deliberately broad classifier: the goal is diversity-detection,
    not perfect categorisation.
    """
    if not domain:
        return "other"
    d = domain.lower().lstrip(".")
    if d.startswith("www."):
        d = d[4:]
    for type_name, patterns in _SOURCE_TYPE_PATTERNS:
        for pat in patterns:
            if pat in d:
                return type_name
    return "other"


@register_extractor("P6-24")
async def capture_p6_24(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P6-24 — Citation diversity in source URL pool (Probable).

    Whether the brand is referenced across a diverse pool of sources
    or concentrated on a small number / single type. LLM retrievers
    pull top-k candidate sources for a query and synthesise across
    them; a brand referenced consistently across multiple
    independent source-types is more likely to be cited in an
    AI Overview answer.

    Composition over data already prefetched: referring_domains
    (top-N sample) + backlinks_summary (profile-wide main_domains).

    Pass:
    - >= 50 distinct external referring main domains (profile-wide)
    - Source-type diversity: span >= 4 distinct named categories
    - No single referring domain > 15% of the sample's backlinks
    """
    from collections import Counter

    captured_at = _now()
    summary = site.backlinks_summary
    refs = site.referring_domains

    if not refs or summary is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-24",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no backlinks data available — citation-diversity "
                    "composition needs referring_domains + summary prefetch"
                ),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "backlinks.summary"],
            errors=["no backlinks data"],
        )

    total_main_domains = int(summary.get("referring_main_domains") or 0)
    sample_size = len(refs)

    type_counts: Counter[str] = Counter()
    type_examples: dict[str, list[dict[str, Any]]] = {}
    for r in refs:
        domain = r.get("domain") or ""
        stype = _classify_source_type(domain)
        type_counts[stype] += 1
        ex_list = type_examples.setdefault(stype, [])
        if len(ex_list) < 5:
            ex_list.append(
                {
                    "domain": domain,
                    "rank": r.get("rank"),
                    "backlinks": r.get("backlinks"),
                }
            )

    sorted_refs = sorted(
        refs,
        key=lambda r: int(r.get("backlinks") or 0),
        reverse=True,
    )
    top_domain = sorted_refs[0] if sorted_refs else None
    top_backlinks = int(top_domain.get("backlinks") or 0) if top_domain else 0
    total_backlinks = sum(int(r.get("backlinks") or 0) for r in refs)
    top_concentration_pct = (
        round(top_backlinks / total_backlinks * 100, 1)
        if total_backlinks
        else 0.0
    )

    distinct_types_with_signal = sum(
        1 for t, n in type_counts.items() if n >= 1 and t != "other"
    )
    types_with_meaningful_signal = [
        t for t, n in type_counts.items() if n >= 2 and t != "other"
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 50 distinct external referring main domains (profile-wide)",
        passed=total_main_domains >= 50,
        evidence={
            "total_main_domains": total_main_domains,
            "sample_inspected": sample_size,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Source-type diversity: >= 4 distinct named categories (excluding 'other')",
        passed=distinct_types_with_signal >= 4,
        evidence={
            "distinct_types_count": distinct_types_with_signal,
            "types_present": [
                t for t, n in type_counts.items() if n >= 1 and t != "other"
            ],
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Top single referring domain <= 15% of sample's backlinks (no concentration)",
        passed=top_concentration_pct <= 15.0,
        evidence={
            "top_domain": top_domain.get("domain") if top_domain else None,
            "top_concentration_pct": top_concentration_pct,
            "top_backlinks": top_backlinks,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-24",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_main_domains_profile_wide": total_main_domains,
            "sample_inspected": sample_size,
            "source_type_distribution": dict(type_counts),
            "distinct_types_count": distinct_types_with_signal,
            "types_with_meaningful_signal_ge_2": types_with_meaningful_signal,
            "top_concentration_pct": top_concentration_pct,
            "top_domain": top_domain.get("domain") if top_domain else None,
            "source_type_examples": type_examples,
            "note": (
                "Citation diversity is a GEO signal: LLM retrievers pull "
                "from multiple source types. Sources classified by "
                "pattern-matching against a curated taxonomy "
                "(wikipedia / government / academic / forum / social / "
                "press_release / news_media / industry_publication / "
                "directory_review / other). The 'other' bucket dominates "
                "for niche profiles; that's expected. The diversity rule "
                "asks whether the brand reaches >=4 of the named "
                "categories."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains", "backlinks.summary"],
    )
