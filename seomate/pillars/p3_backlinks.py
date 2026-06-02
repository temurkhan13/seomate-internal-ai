"""Pillar 3 — Off-Page Authority extractors.

Reads from the orchestrator's backlinks prefetch:
- ``site.backlinks_summary`` — aggregate metrics row from
  DataForSEO ``backlinks_summary`` endpoint
- ``site.referring_domains`` — top-N referring domain records from
  ``referring_domains`` endpoint
- ``site.backlinks_anchors`` — top-N anchor records from ``anchors``
  endpoint
- ``site.backlinks_timeseries`` — monthly snapshots over a 12-month
  window from ``timeseries_summary`` endpoint
- ``site.wikipedia_links`` — Wikipedia exturlusage hits for the
  target domain (P3-28)

Four DataForSEO calls + 1 Wikipedia call drive the whole pillar
(~£0.05 per audit total). Individual extractors don't make API
calls themselves except P3-28 which directly hits the Wikipedia API
via the injected adapter.

Variables operationalised in this module are added in batches; each
batch is verified against pixelettetech.com before more land.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import json as _json

from seomate.adapters import AdapterContext
from seomate.adapters.llm import LlmAdapter, LlmNotConfigured
from seomate.adapters.wikipedia import WikipediaAdapter
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor


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
    errors: list[str] | None = None,
    cost_gbp: float = 0.0,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar="P3",
        captured_at=captured_at,
        taxonomy_version=getattr(ctx, "taxonomy_version", "unknown"),
        subject_type=SubjectType.SITE,
        subject_id=site.domain,
        status=status,
        value=value,
        rules=rules,
        evidence_weight=evidence_weight,
        data_sources_used=data_sources,
        cost_incurred_gbp=cost_gbp,
        errors=errors,
    )


def _unmeasurable_no_summary(
    ctx: AdapterContext,
    site: SiteData,
    var_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
) -> CaptureRecord:
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=var_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "no backlinks_summary data — the DataForSEO Backlinks API "
                "trial/subscription may not be active, or the summary call "
                "failed. Check the audit log for `audit.backlinks_summary_failed`."
            ),
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["backlinks.summary"],
        errors=["no backlinks_summary"],
    )


# ─── P3-01 — Total referring root domains count ─────────────────────────────


@register_extractor("P3-01")
async def capture_p3_01(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-01 — Total referring root domains count (Consensus).

    DataForSEO's ``referring_main_domains`` is the unique-root-domain
    count. Distinct from ``referring_domains`` which includes
    subdomains.

    Pass: site has >= 50 referring main domains (Whitespark / Ahrefs
    baseline for an established brand; sites with <50 are typically
    new or have weak link profiles).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-01", EvidenceWeight.CONSENSUS, captured_at,
        )

    main_domains = int(summary.get("referring_main_domains") or 0)
    main_domains_nofollow = int(summary.get("referring_main_domains_nofollow") or 0)
    main_domains_dofollow = main_domains - main_domains_nofollow
    all_subs = int(summary.get("referring_domains") or 0)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 50 referring root domains (established brand baseline)",
        passed=main_domains >= 50,
        evidence={
            "referring_main_domains": main_domains,
            "referring_main_domains_dofollow": main_domains_dofollow,
            "referring_main_domains_nofollow": main_domains_nofollow,
            "referring_domains_incl_subdomains": all_subs,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "referring_main_domains": main_domains,
            "referring_main_domains_dofollow": main_domains_dofollow,
            "referring_main_domains_nofollow": main_domains_nofollow,
            "referring_domains_incl_subdomains": all_subs,
            "note": (
                "P3-01 counts root domains. The wider 'referring_domains' "
                "number includes subdomains and is generally larger by a "
                "modest factor on most sites."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.summary"],
    )


# ─── P3-04 — Number of linking pages ────────────────────────────────────────


@register_extractor("P3-04")
async def capture_p3_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-04 — Number of linking pages (Consensus).

    Distinct count of individual pages (URLs, not just domains) that
    link to the target site. A natural diversity check: a site with
    254 referring domains but only 250 linking pages has 1 link per
    domain on average (footer/sitewide pattern? Or just one link
    per page from each domain).

    Pass: linking pages >= 100 (rough baseline).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-04", EvidenceWeight.CONSENSUS, captured_at,
        )

    linking_pages = int(summary.get("referring_pages") or 0)
    linking_pages_nofollow = int(summary.get("referring_pages_nofollow") or 0)
    linking_pages_dofollow = linking_pages - linking_pages_nofollow
    main_domains = int(summary.get("referring_main_domains") or 0)
    avg_links_per_domain = (
        round(linking_pages / main_domains, 2) if main_domains else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 100 unique linking pages",
        passed=linking_pages >= 100,
        evidence={
            "linking_pages": linking_pages,
            "linking_pages_dofollow": linking_pages_dofollow,
            "linking_pages_nofollow": linking_pages_nofollow,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-04",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "linking_pages": linking_pages,
            "linking_pages_dofollow": linking_pages_dofollow,
            "linking_pages_nofollow": linking_pages_nofollow,
            "avg_links_per_referring_domain": avg_links_per_domain,
            "note": (
                "Avg links-per-referring-domain ratio gives a quick read on "
                "link-pattern diversity: a high ratio (>5 links/domain) "
                "suggests sitewide / footer placements; a ratio near 1 "
                "suggests organic contextual links."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.summary"],
    )


# ─── P3-17 — Dofollow vs nofollow ratio ─────────────────────────────────────


@register_extractor("P3-17")
async def capture_p3_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-17 — Dofollow vs nofollow ratio (Probable).

    Dofollow links pass PageRank-equivalent authority; nofollow links
    don't. A healthy backlink profile has a meaningful share of
    dofollow links (Backlinko cites >=50% dofollow share as the
    common heuristic), and an unnatural near-100%-dofollow pattern
    may indicate paid-link-building activity rather than organic
    growth.

    Pass: dofollow share between 40% and 95% (organic-looking band).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-17", EvidenceWeight.PROBABLE, captured_at,
        )

    total_pages = int(summary.get("referring_pages") or 0)
    nofollow_pages = int(summary.get("referring_pages_nofollow") or 0)
    if total_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-17",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring pages to compute ratio"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no referring pages"],
        )

    dofollow_pages = total_pages - nofollow_pages
    dofollow_pct = round(dofollow_pages / total_pages * 100, 1)
    nofollow_pct = round(nofollow_pages / total_pages * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Dofollow share between 40% and 95% (organic band)",
        passed=40 <= dofollow_pct <= 95,
        evidence={
            "dofollow_pct": dofollow_pct,
            "nofollow_pct": nofollow_pct,
            "dofollow_pages": dofollow_pages,
            "nofollow_pages": nofollow_pages,
            "total_referring_pages": total_pages,
        },
        notes=(
            "<40% dofollow indicates weak authority transfer; >95% dofollow "
            "may indicate manipulative link building (organic profiles "
            "almost always have some nofollow share from social, news, "
            "forum mentions, etc.)."
        ),
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "dofollow_pages": dofollow_pages,
            "nofollow_pages": nofollow_pages,
            "dofollow_pct": dofollow_pct,
            "nofollow_pct": nofollow_pct,
            "total_referring_pages": total_pages,
            "note": (
                "Ratio computed across referring pages, not unique domains. "
                "The dofollow/nofollow split is generally similar at page "
                "and domain levels but page-level captures repeat-linker "
                "effects."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-02 — Referring domain DR/DA distribution ───────────────────────────


# DataForSEO's `rank` field on referring_domains is their proprietary
# DR-equivalent on a 0-1000 scale. Bucket thresholds informed by
# practitioner-observed Ahrefs DR equivalences.
_DR_BUCKETS = (
    ("very_high", 800),   # DR ~70+ — major publications, large authorities
    ("high", 600),         # DR ~50-70 — established sites
    ("medium", 350),       # DR ~30-50 — mid-tier sites
    ("low", 150),          # DR ~10-30 — small / niche
    ("very_low", 0),       # DR <10 — unranked / spammy / new
)


def _bucket_rank(rank: int | float | None) -> str:
    if rank is None:
        return "unknown"
    r = float(rank)
    for label, floor in _DR_BUCKETS:
        if r >= floor:
            return label
    return "very_low"


@register_extractor("P3-02")
async def capture_p3_02(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-02 — Referring domain DR/DA distribution (Probable).

    Buckets the top-N referring domains (DataForSEO returns 100 by
    default in our prefetch) by their `rank` score. A healthy profile
    has a long tail (most domains low DR) plus a credible top end
    (some high-DR domains anchoring authority transfer).

    Pass: at least 5 referring domains with rank >= 600 (high-tier)
    AND the bottom 'very_low' bucket isn't >70% of the sample (would
    suggest a profile dominated by low-quality sites).
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-02",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains"],
            errors=["no referring_domains"],
        )

    buckets: dict[str, int] = {
        "very_high": 0, "high": 0, "medium": 0,
        "low": 0, "very_low": 0, "unknown": 0,
    }
    ranks: list[float] = []
    high_tier_examples: list[dict[str, Any]] = []
    for r in refs:
        rank = r.get("rank")
        if rank is not None:
            try:
                ranks.append(float(rank))
            except (TypeError, ValueError):
                pass
        bucket = _bucket_rank(rank)
        buckets[bucket] += 1
        if bucket in ("very_high", "high") and len(high_tier_examples) < 10:
            high_tier_examples.append(
                {
                    "domain": r.get("domain"),
                    "rank": rank,
                    "backlinks": r.get("backlinks"),
                }
            )

    total = len(refs)
    high_count = buckets["very_high"] + buckets["high"]
    very_low_pct = round(buckets["very_low"] / total * 100, 1) if total else 0
    median_rank = (
        round(sorted(ranks)[len(ranks) // 2], 1) if ranks else None
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 5 referring domains with rank >= 600 (high-authority tier)",
        passed=high_count >= 5,
        evidence={
            "high_tier_count": high_count,
            "very_high_count": buckets["very_high"],
            "high_count": buckets["high"],
            "high_tier_examples": high_tier_examples,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 70% of referring domains in the 'very_low' rank bucket (avoid spammy-domain-dominated profile)",
        passed=very_low_pct <= 70,
        evidence={
            "very_low_count": buckets["very_low"],
            "very_low_pct": very_low_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-02",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "referring_domains_sampled": total,
            "bucket_counts": buckets,
            "median_rank": median_rank,
            "high_tier_count": high_count,
            "high_tier_examples": high_tier_examples,
            "note": (
                "DataForSEO `rank` is their proprietary DR-equivalent on a "
                "0-1000 scale. Rank >= 600 maps roughly to Ahrefs DR >= 50; "
                ">= 800 to Ahrefs DR >= 70."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains"],
    )


# ─── P3-22 — Linking domain country TLD ────────────────────────────────────


@register_extractor("P3-22")
async def capture_p3_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-22 — Linking domain country TLD (Probable).

    For brands targeting a specific market, ccTLD distribution among
    backlinks signals geographic relevance. A UK-targeted brand
    benefits from a meaningful share of .co.uk / .uk backlinks
    alongside the global .com pool.

    Reports the full TLD distribution from backlinks_summary and
    surfaces local-TLD share for the brand's primary market (inferred
    from GBP country when available; default UK for the pilot).

    Pass: top TLD is .com OR a local relevant TLD (.co.uk, .uk for
    UK brand) — i.e., distribution looks geographically coherent.
    Heavy presence of unrelated ccTLDs (.cn, .ru) without operational
    relevance is a soft warning sign.
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-22", EvidenceWeight.PROBABLE, captured_at,
        )

    tld_dist = summary.get("referring_links_tld") or {}
    if not isinstance(tld_dist, dict) or not tld_dist:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-22",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_links_tld breakdown in summary"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["empty tld breakdown"],
        )

    total_in_tld = sum(int(v or 0) for v in tld_dist.values())
    sorted_tlds = sorted(tld_dist.items(), key=lambda kv: kv[1], reverse=True)
    top_tld, top_tld_count = sorted_tlds[0]
    top_tld_pct = round(top_tld_count / total_in_tld * 100, 1) if total_in_tld else 0

    # Local-TLD share for the brand's primary market
    # GBP country code in gbp_info -> our.local TLD set
    gbp_country = ""
    if site.gbp_info:
        addr_info = site.gbp_info.get("address_info") or {}
        gbp_country = (addr_info.get("country_code") or "").upper()
    local_tld_map = {
        "GB": ("co.uk", "uk"),
        "US": ("us",),  # .us is rarely used; .com dominates
        "CA": ("ca",),
        "AU": ("com.au", "au"),
        "DE": ("de",),
        "FR": ("fr",),
    }
    local_tlds = local_tld_map.get(gbp_country, ())
    local_count = sum(int(tld_dist.get(t, 0)) for t in local_tlds)
    local_pct = round(local_count / total_in_tld * 100, 1) if total_in_tld else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Top TLD is .com or a market-relevant TLD",
        passed=top_tld == "com" or top_tld in local_tlds,
        evidence={
            "top_tld": top_tld,
            "top_tld_count": top_tld_count,
            "top_tld_pct": top_tld_pct,
            "local_tlds_for_market": list(local_tlds),
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-22",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "tld_distribution": dict(sorted_tlds[:15]),
            "top_tld": top_tld,
            "top_tld_pct": top_tld_pct,
            "local_tld_share_pct": local_pct,
            "local_tlds_for_market": list(local_tlds),
            "primary_market_country_from_gbp": gbp_country or None,
            "note": (
                "Inferred primary market from GBP country code. Local-TLD "
                "share is a soft signal — many B2B brands legitimately have "
                "global .com-dominated profiles."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-23 — C-class IP diversity of links ─────────────────────────────────


@register_extractor("P3-23")
async def capture_p3_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-23 — C-class IP diversity of backlinks (Probable).

    A natural backlink profile has its links coming from a wide spread
    of IP subnets (C-class). When many backlinks come from the same
    subnet, that's a signal of PBN (Private Blog Network) /
    link-farm activity — Google's Penguin update penalises this
    pattern.

    DataForSEO's summary provides:
    - ``referring_ips`` — distinct IP addresses linking
    - ``referring_subnets`` — distinct C-class subnets

    Diversity ratio: subnets / pages. Higher = more diverse.
    1.0 = each linking page on its own subnet (very natural).
    0.1 = 10 linking pages per subnet (suspicious).

    Pass: subnet_to_domain_ratio >= 0.6 AND ip_to_subnet_ratio between
    1.0-2.5 (each subnet has 1-2.5 IPs, organic-looking).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-23", EvidenceWeight.PROBABLE, captured_at,
        )

    referring_ips = int(summary.get("referring_ips") or 0)
    referring_subnets = int(summary.get("referring_subnets") or 0)
    referring_domains = int(summary.get("referring_main_domains") or 0)

    if referring_domains == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-23",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring domains to compute IP diversity"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no referring domains"],
        )

    subnet_to_domain_ratio = round(referring_subnets / referring_domains, 3)
    ip_to_subnet_ratio = (
        round(referring_ips / referring_subnets, 3) if referring_subnets else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Subnet-to-domain ratio >= 0.6 (most referring domains on distinct subnets)",
        passed=subnet_to_domain_ratio >= 0.6,
        evidence={
            "referring_subnets": referring_subnets,
            "referring_domains": referring_domains,
            "subnet_to_domain_ratio": subnet_to_domain_ratio,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="IP-to-subnet ratio between 1.0 and 2.5 (organic-looking; tight bands suggest PBN)",
        passed=1.0 <= ip_to_subnet_ratio <= 2.5,
        evidence={
            "referring_ips": referring_ips,
            "referring_subnets": referring_subnets,
            "ip_to_subnet_ratio": ip_to_subnet_ratio,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "referring_ips": referring_ips,
            "referring_subnets": referring_subnets,
            "referring_domains": referring_domains,
            "subnet_to_domain_ratio": subnet_to_domain_ratio,
            "ip_to_subnet_ratio": ip_to_subnet_ratio,
            "note": (
                "C-class IP diversity is one of the strongest organic-vs-"
                "manipulated profile signals. PBN patterns concentrate "
                "backlinks on a small number of subnets; organic profiles "
                "spread across hundreds."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-12 — Anchor text distribution ──────────────────────────────────────


_GENERIC_ANCHOR_PHRASES = (
    "click here", "click this", "read more", "read this", "see more",
    "see this", "visit website", "visit site", "visit our website",
    "company website", "official website", "official site",
    "home", "homepage", "here", "this", "this article", "this site",
    "this website", "this link", "link", "the website", "the site",
    "go here", "find out more", "learn more", "more info", "more",
    "website", "website link", "site",
)


_URL_LIKE_RE = None  # initialised lazily


def _classify_anchor(anchor: str | None, brand_variants: tuple[str, ...]) -> str:
    """Classify an anchor as branded / naked_url / generic / exact_match / other."""
    if anchor is None or not anchor.strip():
        return "empty"
    a = anchor.strip().lower()

    # Naked URL — looks like a domain or full URL
    global _URL_LIKE_RE
    if _URL_LIKE_RE is None:
        import re
        _URL_LIKE_RE = re.compile(
            r"^(https?://)?[a-z0-9\-]+(\.[a-z0-9\-]+)+(/.*)?$"
        )
    if _URL_LIKE_RE.match(a):
        return "naked_url"

    # Generic phrases
    if a in _GENERIC_ANCHOR_PHRASES:
        return "generic"
    for phrase in _GENERIC_ANCHOR_PHRASES:
        if phrase in a and len(a) < len(phrase) + 8:
            return "generic"

    # Branded — contains any brand variant
    for variant in brand_variants:
        if variant and variant.lower() in a:
            return "branded"

    # Else — likely exact-match keyword / descriptive
    return "exact_match_or_descriptive"


@register_extractor("P3-12")
async def capture_p3_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-12 — Anchor text distribution (Consensus).

    Categorises the top-N anchor texts pointing at the site into:
    - **branded** (contains brand name) — best signal
    - **naked_url** (literal URL or domain as anchor) — neutral
    - **generic** ("click here", "visit site", "read more") — low value
    - **exact_match_or_descriptive** — keyword anchors; high
      concentration can trigger over-optimisation penalties
    - **empty** — no anchor text (e.g. image links)

    Pass: branded share >= 25% AND exact-match share <= 60% (avoids
    over-optimised profile that Google's Penguin demotes).
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-12",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no anchor data — backlinks_anchors call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["backlinks.anchors"],
            errors=["no anchors"],
        )

    brand_variants: tuple[str, ...] = ()
    if site.brand:
        brand_variants = site.brand.all_variants

    bucket_counts: dict[str, int] = {
        "branded": 0,
        "naked_url": 0,
        "generic": 0,
        "exact_match_or_descriptive": 0,
        "empty": 0,
    }
    bucket_backlinks: dict[str, int] = dict(bucket_counts)
    examples: dict[str, list[str]] = {k: [] for k in bucket_counts}

    for a in anchors:
        anchor_text = a.get("anchor")
        backlinks_count = int(a.get("backlinks") or 0)
        cls = _classify_anchor(anchor_text, brand_variants)
        bucket_counts[cls] += 1
        bucket_backlinks[cls] += backlinks_count
        if len(examples[cls]) < 3 and anchor_text:
            examples[cls].append(f"{anchor_text!r} ({backlinks_count} backlinks)")

    total_backlinks_in_sample = sum(bucket_backlinks.values())
    pct_by_backlinks = {
        k: round(v / total_backlinks_in_sample * 100, 1) if total_backlinks_in_sample else 0
        for k, v in bucket_backlinks.items()
    }

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Branded anchor share >= 25% of total backlinks in sample",
        passed=pct_by_backlinks.get("branded", 0) >= 25,
        evidence={
            "branded_count": bucket_counts["branded"],
            "branded_backlinks": bucket_backlinks["branded"],
            "branded_pct_of_backlinks": pct_by_backlinks.get("branded", 0),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Exact-match / descriptive anchors <= 60% of backlinks (avoid over-optimisation)",
        passed=pct_by_backlinks.get("exact_match_or_descriptive", 0) <= 60,
        evidence={
            "exact_match_count": bucket_counts["exact_match_or_descriptive"],
            "exact_match_backlinks": bucket_backlinks["exact_match_or_descriptive"],
            "exact_match_pct_of_backlinks": pct_by_backlinks.get(
                "exact_match_or_descriptive", 0
            ),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-12",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "anchors_sampled": len(anchors),
            "total_backlinks_in_sample": total_backlinks_in_sample,
            "bucket_counts": bucket_counts,
            "bucket_backlinks": bucket_backlinks,
            "pct_of_backlinks_by_bucket": pct_by_backlinks,
            "examples_by_bucket": examples,
            "note": (
                "Classification: branded if anchor contains any brand variant; "
                "naked_url if anchor literally is a URL; generic for fixed "
                "phrases ('click here', 'visit site', etc.); empty when anchor "
                "is null (typical of image-link rows). Backlinks-weighted "
                "percentages are the operational signal — counts can be "
                "misleading because top anchors carry many links."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.anchors"],
    )


# ─── P3-18 — Sponsored / UGC link tags ─────────────────────────────────────


@register_extractor("P3-18")
async def capture_p3_18(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-18 — Sponsored / UGC link tags (Consensus).

    Backlinks pointing at the target that carry ``rel="sponsored"`` or
    ``rel="ugc"`` attributes — Google's two qualifier tags that mark
    paid placements and user-generated link contexts. The summary's
    ``referring_links_attributes`` aggregates these.

    Healthy profile: a modest share of sponsored/UGC links is normal
    (forum signatures, sponsored posts disclosed correctly). An
    absence is fine. A LARGE share of sponsored is a paid-link-
    building footprint.

    Pass: sponsored share <= 15% AND ugc share <= 15% (each).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-18", EvidenceWeight.CONSENSUS, captured_at,
        )

    attrs = summary.get("referring_links_attributes") or {}
    if not isinstance(attrs, dict):
        attrs = {}
    total_pages = int(summary.get("referring_pages") or 0)
    sponsored = int(attrs.get("sponsored") or 0)
    ugc = int(attrs.get("ugc") or 0)
    nofollow = int(attrs.get("nofollow") or 0)
    noopener = int(attrs.get("noopener") or 0)
    noreferrer = int(attrs.get("noreferrer") or 0)
    external = int(attrs.get("external") or 0)

    if total_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring pages to compute attribute share"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["backlinks.summary"],
            errors=["no referring pages"],
        )

    sponsored_pct = round(sponsored / total_pages * 100, 1)
    ugc_pct = round(ugc / total_pages * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Sponsored-link share <= 15% of referring pages (avoid paid-link footprint)",
        passed=sponsored_pct <= 15,
        evidence={
            "sponsored_count": sponsored,
            "sponsored_pct": sponsored_pct,
            "total_referring_pages": total_pages,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="UGC-link share <= 15% of referring pages",
        passed=ugc_pct <= 15,
        evidence={
            "ugc_count": ugc,
            "ugc_pct": ugc_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-18",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_referring_pages": total_pages,
            "rel_attribute_counts": {
                "sponsored": sponsored,
                "ugc": ugc,
                "nofollow": nofollow,
                "noopener": noopener,
                "noreferrer": noreferrer,
                "external": external,
            },
            "sponsored_pct": sponsored_pct,
            "ugc_pct": ugc_pct,
            "note": (
                "rel='sponsored' marks paid/affiliate links; rel='ugc' marks "
                "user-generated comments/forum links. Both are legitimate "
                "tags Google introduced in 2019; their absence isn't "
                "necessarily a problem (legitimate organic links don't need "
                "them), but heavy presence of 'sponsored' indicates a paid-"
                "link-building footprint."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.summary"],
    )


# ─── P3-19 — Contextual links (in-content vs sidebar/footer) ───────────────


@register_extractor("P3-19")
async def capture_p3_19(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-19 — Contextual links / in-content placement (Probable).

    Links placed inside the main content area (``<article>``,
    ``<section>``, ``<main>``) carry more authority than links
    relegated to sidebar / footer / nav (``<aside>``, ``<nav>``,
    ``<footer>``). DataForSEO's ``referring_links_semantic_locations``
    aggregates the HTML5 semantic element each backlink sits inside.

    Pass: in-content share (article + section + main + figure) >= 60%
    of backlinks. Sites with most backlinks in nav/aside/footer have
    boilerplate-style links that pass less authority.
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-19", EvidenceWeight.PROBABLE, captured_at,
        )

    locations = summary.get("referring_links_semantic_locations") or {}
    if not isinstance(locations, dict) or not locations:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no semantic_locations breakdown in summary"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no semantic locations"],
        )

    total = sum(int(v or 0) for v in locations.values())
    in_content_tags = ("article", "section", "main", "figure")
    boilerplate_tags = ("nav", "aside", "footer", "header")

    in_content = sum(int(locations.get(t, 0)) for t in in_content_tags)
    boilerplate = sum(int(locations.get(t, 0)) for t in boilerplate_tags)
    other = total - in_content - boilerplate
    in_content_pct = round(in_content / total * 100, 1) if total else 0
    boilerplate_pct = round(boilerplate / total * 100, 1) if total else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 60% of backlinks placed in main-content semantic elements (article/section/main/figure)",
        passed=in_content_pct >= 60,
        evidence={
            "in_content_count": in_content,
            "in_content_pct": in_content_pct,
            "total_links_with_location": total,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 30% of backlinks in nav / aside / footer / header (boilerplate)",
        passed=boilerplate_pct <= 30,
        evidence={
            "boilerplate_count": boilerplate,
            "boilerplate_pct": boilerplate_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-19",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_links_with_location": total,
            "location_distribution": dict(
                sorted(locations.items(), key=lambda kv: kv[1], reverse=True)
            ),
            "in_content_count": in_content,
            "in_content_pct": in_content_pct,
            "boilerplate_count": boilerplate,
            "boilerplate_pct": boilerplate_pct,
            "other_count": other,
            "note": (
                "Semantic-element classification is reliable when the linking "
                "page uses HTML5 sectioning correctly. Sites that wrap "
                "everything in generic <div>s show up as 'unknown' "
                "(empty-string key in the location distribution)."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-03 — Linking domain age distribution ───────────────────────────────


def _parse_iso_or_dfs(ts: str | None) -> datetime | None:
    """Parse DataForSEO timestamps.

    Accepts:
    - ISO 8601 with Z suffix ("2021-04-12T08:30:00Z")
    - DataForSEO format ("2021-04-12 08:30:00 +00:00")
    - Plain date ("2021-04-12")
    """
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    # ISO with Z
    if s.endswith("Z"):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    # DataForSEO "YYYY-MM-DD HH:MM:SS +00:00"
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        pass
    # ISO without Z
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    # Plain date
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@register_extractor("P3-03")
async def capture_p3_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-03 — Linking domain age distribution (Probable).

    A mature backlink profile shows links accumulated over years, not
    months. A sudden spike of newly-discovered referring domains is
    one of the strongest indicators of paid-link / link-scheme
    behaviour (Penguin's algorithmic target).

    Uses ``first_seen`` from the top-N referring domains. Pass:
    - Median first-seen age >= 365 days (most refs older than 1y)
    - <= 30% of refs first seen in the last 90 days (no recent spike)
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-03",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains"],
            errors=["no referring_domains"],
        )

    now = captured_at
    ages_days: list[int] = []
    no_first_seen = 0
    for r in refs:
        first_seen = _parse_iso_or_dfs(r.get("first_seen"))
        if first_seen is None:
            no_first_seen += 1
            continue
        age = (now - first_seen).days
        if age < 0:
            age = 0
        ages_days.append(age)

    if not ages_days:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-03",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no parseable first_seen timestamps on sampled domains"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains"],
            errors=["no parseable first_seen"],
        )

    ages_sorted = sorted(ages_days)
    n = len(ages_sorted)
    median_age = ages_sorted[n // 2] if n % 2 else (
        (ages_sorted[n // 2 - 1] + ages_sorted[n // 2]) // 2
    )
    oldest_age = ages_sorted[-1]
    newest_age = ages_sorted[0]

    last_30 = sum(1 for a in ages_days if a <= 30)
    last_90 = sum(1 for a in ages_days if a <= 90)
    last_365 = sum(1 for a in ages_days if a <= 365)
    over_365 = sum(1 for a in ages_days if a > 365)
    over_730 = sum(1 for a in ages_days if a > 730)

    recent_90_pct = round(last_90 / n * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Median referring-domain first-seen age >= 365 days (mature profile)",
        passed=median_age >= 365,
        evidence={
            "median_age_days": median_age,
            "sample_size": n,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 30% of referring domains first seen in the last 90 days (no acquisition spike)",
        passed=recent_90_pct <= 30,
        evidence={
            "last_90d_count": last_90,
            "last_90d_pct": recent_90_pct,
            "sample_size": n,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-03",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "sample_size": n,
            "no_first_seen": no_first_seen,
            "median_age_days": median_age,
            "oldest_age_days": oldest_age,
            "newest_age_days": newest_age,
            "buckets": {
                "last_30_days": last_30,
                "last_90_days": last_90,
                "last_365_days": last_365,
                "over_1_year": over_365,
                "over_2_years": over_730,
            },
            "recent_90_pct": recent_90_pct,
            "note": (
                "Age computed from DataForSEO's first_seen timestamp on "
                "each referring domain. A sudden cluster of recent dates "
                "is one of the strongest paid-link signals; gradual "
                "accumulation over years looks organic."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains"],
    )


# ─── P3-29 — Toxic backlink presence ───────────────────────────────────────


@register_extractor("P3-29")
async def capture_p3_29(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-29 — Toxic backlink presence (Probable).

    DataForSEO provides a ``backlinks_spam_score`` (0-100, higher =
    more toxic) at both profile-level (summary) and per-domain
    (referring_domains rows). High spam scores correlate with
    PBNs, hacked sites, scraper aggregators, comment-link farms.

    Pass:
    - Overall profile ``backlinks_spam_score`` < 30
    - <= 10% of sampled referring domains have per-domain spam >= 60
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-29", EvidenceWeight.PROBABLE, captured_at,
        )

    profile_spam = summary.get("backlinks_spam_score")
    try:
        profile_spam_int = int(profile_spam) if profile_spam is not None else None
    except (TypeError, ValueError):
        profile_spam_int = None

    refs = site.referring_domains or []
    per_domain_scores: list[int] = []
    toxic_examples: list[dict[str, Any]] = []
    for r in refs:
        score = r.get("backlinks_spam_score")
        try:
            score_int = int(score) if score is not None else None
        except (TypeError, ValueError):
            score_int = None
        if score_int is None:
            continue
        per_domain_scores.append(score_int)
        if score_int >= 60 and len(toxic_examples) < 15:
            toxic_examples.append(
                {
                    "domain": r.get("domain"),
                    "spam_score": score_int,
                    "backlinks": r.get("backlinks"),
                    "rank": r.get("rank"),
                }
            )

    n_scored = len(per_domain_scores)
    toxic_count = sum(1 for s in per_domain_scores if s >= 60)
    moderate_count = sum(1 for s in per_domain_scores if 30 <= s < 60)
    clean_count = sum(1 for s in per_domain_scores if s < 30)
    toxic_pct = round(toxic_count / n_scored * 100, 1) if n_scored else 0.0

    if profile_spam_int is None and n_scored == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-29",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no spam_score data in summary or referring_domains"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary", "backlinks.referring_domains"],
            errors=["no spam_score"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Profile-level backlinks_spam_score < 30 (low overall toxicity)",
        passed=(profile_spam_int is not None and profile_spam_int < 30),
        evidence={"profile_spam_score": profile_spam_int},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 10% of sampled referring domains with spam_score >= 60",
        passed=(n_scored > 0 and toxic_pct <= 10.0),
        evidence={
            "toxic_count": toxic_count,
            "toxic_pct": toxic_pct,
            "sample_size": n_scored,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-29",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "profile_spam_score": profile_spam_int,
            "sample_size": n_scored,
            "toxic_count_per_domain_ge_60": toxic_count,
            "toxic_pct": toxic_pct,
            "distribution": {
                "clean_lt_30": clean_count,
                "moderate_30_to_59": moderate_count,
                "toxic_ge_60": toxic_count,
            },
            "toxic_examples": toxic_examples,
            "note": (
                "DataForSEO's spam_score is a 0-100 composite based on "
                "their proprietary signals. Persistent presence of "
                "ge-60 domains is candidate for Google Disavow review."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary", "backlinks.referring_domains"],
    )


# ─── P3-33 — Forum / community link presence ───────────────────────────────


@register_extractor("P3-33")
async def capture_p3_33(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-33 — Forum / community link presence (Probable).

    DataForSEO classifies referring page platforms; ``message-boards``
    covers vBulletin, phpBB, Discourse, Reddit-likes, Stack-Exchange
    style forums. Organic forum mentions are healthy community
    signals; an outsized share is often forum-spam profile-bio links
    (a long-standing low-quality link tactic).

    Pass:
    - At least 1 message-board referring link (community presence)
    - <= 25% of profile is message-boards (not dominated by them)
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-33", EvidenceWeight.PROBABLE, captured_at,
        )

    platform_types = summary.get("referring_links_platform_types") or {}
    if not isinstance(platform_types, dict) or not platform_types:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-33",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no platform_types breakdown in summary"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no platform_types"],
        )

    total = sum(int(v or 0) for v in platform_types.values())
    forum_count = int(platform_types.get("message-boards", 0) or 0)
    forum_pct = round(forum_count / total * 100, 1) if total else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 message-board referring link (organic community presence)",
        passed=forum_count >= 1,
        evidence={"forum_count": forum_count},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 25% of profile is message-boards (not dominated by forum-spam)",
        passed=forum_pct <= 25.0,
        evidence={"forum_pct": forum_pct, "total_classified_links": total},
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-33",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "forum_count": forum_count,
            "forum_pct": forum_pct,
            "total_classified_links": total,
            "platform_distribution": dict(
                sorted(platform_types.items(), key=lambda kv: kv[1], reverse=True)
            ),
            "note": (
                "Healthy forum signals come from topical communities "
                "discussing the brand; a near-100% message-boards "
                "share usually means forum profile-link spam."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-05 — Total backlinks ───────────────────────────────────────────────


@register_extractor("P3-05")
async def capture_p3_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-05 — Total backlinks count (Consensus).

    Raw count of inbound links across all referring pages. Distinct
    from P3-01 (root domains) and P3-04 (linking pages) — multiple
    backlinks can come from a single page (image link + anchor link
    on same article both count).

    Pass: site has >= 500 total backlinks. Practitioner heuristic for
    an established brand; sites with sparse backlinks rarely rank
    competitively even with strong on-page.
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-05", EvidenceWeight.CONSENSUS, captured_at,
        )

    total_backlinks = int(summary.get("backlinks") or 0)
    referring_pages = int(summary.get("referring_pages") or 0)
    backlinks_per_page = (
        round(total_backlinks / referring_pages, 2) if referring_pages else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has >= 500 total backlinks (established profile baseline)",
        passed=total_backlinks >= 500,
        evidence={"total_backlinks": total_backlinks},
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_backlinks": total_backlinks,
            "referring_pages": referring_pages,
            "backlinks_per_referring_page": backlinks_per_page,
            "note": (
                "Total backlinks counts every inbound link occurrence. "
                "A high backlinks-per-page ratio (>2) indicates repeat "
                "linking from the same pages, which is common for "
                "in-content brand mentions plus a footer logo link."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.summary"],
    )


# ─── P3-06 — Backlinks from .edu / .gov domains ────────────────────────────


_AUTHORITATIVE_TLDS = ("edu", "gov", "ac", "mil")


@register_extractor("P3-06")
async def capture_p3_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-06 — Backlinks from .edu/.gov/.ac/.mil domains (Contested).

    Historically practitioners overweight .edu/.gov as authority
    signals; modern consensus is that they only matter to the extent
    they're topically relevant. Still, presence is a positive
    long-tail signal — these TLDs are gated and rarely link spam.

    DataForSEO's ``referring_links_tld`` is the count of LINKS by TLD,
    not domains. We surface raw counts so SEO exec can verify whether
    these are organic citations or footer link aggregators.

    Pass: at least 1 backlink from an authoritative TLD.
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-06", EvidenceWeight.CONTESTED, captured_at,
        )

    tld_counts = summary.get("referring_links_tld") or {}
    if not isinstance(tld_counts, dict):
        tld_counts = {}

    # Match exact TLD AND TLDs ending with the authoritative suffix
    # (e.g., "ac.uk" matches "ac"; "edu.au" matches "edu")
    matches: dict[str, int] = {}
    for tld, count in tld_counts.items():
        if not isinstance(tld, str):
            continue
        parts = tld.lower().split(".")
        if any(p in _AUTHORITATIVE_TLDS for p in parts):
            try:
                matches[tld] = int(count or 0)
            except (TypeError, ValueError):
                continue

    authoritative_total = sum(matches.values())
    total_classified = sum(int(v or 0) for v in tld_counts.values())
    authoritative_pct = (
        round(authoritative_total / total_classified * 100, 2)
        if total_classified
        else 0.0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 backlink from .edu / .gov / .ac / .mil (gated TLDs)",
        passed=authoritative_total >= 1,
        evidence={
            "authoritative_total": authoritative_total,
            "matching_tlds": matches,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-06",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "authoritative_total": authoritative_total,
            "authoritative_pct_of_classified": authoritative_pct,
            "matching_tlds": matches,
            "total_classified_links": total_classified,
            "note": (
                "Counts are at the LINK level, not domain. A handful of "
                ".edu / .gov links from topically-relevant sources "
                "(university research citations, gov agency lists) is "
                "high-quality; footer-link aggregators don't count for "
                "much."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=["backlinks.summary"],
    )


# ─── P3-26 — Backlink age ──────────────────────────────────────────────────


@register_extractor("P3-26")
async def capture_p3_26(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-26 — Backlink age / earliest discovery (Probable).

    DataForSEO's ``first_seen`` at the SUMMARY level is the earliest
    backlink they've ever crawled for this target — a proxy for how
    long the site has been in the link graph.

    Distinct from P3-03 (linking domain age distribution across the
    top-100 sample) — this is the single oldest known inbound link.

    Pass: earliest backlink >= 2 years old (link graph evidence of an
    established presence, not a freshly-launched domain).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-26", EvidenceWeight.PROBABLE, captured_at,
        )

    first_seen_str = summary.get("first_seen")
    first_seen_dt = _parse_iso_or_dfs(first_seen_str)

    if first_seen_dt is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-26",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no first_seen timestamp in summary (site likely has no backlinks crawled)",
                "first_seen_raw": first_seen_str,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no first_seen"],
        )

    age_days = (captured_at - first_seen_dt).days
    age_years = round(age_days / 365.25, 2)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Earliest backlink first seen >= 730 days ago (2+ years in link graph)",
        passed=age_days >= 730,
        evidence={
            "age_days": age_days,
            "age_years": age_years,
            "first_seen": first_seen_str,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-26",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "first_seen": first_seen_str,
            "age_days": age_days,
            "age_years": age_years,
            "note": (
                "first_seen is the earliest DataForSEO crawled a link to "
                "this target. It's bounded by their crawl history (rolling "
                "~5y window), so very old sites may show first_seen capped "
                "at the window edge. Combine with domain WHOIS age for "
                "a full picture."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-32 — Brand mention frequency (linked) ──────────────────────────────


@register_extractor("P3-32")
async def capture_p3_32(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-32 — Brand mention frequency (linked + unlinked) (Probable).

    The full variable measures BOTH linked brand mentions (anchor
    contains brand) and unlinked mentions (brand name appearing in
    referring-page body text without a hyperlink). Unlinked-mention
    detection requires either a web-mention API or fetching every
    referring page's HTML — not available in our backlinks prefetch.

    What we CAN measure: the LINKED portion, by counting anchor text
    occurrences that contain a brand variant and aggregating the
    backlinks-count behind those anchors.

    Pass: linked brand mentions account for >= 20% of total backlinks
    across the sampled top-N anchors (organic profile dominated by
    brand-name references, not over-optimised keyword anchors).
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-32",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no backlinks_anchors data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no anchors"],
        )

    brand_variants: tuple[str, ...] = ()
    if site.brand:
        brand_variants = site.brand.all_variants
    if not brand_variants:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-32",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand variants configured — cannot classify branded anchors"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no brand variants"],
        )

    branded_backlinks = 0
    other_backlinks = 0
    branded_anchor_examples: list[dict[str, Any]] = []
    for a in anchors:
        anchor_text = a.get("anchor")
        backlinks_count = int(a.get("backlinks") or 0)
        cls = _classify_anchor(anchor_text, brand_variants)
        if cls == "branded":
            branded_backlinks += backlinks_count
            if len(branded_anchor_examples) < 10:
                branded_anchor_examples.append(
                    {"anchor": anchor_text, "backlinks": backlinks_count}
                )
        else:
            other_backlinks += backlinks_count

    total_sampled = branded_backlinks + other_backlinks
    branded_pct = (
        round(branded_backlinks / total_sampled * 100, 1)
        if total_sampled
        else 0.0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 20% of sampled backlinks use branded anchors (healthy linked-mention share)",
        passed=branded_pct >= 20.0,
        evidence={
            "branded_backlinks": branded_backlinks,
            "branded_pct": branded_pct,
            "total_sampled_backlinks": total_sampled,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-32",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "branded_backlinks": branded_backlinks,
            "other_backlinks": other_backlinks,
            "total_sampled_backlinks": total_sampled,
            "branded_pct_of_sampled": branded_pct,
            "branded_anchor_examples": branded_anchor_examples,
            "brand_variants_used": list(brand_variants),
            "note": (
                "Linked component only. Unlinked-mention frequency "
                "(brand named in body text without hyperlink) needs a "
                "separate web-mention pipeline and is not in this audit. "
                "A high branded share is GOOD; over-optimised exact-match "
                "anchors (low branded share) are a Penguin risk."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.anchors"],
    )


# ─── P3-35 — Authority-site links ──────────────────────────────────────────


@register_extractor("P3-35")
async def capture_p3_35(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-35 — Authority-site links (Consensus).

    Counts referring domains with DataForSEO ``rank`` >= 600 (their
    ~DR 50+ equivalent — established sites with substantial link
    profiles of their own). Even a small number of authority-site
    links anchors a site's link graph and is consistently correlated
    with rank in practitioner studies.

    Distinct from P3-02 (full DR distribution) — this surfaces the
    actual authority-domain names so an SEO exec can verify whether
    they're organic editorial citations or paid placements.

    Pass: at least 3 referring domains with rank >= 600.
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-35",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["backlinks.referring_domains"],
            errors=["no referring_domains"],
        )

    authority_threshold = 600
    authorities: list[dict[str, Any]] = []
    for r in refs:
        rank = r.get("rank")
        try:
            rank_f = float(rank) if rank is not None else None
        except (TypeError, ValueError):
            rank_f = None
        if rank_f is not None and rank_f >= authority_threshold:
            authorities.append(
                {
                    "domain": r.get("domain"),
                    "rank": rank,
                    "backlinks": r.get("backlinks"),
                    "first_seen": r.get("first_seen"),
                    "country": r.get("country"),
                }
            )

    authority_count = len(authorities)
    authorities.sort(
        key=lambda d: float(d.get("rank") or 0), reverse=True,
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 3 referring domains with DataForSEO rank >= 600 (authority sites, ~DR 50+)",
        passed=authority_count >= 3,
        evidence={
            "authority_count": authority_count,
            "threshold_rank": authority_threshold,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-35",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "authority_count": authority_count,
            "threshold_rank": authority_threshold,
            "sample_size": len(refs),
            "authorities": authorities[:25],
            "note": (
                "DataForSEO's 'rank' is 0-1000, roughly Ahrefs DR × 10. "
                "Manual inspection of the surfaced domains is essential: "
                "an authority-site link earned through editorial coverage "
                "vs. a paid sponsored placement carry very different "
                "weight even at the same DR."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.referring_domains"],
    )


# ─── P3-39 — Sitewide vs single-page links ─────────────────────────────────


@register_extractor("P3-39")
async def capture_p3_39(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-39 — Sitewide vs single-page links (Probable).

    Sitewide links appear in every page of a referring site (footer,
    sidebar, blogroll) — a single sitewide source can generate
    hundreds of low-signal backlinks. Single-page links from
    in-content editorial placements are much more valuable.

    Proxy: average backlinks per referring page across the top-N
    referring domains. Very high backlinks-per-page on the top domains
    suggests sitewide placement; spread is healthier.

    Pass:
    - Site-level backlinks/referring-page ratio <= 3.0 (no single
      page is producing dozens of links)
    - Top-1 referring domain's backlinks / its referring_pages
      <= 5.0 (most-frequent linker isn't carpet-bombing)
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-39", EvidenceWeight.PROBABLE, captured_at,
        )

    total_backlinks = int(summary.get("backlinks") or 0)
    referring_pages = int(summary.get("referring_pages") or 0)
    site_ratio = (
        round(total_backlinks / referring_pages, 2) if referring_pages else 0.0
    )

    refs = site.referring_domains or []
    top_domain_ratios: list[dict[str, Any]] = []
    for r in refs[:10]:
        d_backlinks = int(r.get("backlinks") or 0)
        d_pages = int(r.get("referring_pages") or 0)
        ratio = round(d_backlinks / d_pages, 2) if d_pages else 0.0
        top_domain_ratios.append(
            {
                "domain": r.get("domain"),
                "backlinks": d_backlinks,
                "referring_pages": d_pages,
                "ratio": ratio,
                "rank": r.get("rank"),
            }
        )

    top1_ratio = top_domain_ratios[0]["ratio"] if top_domain_ratios else 0.0
    suspected_sitewide = [
        d for d in top_domain_ratios if d["ratio"] >= 5.0
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site-level backlinks-per-referring-page <= 3.0 (no global carpet-bombing)",
        passed=site_ratio <= 3.0,
        evidence={
            "total_backlinks": total_backlinks,
            "referring_pages": referring_pages,
            "site_ratio": site_ratio,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No sampled referring domain has a backlinks/pages ratio >= 5.0 (no sitewide source)",
        passed=len(suspected_sitewide) == 0,
        evidence={
            "top1_ratio": top1_ratio,
            "top1_domain": (
                top_domain_ratios[0].get("domain") if top_domain_ratios else None
            ),
            "suspected_sitewide": [
                {"domain": d.get("domain"), "ratio": d["ratio"]}
                for d in suspected_sitewide
            ],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-39",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "site_ratio": site_ratio,
            "total_backlinks": total_backlinks,
            "referring_pages": referring_pages,
            "top_referring_domains_ratios": top_domain_ratios,
            "suspected_sitewide_domains": suspected_sitewide,
            "note": (
                "Ratio is a proxy: high backlinks-per-page concentrated on "
                "a single referring domain typically indicates sitewide "
                "footer/sidebar placement (blogroll, partner badges). "
                "Manual inspection of the top referring domain's pages "
                "confirms whether it's editorial or sitewide."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary", "backlinks.referring_domains"],
    )


# ─── timeseries helpers (P3-24 / P3-25) ────────────────────────────────────


def _timeseries_endpoint_deltas(
    points: list[dict],
    *,
    metric: str = "backlinks",
) -> dict[str, Any]:
    """Compute month-over-month deltas across a timeseries.

    Returns a summary with first/last values, absolute change,
    percentage change, monthly deltas, max-gain month, and max-loss
    month. The DataForSEO timeseries_summary endpoint emits one row
    per period (typically monthly).
    """
    if not points:
        return {
            "available": False,
            "reason": "no timeseries points",
        }

    def _parse_dt(row: dict) -> datetime | None:
        raw = row.get("date")
        if not raw:
            return None
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return None

    rows = []
    for p in points:
        dt = _parse_dt(p)
        if dt is None:
            continue
        try:
            v = int(p.get(metric) or 0)
        except (TypeError, ValueError):
            v = 0
        rows.append((dt, v))
    rows.sort(key=lambda x: x[0])
    if len(rows) < 2:
        return {
            "available": False,
            "reason": "fewer than 2 timeseries points",
            "points_seen": len(rows),
        }

    first_dt, first_v = rows[0]
    last_dt, last_v = rows[-1]
    abs_change = last_v - first_v
    pct_change = (abs_change / first_v * 100) if first_v else 0.0

    deltas: list[dict[str, Any]] = []
    for i in range(1, len(rows)):
        prev_dt, prev_v = rows[i - 1]
        cur_dt, cur_v = rows[i]
        deltas.append(
            {
                "from": prev_dt.strftime("%Y-%m"),
                "to": cur_dt.strftime("%Y-%m"),
                "delta": cur_v - prev_v,
                "from_value": prev_v,
                "to_value": cur_v,
            }
        )

    months_span = max(1, len(rows) - 1)
    avg_delta_per_month = round(abs_change / months_span, 1)

    gains = [d for d in deltas if d["delta"] > 0]
    losses = [d for d in deltas if d["delta"] < 0]
    max_gain = max(gains, key=lambda d: d["delta"], default=None)
    max_loss = min(losses, key=lambda d: d["delta"], default=None)

    return {
        "available": True,
        "metric": metric,
        "first_period": first_dt.strftime("%Y-%m"),
        "last_period": last_dt.strftime("%Y-%m"),
        "first_value": first_v,
        "last_value": last_v,
        "abs_change": abs_change,
        "pct_change": round(pct_change, 1),
        "months_in_series": len(rows),
        "avg_delta_per_month": avg_delta_per_month,
        "deltas": deltas,
        "max_gain_month": max_gain,
        "max_loss_month": max_loss,
        "total_months_with_gain": len(gains),
        "total_months_with_loss": len(losses),
    }


# ─── P3-24 — Backlink velocity (positive / gains) ──────────────────────────


@register_extractor("P3-24")
async def capture_p3_24(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-24 — Backlink velocity, positive direction (Probable).

    Tracks the rate at which the site is GAINING backlinks over a
    rolling ~12-month window. Sudden upward spikes can indicate paid
    link campaigns; flat or modestly-rising profiles look organic.

    Uses DataForSEO's timeseries_summary monthly snapshots — we compute
    referring-domain gains (the cleaner metric — domain count is less
    noisy than raw backlink count which double-counts sitewide).

    Pass:
    - At least one month in the window with positive referring-domain
      gain (the site is not stagnant)
    - No single month with a delta > 50% of the starting count
      (no acquisition spike that would trigger Penguin scrutiny)
    """
    captured_at = _now()
    series = site.backlinks_timeseries
    if not series:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-24",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no timeseries_summary data — DataForSEO call failed or empty",
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.timeseries_summary"],
            errors=["no timeseries"],
        )

    deltas = _timeseries_endpoint_deltas(series, metric="referring_main_domains")
    if not deltas.get("available"):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-24",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value=deltas,
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.timeseries_summary"],
            errors=[deltas.get("reason") or "no usable timeseries"],
        )

    months_with_gain = deltas["total_months_with_gain"]
    first_v = deltas["first_value"]
    max_gain_month = deltas["max_gain_month"] or {}
    biggest_gain_pct_of_start = (
        (max_gain_month.get("delta", 0) / first_v * 100) if first_v else 0.0
    )
    biggest_gain_pct_of_start = round(biggest_gain_pct_of_start, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 month in window with positive referring-domain gain (not stagnant)",
        passed=months_with_gain >= 1,
        evidence={
            "months_with_gain": months_with_gain,
            "months_in_series": deltas["months_in_series"],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No single month with referring-domain gain > 50% of starting count (no spike)",
        passed=biggest_gain_pct_of_start <= 50.0,
        evidence={
            "biggest_gain_pct_of_start": biggest_gain_pct_of_start,
            "biggest_gain_delta": max_gain_month.get("delta"),
            "biggest_gain_month": max_gain_month.get("to"),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-24",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "metric": "referring_main_domains",
            "window": f"{deltas['first_period']} → {deltas['last_period']}",
            "starting_value": first_v,
            "ending_value": deltas["last_value"],
            "abs_change": deltas["abs_change"],
            "pct_change": deltas["pct_change"],
            "avg_delta_per_month": deltas["avg_delta_per_month"],
            "months_with_gain": months_with_gain,
            "months_with_loss": deltas["total_months_with_loss"],
            "biggest_gain_month": max_gain_month,
            "biggest_gain_pct_of_start": biggest_gain_pct_of_start,
            "deltas_full": deltas["deltas"],
            "note": (
                "Velocity is measured on referring main domains (less "
                "noisy than raw backlinks). Healthy profiles show a "
                "gentle upward trend; aggressive spikes (>50% in one "
                "month) often correlate with paid-link campaigns."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.timeseries_summary"],
    )


# ─── P3-25 — Backlink velocity (negative / loss rate) ──────────────────────


@register_extractor("P3-25")
async def capture_p3_25(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-25 — Backlink velocity, negative direction / loss rate (Probable).

    Rate at which previously-existing backlinks are LOST over time:
    page deletions, redirects, link removals, de-indexation. Sustained
    losses with no compensating gains shrink the profile and erode
    authority. Spikes (sudden cliff drops) often indicate site-wide
    de-indexation of a major linker, manual disavow campaigns, or
    crawler-coverage shifts in DataForSEO's own index.

    Pass:
    - Overall net change >= -10% across the window (profile isn't
      collapsing)
    - No single month with a referring-domain delta < -20% of the
      prior count (no cliff drop)
    """
    captured_at = _now()
    series = site.backlinks_timeseries
    if not series:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-25",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no timeseries_summary data — DataForSEO call failed or empty",
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.timeseries_summary"],
            errors=["no timeseries"],
        )

    deltas = _timeseries_endpoint_deltas(series, metric="referring_main_domains")
    if not deltas.get("available"):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-25",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value=deltas,
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.timeseries_summary"],
            errors=[deltas.get("reason") or "no usable timeseries"],
        )

    pct_change = deltas["pct_change"]
    max_loss_month = deltas["max_loss_month"] or {}
    biggest_loss_delta = max_loss_month.get("delta", 0)
    biggest_loss_from = max_loss_month.get("from_value") or 0
    biggest_loss_pct_of_prior = (
        (biggest_loss_delta / biggest_loss_from * 100) if biggest_loss_from else 0.0
    )
    biggest_loss_pct_of_prior = round(biggest_loss_pct_of_prior, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Window-wide net referring-domain change >= -10% (profile not collapsing)",
        passed=pct_change >= -10.0,
        evidence={
            "pct_change": pct_change,
            "abs_change": deltas["abs_change"],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No single month with referring-domain loss > 20% of prior count (no cliff drop)",
        passed=biggest_loss_pct_of_prior >= -20.0,
        evidence={
            "biggest_loss_pct_of_prior": biggest_loss_pct_of_prior,
            "biggest_loss_delta": biggest_loss_delta,
            "biggest_loss_month": max_loss_month.get("to"),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-25",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "metric": "referring_main_domains",
            "window": f"{deltas['first_period']} → {deltas['last_period']}",
            "starting_value": deltas["first_value"],
            "ending_value": deltas["last_value"],
            "abs_change": deltas["abs_change"],
            "pct_change": pct_change,
            "months_with_gain": deltas["total_months_with_gain"],
            "months_with_loss": deltas["total_months_with_loss"],
            "biggest_loss_month": max_loss_month,
            "biggest_loss_pct_of_prior": biggest_loss_pct_of_prior,
            "deltas_full": deltas["deltas"],
            "note": (
                "Sustained losses without compensating gains indicate "
                "decay. DataForSEO's own crawl-coverage shifts can also "
                "show as losses — when a single big cliff drop appears, "
                "cross-check against Ahrefs' lost-links view before "
                "attributing it to actual link loss."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.timeseries_summary"],
    )


# ─── P3-28 — Linked as Wikipedia source ────────────────────────────────────


@register_extractor("P3-28")
async def capture_p3_28(
    ctx: AdapterContext,
    site: SiteData,
    *,
    wikipedia: WikipediaAdapter,
) -> CaptureRecord:
    """P3-28 — Linked as Wikipedia source (Probable).

    Wikipedia's citation guidelines require reliable sources. A
    Wikipedia article externally linking to a site is one of the
    strongest editorial signals available — Wikipedia editors actively
    police citations against the verifiability and reliable-source
    policies.

    Uses MediaWiki's ``list=exturlusage`` to find Wikipedia articles
    that contain an external link to the target domain.

    Pass: at least 1 Wikipedia article (any language) links to the
    target as an external reference.
    """
    captured_at = _now()
    domain = site.domain

    # Try https first; fall back to http
    hits: list[dict[str, Any]] = []
    try:
        hits = await wikipedia.external_url_usage(domain, protocol="https", limit=50)
    except Exception:  # noqa: BLE001
        hits = []
    if not hits:
        try:
            hits = await wikipedia.external_url_usage(
                domain, protocol="http", limit=50
            )
        except Exception:  # noqa: BLE001
            pass

    citation_count = len(hits)
    samples = []
    for h in hits[:20]:
        samples.append(
            {
                "title": h.get("title"),
                "pageid": h.get("pageid"),
                "url": h.get("url"),
            }
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 Wikipedia article externally links to the target domain",
        passed=citation_count >= 1,
        evidence={
            "citation_count": citation_count,
            "domain_queried": domain,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-28",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "citation_count": citation_count,
            "samples": samples,
            "domain_queried": domain,
            "note": (
                "Search limited to the English Wikipedia language edition. "
                "A non-English edition citation does not appear here. "
                "Wikipedia citations are one of the strongest editorial "
                "trust signals; a single citation typically reflects an "
                "editor's deliberate inclusion under WP:RS / WP:V "
                "policies."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["mediawiki.exturlusage"],
    )


# ─── P3-15 — Anchor spam phrase count ──────────────────────────────────────


# Patterns associated with paid-link operators and link networks. Each
# pattern is a substring matched case-insensitively against anchor text.
# Drawn from observed Penguin-flagged anchor patterns and the cluster
# we already see in pixelettetech.com's profile (TG @LINKS_DEALER,
# SeoBoost.agency style pitches).
_SPAM_ANCHOR_PATTERNS = (
    # Direct link-vendor signatures
    "links_dealer",
    "links dealer",
    "@links",
    "seoboost",
    "buy backlinks",
    "buy links",
    "guest post for sale",
    "pbn link",
    "real pbn",
    "premium backlinks",
    # Skyrocket-rank / DR-spam phrasing (classic seller copy)
    "skyrocket your",
    "skyrocket ahrefs",
    "ahrefs dr",
    "moz da",
    "majestic tf",
    # CTA / spam-phrase clusters that show up in over-optimised
    # anchor profiles
    "best price",
    "cheap seo",
    "lowest price",
    "pay after",
    "competitors trust us",
    # Money-keyword phrases stacked into anchors (deliberately
    # generic; flag if the anchor reads like an ad)
    "click here to buy",
    "order now",
    "limited offer",
)


@register_extractor("P3-15")
async def capture_p3_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-15 — Anchor spam phrase count (Probable).

    The leak features `phraseAnchorSpamCount`, `phraseAnchorSpamFraq`,
    `phraseAnchorSpamDemoted` collectively track Google's detection
    of suspicious anchor patterns: paid-link-network signatures,
    money-keyword stuffing, ad-style CTAs.

    We can't see Google's exact algorithm, but we can detect the
    same SHAPE of anchor patterns in our prefetched anchor data
    using a curated spam-phrase library.

    Pass:
    - Zero anchors match a spam-phrase pattern, AND
    - No single anchor accounts for >5% of total sampled backlinks
      (concentration-on-one-phrase is itself a manipulation signal)
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-15",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no backlinks_anchors data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no anchors"],
        )

    total_backlinks_sampled = 0
    spam_matches: list[dict[str, Any]] = []
    anchor_concentrations: list[dict[str, Any]] = []

    for a in anchors:
        text = (a.get("anchor") or "").strip()
        if not text:
            continue
        backlinks_count = int(a.get("backlinks") or 0)
        total_backlinks_sampled += backlinks_count
        lower = text.lower()
        for pattern in _SPAM_ANCHOR_PATTERNS:
            if pattern in lower:
                spam_matches.append(
                    {
                        "anchor": text[:200],
                        "matched_pattern": pattern,
                        "backlinks": backlinks_count,
                        "referring_domains": a.get("referring_domains"),
                    }
                )
                break  # one match per anchor is enough

        anchor_concentrations.append(
            {"anchor": text[:120], "backlinks": backlinks_count}
        )

    spam_match_count = len(spam_matches)
    spam_backlinks_total = sum(m["backlinks"] for m in spam_matches)
    spam_pct_of_sampled = (
        round(spam_backlinks_total / total_backlinks_sampled * 100, 1)
        if total_backlinks_sampled
        else 0.0
    )

    # Concentration check: top single anchor as % of sampled backlinks
    anchor_concentrations.sort(key=lambda d: d["backlinks"], reverse=True)
    top_anchor = anchor_concentrations[0] if anchor_concentrations else None
    top_pct = (
        round(top_anchor["backlinks"] / total_backlinks_sampled * 100, 1)
        if (top_anchor and total_backlinks_sampled)
        else 0.0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Zero anchors match a known spam-phrase pattern (paid-link / money-keyword)",
        passed=spam_match_count == 0,
        evidence={
            "spam_match_count": spam_match_count,
            "spam_backlinks_total": spam_backlinks_total,
            "spam_pct_of_sampled": spam_pct_of_sampled,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No single anchor accounts for > 5% of sampled backlinks (no concentration)",
        passed=top_pct <= 5.0,
        evidence={
            "top_anchor": top_anchor,
            "top_pct": top_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-15",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "spam_match_count": spam_match_count,
            "spam_matches": spam_matches[:25],
            "spam_backlinks_total": spam_backlinks_total,
            "spam_pct_of_sampled": spam_pct_of_sampled,
            "top_anchor": top_anchor,
            "top_pct_of_sampled": top_pct,
            "total_sampled_backlinks": total_backlinks_sampled,
            "spam_patterns_library_size": len(_SPAM_ANCHOR_PATTERNS),
            "note": (
                "Curated pattern library detects the shape of paid-link / "
                "money-keyword anchors. Surfacing the actual matched "
                "anchors lets a manual reviewer judge whether each is a "
                "genuine spam signal or a false positive. Disavow "
                "candidates are usually a subset of these."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.anchors"],
    )


# ─── P3-08 — Homepage PageRank (homepagePagerankNs) proxy ──────────────────


@register_extractor("P3-08")
async def capture_p3_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-08 — Homepage PageRank proxy (Probable).

    The leaked `homepagePagerankNs` feature is internal to Google and
    not directly observable. The taxonomy documents DataForSEO's
    domain-level ``rank`` as the operational approximation: it scores
    the root domain's overall authority on a 0-1000 scale (~Ahrefs
    DR × 10) and is used as the de-facto homepage-authority proxy.

    Pass: domain rank >= 200 (Ahrefs DR ~20+; minimum for a site
    with established external authority).
    """
    captured_at = _now()
    summary = site.backlinks_summary
    if summary is None:
        return _unmeasurable_no_summary(
            ctx, site, "P3-08", EvidenceWeight.PROBABLE, captured_at,
        )

    rank = summary.get("rank")
    try:
        rank_int = int(rank) if rank is not None else None
    except (TypeError, ValueError):
        rank_int = None

    if rank_int is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-08",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no rank field in backlinks_summary"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.summary"],
            errors=["no rank"],
        )

    # Approximate DR equivalent (DataForSEO rank / 10 ≈ Ahrefs DR)
    approx_dr = round(rank_int / 10, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Domain rank >= 200 (~DR 20+; established authority threshold)",
        passed=rank_int >= 200,
        evidence={
            "dataforseo_rank": rank_int,
            "approx_dr_equivalent": approx_dr,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-08",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "dataforseo_rank": rank_int,
            "approx_dr_equivalent": approx_dr,
            "rank_scale": "0-1000 (DataForSEO proprietary; ~Ahrefs DR × 10)",
            "note": (
                "homepagePagerankNs is a Google-internal feature; this "
                "extractor uses DataForSEO's domain-level rank as the "
                "documented external approximation. The rank is computed "
                "across the entire link graph DataForSEO has crawled, so "
                "it behaves as a homepage-authority proxy even for "
                "sub-paths."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.summary"],
    )


# ─── P3-20 — Link location in content ──────────────────────────────────────


@register_extractor("P3-20")
async def capture_p3_20(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-20 — Link location in content (Probable, partial measurement).

    The variable wants per-link position WITHIN the page body — above
    the fold vs mid-content vs below the fold. That position-precision
    requires rendering each linking page in a browser-equivalent
    environment, which is operationally prohibitive at backlink scale.

    What DataForSEO does expose is HTML5 semantic location
    (``article``/``section``/``main``/``figure`` vs ``nav``/``aside``/
    ``footer``/``header``). That signal is already operationalised by
    **P3-19 — Contextual links** with multi-rule evaluation.

    We mark P3-20 as UNMEASURABLE here so the SEO exec doc surfaces
    the limitation explicitly. The redirect points readers to P3-19
    for the available data.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-20",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "per-link above-fold / below-fold position requires "
                "rendering each linking page; not feasible at backlink "
                "scale. Semantic location (article/main vs nav/footer) "
                "is captured at P3-19 — Contextual links."
            ),
            "see_also": "P3-19",
            "approximation_available_at": "P3-19",
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[],
        errors=["position requires browser render"],
    )


# ─── P3-30 — Disavow tool usage ────────────────────────────────────────────


@register_extractor("P3-30")
async def capture_p3_30(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-30 — Disavow tool usage (Consensus, owner-only).

    Google's disavow file is uploaded to and read from Google Search
    Console. The disavow list itself is visible only to verified
    property owners — there is no public API and no third-party
    measurement path. SEOMATE runs as an external auditor; it has no
    GSC access.

    Marked UNMEASURABLE with explicit owner-data remediation. When a
    later platform phase adds optional GSC integration, this extractor
    will be rewritten to parse the disavow file directly.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-30",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "disavow file is visible only to verified property owners "
                "in Google Search Console; no public API exposes it. "
                "External audits cannot read it."
            ),
            "remediation": (
                "to populate this variable, connect Google Search Console "
                "ownership in a future platform release, or have the site "
                "owner export the active disavow file and upload it as "
                "supplementary audit input."
            ),
            "related": ["P3-29 — Toxic backlink presence (the disavow source-of-truth)"],
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[],
        errors=["owner-only access"],
    )


# ─── P3-37 — Widget links ──────────────────────────────────────────────────


@register_extractor("P3-37")
async def capture_p3_37(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-37 — Widget links (Probable).

    Widget links are backlinks placed via embedded widgets, badges,
    or iframes that a third-party site installs. Classic patterns:
    "Powered by X" embedded in every customer's footer, certification
    badges with hardcoded backlink, tool/calculator embeds.

    Detection heuristics from the data we already have:
    1. **Anchor concentration on a single phrase across many domains**
       — a widget that ships the same anchor will surface in
       backlinks_anchors as one anchor entry with high
       `referring_main_domains` count.
    2. **Single-domain backlink avalanche** — one referring domain
       contributing dozens of backlinks across many of its own pages
       (high backlinks/referring_pages ratio for that domain).

    Pass:
    - No anchor accounts for backlinks across >= 20 distinct domains
      with identical phrasing (no widget-style mass syndication)
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-37",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no backlinks_anchors data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no anchors"],
        )

    # Branded anchors / naked-URL citations spanning many domains are
    # NORMAL organic brand-mention behaviour, not widgets. Real widgets
    # ship a NON-branded, NON-URL anchor identical across many sites
    # ("Powered by X", "Free SEO Audit", "Get a Quote"). Exclude
    # branded + naked-URL anchors from the widget-candidate check.
    brand_variants: tuple[str, ...] = ()
    if site.brand:
        brand_variants = site.brand.all_variants

    widget_candidates: list[dict[str, Any]] = []
    excluded_branded_url: list[dict[str, Any]] = []
    for a in anchors:
        text = (a.get("anchor") or "").strip()
        if not text:
            continue
        ref_domains = int(a.get("referring_main_domains") or 0)
        backlinks = int(a.get("backlinks") or 0)
        if ref_domains < 20:
            continue

        # Classify the anchor — only flag widgets if it's not
        # branded / naked-URL / image-alt-empty
        cls = _classify_anchor(text, brand_variants)
        record = {
            "anchor": text[:200],
            "referring_main_domains": ref_domains,
            "backlinks": backlinks,
            "backlinks_per_domain": (
                round(backlinks / ref_domains, 2) if ref_domains else 0
            ),
            "anchor_class": cls,
        }
        if cls in ("branded", "naked_url", "empty"):
            excluded_branded_url.append(record)
        else:
            widget_candidates.append(record)

    # Sort by domain spread, highest first
    widget_candidates.sort(
        key=lambda d: d["referring_main_domains"], reverse=True,
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No anchor spans >= 20 distinct referring domains with identical phrasing (no widget syndication)",
        passed=len(widget_candidates) == 0,
        evidence={
            "widget_candidate_count": len(widget_candidates),
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-37",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "widget_candidate_count": len(widget_candidates),
            "widget_candidates": widget_candidates[:15],
            "excluded_branded_or_url_count": len(excluded_branded_url),
            "excluded_branded_or_url": excluded_branded_url[:5],
            "threshold_domains": 20,
            "note": (
                "Non-branded, non-URL anchors spanning many domains "
                "with identical phrasing are the classic widget/badge "
                "signature. Branded anchors and naked-URL citations "
                "with wide cross-domain spread are organic and are "
                "reported separately as 'excluded_branded_or_url' for "
                "reviewer sanity-checking, but they don't trigger a fail."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.anchors"],
    )


# ─── P3-38 — Press release / article directory links ──────────────────────


# Anchor / domain patterns characteristic of press-release wires and
# article-directory networks. PRs typically have brand-name +
# boilerplate phrasing in anchors; article directories often use
# generic info-content anchors with high cross-domain spread.
_PRESS_RELEASE_DOMAIN_PATTERNS = (
    "prnewswire", "prweb", "businesswire", "newswire", "pressrelease",
    "openpr", "einnews", "marketwatch", "issuewire", "pr.com",
    "sbwire", "24-7pressrelease", "globenewswire", "accesswire",
    "ein.news", "pressreleasepoint", "prlog",
)
_DIRECTORY_DOMAIN_PATTERNS = (
    "ezinearticles", "articlebase", "articlesfactory", "goarticles",
    "articlesnatch", "buzzle", "hubpages", "selfgrowth",
    "amazines", "articledashboard", "articleclick", "isnare",
    "freedirectory", "submitfreelink", "addurl",
    "directorysearch", "linkdirectory", "bestoftheweb",
)


@register_extractor("P3-38")
async def capture_p3_38(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-38 — Press-release / article-directory links (Probable).

    Press-release distribution wires and article directories produce
    high-volume, low-quality syndication backlinks. Google's Penguin
    explicitly devalues these. Detection here uses domain-pattern
    matching against known PR-wire and article-directory networks.

    Pass:
    - Zero referring domains match a known press-release-wire pattern
    - Zero referring domains match a known article-directory pattern
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-38",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains"],
            errors=["no referring_domains"],
        )

    pr_matches: list[dict[str, Any]] = []
    directory_matches: list[dict[str, Any]] = []
    for r in refs:
        domain = (r.get("domain") or "").lower()
        if not domain:
            continue
        backlinks = int(r.get("backlinks") or 0)
        rank = r.get("rank")
        for pattern in _PRESS_RELEASE_DOMAIN_PATTERNS:
            if pattern in domain:
                pr_matches.append(
                    {
                        "domain": domain,
                        "matched_pattern": pattern,
                        "backlinks": backlinks,
                        "rank": rank,
                    }
                )
                break
        for pattern in _DIRECTORY_DOMAIN_PATTERNS:
            if pattern in domain:
                directory_matches.append(
                    {
                        "domain": domain,
                        "matched_pattern": pattern,
                        "backlinks": backlinks,
                        "rank": rank,
                    }
                )
                break

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Zero referring domains match a known press-release-wire pattern",
        passed=len(pr_matches) == 0,
        evidence={"pr_match_count": len(pr_matches)},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Zero referring domains match a known article-directory pattern",
        passed=len(directory_matches) == 0,
        evidence={"directory_match_count": len(directory_matches)},
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-38",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pr_match_count": len(pr_matches),
            "press_release_matches": pr_matches[:20],
            "directory_match_count": len(directory_matches),
            "directory_matches": directory_matches[:20],
            "pr_pattern_library_size": len(_PRESS_RELEASE_DOMAIN_PATTERNS),
            "directory_pattern_library_size": len(_DIRECTORY_DOMAIN_PATTERNS),
            "sample_size": len(refs),
            "note": (
                "Detection is domain-pattern based and covers the major "
                "PR-wire networks (PR Newswire, BusinessWire, etc.) and "
                "classic article directories (EzineArticles, HubPages, "
                "etc.). Smaller or local PR services may not match. "
                "A few matches typically reflect organic PR coverage; "
                "many matches indicate active PR-link buying."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains"],
    )


# ─── P3-07 — Authority of linking page ─────────────────────────────────────


@register_extractor("P3-07")
async def capture_p3_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-07 — Authority of linking page (Probable).

    Distinct from P3-02 (domain-level DR distribution) — this measures
    PAGE-level authority of the pages hosting each backlink. A
    high-rank PAGE on a moderate-DR DOMAIN often passes more value
    than a low-rank page on a high-DR domain.

    Uses DataForSEO's per-anchor ``rank`` field, which aggregates
    rank across the linking pages each anchor surfaces. Provides a
    distributional view of linking-page authority across the sampled
    anchor inventory.

    Pass:
    - At least 5 anchors with rank >= 600 (linking pages with strong
      authority)
    - <= 60% of anchors with rank < 150 (profile not dominated by
      low-authority linking pages)
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-07",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no backlinks_anchors data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no anchors"],
        )

    ranks: list[int] = []
    high_authority: list[dict[str, Any]] = []
    very_low: list[dict[str, Any]] = []
    for a in anchors:
        rank = a.get("rank")
        try:
            rank_int = int(rank) if rank is not None else None
        except (TypeError, ValueError):
            rank_int = None
        if rank_int is None:
            continue
        ranks.append(rank_int)
        record = {
            "anchor": (a.get("anchor") or "")[:120],
            "rank": rank_int,
            "backlinks": a.get("backlinks"),
            "referring_main_domains": a.get("referring_main_domains"),
        }
        if rank_int >= 600 and len(high_authority) < 15:
            high_authority.append(record)
        if rank_int < 150:
            very_low.append(record)

    if not ranks:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-07",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no parseable rank values on sampled anchors"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors"],
            errors=["no parseable rank"],
        )

    n = len(ranks)
    buckets = {
        "very_high_ge_800": sum(1 for r in ranks if r >= 800),
        "high_600_799": sum(1 for r in ranks if 600 <= r < 800),
        "medium_350_599": sum(1 for r in ranks if 350 <= r < 600),
        "low_150_349": sum(1 for r in ranks if 150 <= r < 350),
        "very_low_lt_150": sum(1 for r in ranks if r < 150),
    }
    very_low_pct = round(buckets["very_low_lt_150"] / n * 100, 1)
    high_count = buckets["very_high_ge_800"] + buckets["high_600_799"]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 5 anchors with rank >= 600 (high-authority linking pages present)",
        passed=high_count >= 5,
        evidence={
            "high_authority_count": high_count,
            "sampled_anchors": n,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 60% of anchors at rank < 150 (profile not dominated by low-authority pages)",
        passed=very_low_pct <= 60.0,
        evidence={
            "very_low_count": buckets["very_low_lt_150"],
            "very_low_pct": very_low_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-07",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "sampled_anchors": n,
            "rank_buckets": buckets,
            "very_low_pct": very_low_pct,
            "high_authority_count": high_count,
            "high_authority_examples": high_authority,
            "very_low_count": len(very_low),
            "note": (
                "DataForSEO's per-anchor 'rank' aggregates rank across "
                "the linking pages that surface each anchor. A robust "
                "profile has a mix: some high-authority linking pages "
                "anchoring the top end, with a long tail of medium / "
                "lower-rank pages. A profile dominated by very-low "
                "ranks usually means scraper sites and link farms."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.anchors"],
    )


# ─── P3-10 — Page-level PageRank (PageRankNS proxy) ────────────────────────


@register_extractor("P3-10")
async def capture_p3_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-10 — Page-level PageRank for our own pages (Probable).

    The leaked Google feature ``PageRankNS`` is per-document. The
    documented external proxy is DataForSEO's per-URL ``rank`` from
    the ``bulk_pages_summary`` endpoint, which scores each page on
    a 0-1000 scale based on its inbound link profile.

    Reports per-page rank for the audited site's own pages. Surfaces
    pages with zero or very low rank (orphaned in the link graph)
    and the rank distribution across the site.

    Pass:
    - Homepage rank >= 200 (~DR 20+; established authority)
    - At least 25% of audited pages have rank >= 100 (most pages
      have some external link equity, not just the home page)
    """
    captured_at = _now()
    rows = site.bulk_pages_backlinks
    if not rows:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no bulk_pages_summary data — DataForSEO call failed or empty",
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.bulk_pages_summary"],
            errors=["no bulk_pages_summary"],
        )

    homepage_rank: int | None = None
    per_page: list[dict[str, Any]] = []
    primary = (site.primary_url or "").rstrip("/")

    for r in rows:
        url = r.get("url") or r.get("target") or ""
        rank = r.get("rank")
        try:
            rank_int = int(rank) if rank is not None else None
        except (TypeError, ValueError):
            rank_int = None
        backlinks = r.get("backlinks")
        ref_pages = r.get("referring_pages")
        ref_domains = r.get("referring_domains")

        per_page.append(
            {
                "url": url,
                "rank": rank_int,
                "backlinks": backlinks,
                "referring_pages": ref_pages,
                "referring_domains": ref_domains,
            }
        )

        stripped = url.rstrip("/")
        if primary and (stripped == primary or stripped == primary.replace("www.", "")):
            homepage_rank = rank_int

    ranks_present = [p["rank"] for p in per_page if p["rank"] is not None]
    if not ranks_present:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no parseable rank values in bulk_pages_summary response",
                "rows_received": len(rows),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.bulk_pages_summary"],
            errors=["no parseable rank"],
        )

    n = len(ranks_present)
    above_100 = sum(1 for r in ranks_present if r >= 100)
    above_100_pct = round(above_100 / n * 100, 1)
    distribution = {
        "ge_500": sum(1 for r in ranks_present if r >= 500),
        "200_499": sum(1 for r in ranks_present if 200 <= r < 500),
        "100_199": sum(1 for r in ranks_present if 100 <= r < 200),
        "1_99": sum(1 for r in ranks_present if 1 <= r < 100),
        "zero": sum(1 for r in ranks_present if r == 0),
    }

    per_page.sort(key=lambda d: d.get("rank") or -1, reverse=True)
    zero_rank_urls = [p["url"] for p in per_page if p.get("rank") == 0]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Homepage rank >= 200 (~DR 20+; established homepage authority)",
        passed=(homepage_rank is not None and homepage_rank >= 200),
        evidence={"homepage_rank": homepage_rank, "homepage_match": primary},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">= 25% of audited pages have rank >= 100 (equity spreads beyond homepage)",
        passed=above_100_pct >= 25.0,
        evidence={
            "above_100_count": above_100,
            "above_100_pct": above_100_pct,
            "sampled_pages": n,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "homepage_rank": homepage_rank,
            "homepage_url_matched": primary,
            "pages_sampled": n,
            "above_100_count": above_100,
            "above_100_pct": above_100_pct,
            "distribution": distribution,
            "top_pages_by_rank": per_page[:10],
            "zero_rank_count": len(zero_rank_urls),
            "zero_rank_urls": zero_rank_urls[:15],
            "note": (
                "Rank is DataForSEO's per-URL 0-1000 score (~Ahrefs UR × 10). "
                "Pages with zero rank receive no external link equity at "
                "all; they exist only via internal linking. Pages with "
                "ge-200 rank carry meaningful external authority."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.bulk_pages_summary"],
    )


# ─── P3-31 — Reciprocal link ratio ─────────────────────────────────────────


@register_extractor("P3-31")
async def capture_p3_31(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-31 — Reciprocal link ratio (Probable).

    Detects "you link to me, I link to you" patterns. Google
    considers excessive reciprocal linking a manipulation pattern
    (link schemes guideline). A few reciprocals are organic (partners,
    industry peers, supplier relationships); many reciprocals across
    low-quality domains is a Penguin risk.

    Uses our existing link_graph to extract outbound EXTERNAL domains
    from our pages, then intersects against the referring_domains
    list. The intersection size is the reciprocal count.

    Pass:
    - Reciprocal ratio (reciprocals / referring_domains sample) <= 10%
      (small, organic-looking overlap)
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-31",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "html.outbound_external"],
            errors=["no referring_domains"],
        )

    link_graph = site.link_graph
    if link_graph is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-31",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link_graph available — HTML prefetch produced no parsed links"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "html.outbound_external"],
            errors=["no link_graph"],
        )

    from urllib.parse import urlparse

    outbound_domains: set[str] = set()
    for url, refs_list in link_graph.outbound.items():
        for ref in refs_list:
            if getattr(ref, "is_internal", True):
                continue
            target = getattr(ref, "target_url", None)
            if not target:
                continue
            try:
                host = urlparse(target).hostname or ""
            except Exception:  # noqa: BLE001
                continue
            host = host.lower().lstrip(".")
            if host.startswith("www."):
                host = host[4:]
            if host:
                outbound_domains.add(host)

    referring_set: set[str] = set()
    for r in refs:
        d = (r.get("domain") or "").lower().lstrip(".")
        if d.startswith("www."):
            d = d[4:]
        if d:
            referring_set.add(d)

    reciprocals = sorted(outbound_domains & referring_set)
    ref_count = len(referring_set)
    reciprocal_pct = (
        round(len(reciprocals) / ref_count * 100, 1) if ref_count else 0.0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Reciprocal ratio <= 10% of sampled referring domains (no link-scheme pattern)",
        passed=reciprocal_pct <= 10.0,
        evidence={
            "reciprocal_count": len(reciprocals),
            "reciprocal_pct": reciprocal_pct,
            "sampled_referring_domains": ref_count,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-31",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "reciprocal_count": len(reciprocals),
            "reciprocal_pct": reciprocal_pct,
            "reciprocal_domains": reciprocals[:25],
            "outbound_domains_count": len(outbound_domains),
            "referring_domains_sampled": ref_count,
            "note": (
                "Reciprocal detection compares OUR audited pages' outbound "
                "external domains against the top-N referring domains. "
                "Limitations: outbound is only from pages we crawled; "
                "referring is the top-N by rank (not exhaustive). Real "
                "reciprocal ratio at the full-profile level is bounded "
                "by sampling. Surfaces actual matched domains so a "
                "reviewer can verify each."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains", "html.outbound_external"],
    )


# ─── LLM helpers for P3-14 / P3-21 / P3-34 ─────────────────────────────────


def _site_topic_summary(site: SiteData) -> str:
    """One-line topic summary of the audited site for LLM context.

    Derives from brand name + a sample of page titles + the home page's
    first text snippet if available. Stays under ~400 chars so the
    Haiku prompts remain tight.
    """
    parts: list[str] = []
    if site.brand and site.brand.name:
        parts.append(site.brand.name)

    # Sample first 6 page titles
    titles: list[str] = []
    for url, audit in list(site.page_audits.items())[:30]:
        if audit.title and audit.title.strip():
            titles.append(audit.title.strip())
        if len(titles) >= 6:
            break
    if titles:
        parts.append("; pages: " + " | ".join(titles))

    summary = " — ".join(parts) if parts else (site.domain or "unknown site")
    return summary[:400]


async def _call_haiku_json(
    llm: LlmAdapter,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> list[dict[str, Any]] | None:
    """Single Haiku call that expects a JSON array reply.

    Returns the parsed list, or None if the call failed (not configured,
    billing-blocked, malformed JSON). Errors are logged via the
    adapter's tracker, not raised.
    """
    if not llm.is_configured:
        return None
    try:
        result = await llm.batch_evaluate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
    except LlmNotConfigured:
        return None
    except Exception:  # noqa: BLE001
        return None
    if result.parsed is None or result.error:
        return None
    return result.parsed


# ─── P3-14 — Anchor mismatch demotion ──────────────────────────────────────


@register_extractor("P3-14")
async def capture_p3_14(
    ctx: AdapterContext,
    site: SiteData,
    *,
    llm: LlmAdapter,
) -> CaptureRecord:
    """P3-14 — Anchor mismatch demotion (Probable, LLM-classified).

    Leak feature ``AnchorMismatchDemotion`` penalises links whose
    anchor text doesn't match the destination's topic. We can't see
    Google's exact judgement, but we can detect the same pattern by
    asking an LLM (Haiku) to classify each anchor's topical alignment
    with the audited site's known topic.

    Pass: <= 20% of sampled anchors classified as topic-mismatched
    by Haiku (mismatched anchors should be rare and individually
    auditable).
    """
    captured_at = _now()
    anchors = site.backlinks_anchors
    if not anchors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-14",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no backlinks_anchors data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors", "llm.anthropic_haiku"],
            errors=["no anchors"],
        )

    # Take top 30 anchors by backlink count for LLM analysis (cost-bound)
    sorted_anchors = sorted(
        anchors, key=lambda a: int(a.get("backlinks") or 0), reverse=True
    )
    sample = sorted_anchors[:30]
    sample_payload = [
        {
            "idx": i,
            "anchor": (a.get("anchor") or "")[:200],
            "backlinks": int(a.get("backlinks") or 0),
        }
        for i, a in enumerate(sample)
    ]

    topic = _site_topic_summary(site)
    system_prompt = (
        "You are an SEO analyst classifying backlink anchor texts. "
        "For each anchor, decide whether its text is topically aligned "
        "with the destination site's actual subject area or whether it "
        "looks mismatched (off-topic anchor pointing at this site). "
        "Branded anchors (containing the brand name) count as aligned. "
        "Naked URL anchors are neutral (not mismatched). Generic "
        "anchors like 'click here' / 'visit website' are neutral. "
        "Reply ONLY with a JSON array."
    )
    user_prompt = (
        f"Destination site topic context:\n{topic}\n\n"
        "For each anchor below, return a JSON object with: "
        "`idx` (int), `alignment` (one of: 'aligned', 'neutral', "
        "'mismatched'), and `reason` (short string). Return one object "
        "per input anchor, in a JSON array.\n\n"
        f"Anchors:\n{_json.dumps(sample_payload, ensure_ascii=False)}"
    )

    classifications = await _call_haiku_json(
        llm, system_prompt=system_prompt, user_prompt=user_prompt
    )
    if classifications is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-14",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "LLM classifier unavailable (ANTHROPIC_API_KEY missing, "
                    "billing-blocked, or parse failure). Re-run audit with "
                    "credits available to populate this variable."
                ),
                "sampled_anchors": len(sample),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.anchors", "llm.anthropic_haiku"],
            errors=["llm unavailable"],
        )

    by_idx = {int(c.get("idx", -1)): c for c in classifications if isinstance(c, dict)}
    aligned_count = 0
    neutral_count = 0
    mismatched_count = 0
    mismatched_examples: list[dict[str, Any]] = []
    unclassified = 0
    for i, a in enumerate(sample):
        cls = by_idx.get(i)
        if cls is None:
            unclassified += 1
            continue
        alignment = (cls.get("alignment") or "").lower()
        if alignment == "aligned":
            aligned_count += 1
        elif alignment == "mismatched":
            mismatched_count += 1
            if len(mismatched_examples) < 15:
                mismatched_examples.append(
                    {
                        "anchor": sample_payload[i]["anchor"],
                        "backlinks": sample_payload[i]["backlinks"],
                        "reason": cls.get("reason", ""),
                    }
                )
        else:
            neutral_count += 1

    n = len(sample) - unclassified
    mismatched_pct = round(mismatched_count / n * 100, 1) if n else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="<= 20% of sampled anchors classified as topic-mismatched by LLM",
        passed=mismatched_pct <= 20.0,
        evidence={
            "mismatched_count": mismatched_count,
            "mismatched_pct": mismatched_pct,
            "sampled_anchors": n,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-14",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "sampled_anchors": n,
            "aligned_count": aligned_count,
            "neutral_count": neutral_count,
            "mismatched_count": mismatched_count,
            "mismatched_pct": mismatched_pct,
            "unclassified": unclassified,
            "mismatched_examples": mismatched_examples,
            "topic_context_used": topic,
            "note": (
                "Anchor mismatch is LLM-classified against the audited "
                "site's known topic; not a literal read of Google's "
                "AnchorMismatchDemotion feature. A small mismatched "
                "share is normal (generic anchors, scraped sites). "
                "High share indicates either off-topic linker spam or a "
                "site whose actual topic differs from what links suggest."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.anchors", "llm.anthropic_haiku"],
    )


# ─── P3-21 — Linking domain topical relevance ──────────────────────────────


@register_extractor("P3-21")
async def capture_p3_21(
    ctx: AdapterContext,
    site: SiteData,
    *,
    llm: LlmAdapter,
) -> CaptureRecord:
    """P3-21 — Linking domain topical relevance (Consensus, LLM-classified).

    Backlinks from topically-relevant domains carry more weight than
    backlinks from random / scraper / off-topic sites. Haiku classifies
    each referring domain's likely topic area and judges relevance to
    the audited site's subject area.

    Pass: >= 25% of sampled referring domains classified as topically
    relevant or partially-relevant (i.e. the link profile shows
    meaningful topical context, not just scattered low-quality links).
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-21",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["no referring_domains"],
        )

    sample = refs[:50]
    sample_payload = [
        {
            "idx": i,
            "domain": (r.get("domain") or "")[:120],
            "rank": r.get("rank"),
            "backlinks": r.get("backlinks"),
        }
        for i, r in enumerate(sample)
    ]
    topic = _site_topic_summary(site)
    system_prompt = (
        "You are an SEO analyst classifying referring domains by topical "
        "relevance to a destination site. Use the domain name and rank "
        "as your signal — a low-rank domain whose name implies a "
        "different industry is not relevant; a recognised tech / "
        "software / business publication IS relevant to a tech B2B site. "
        "Reply ONLY with a JSON array."
    )
    user_prompt = (
        f"Destination site topic context:\n{topic}\n\n"
        "For each referring domain below, return a JSON object with: "
        "`idx` (int), `relevance` (one of: 'relevant', "
        "'partially_relevant', 'irrelevant', 'unknown'), and `reason` "
        "(short string, ≤ 120 chars). Return one object per input "
        "domain, in a JSON array.\n\n"
        f"Referring domains:\n{_json.dumps(sample_payload, ensure_ascii=False)}"
    )

    classifications = await _call_haiku_json(
        llm, system_prompt=system_prompt, user_prompt=user_prompt
    )
    if classifications is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-21",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "LLM classifier unavailable (ANTHROPIC_API_KEY missing, "
                    "billing-blocked, or parse failure). Re-run audit with "
                    "credits available to populate this variable."
                ),
                "sampled_domains": len(sample),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["llm unavailable"],
        )

    by_idx = {int(c.get("idx", -1)): c for c in classifications if isinstance(c, dict)}
    buckets = {"relevant": 0, "partially_relevant": 0, "irrelevant": 0, "unknown": 0}
    relevant_examples: list[dict[str, Any]] = []
    irrelevant_examples: list[dict[str, Any]] = []
    unclassified = 0
    for i, r in enumerate(sample):
        cls = by_idx.get(i)
        if cls is None:
            unclassified += 1
            continue
        rel = (cls.get("relevance") or "unknown").lower()
        if rel not in buckets:
            rel = "unknown"
        buckets[rel] += 1
        if rel == "relevant" and len(relevant_examples) < 15:
            relevant_examples.append(
                {
                    "domain": sample_payload[i]["domain"],
                    "rank": sample_payload[i]["rank"],
                    "reason": cls.get("reason", ""),
                }
            )
        elif rel == "irrelevant" and len(irrelevant_examples) < 15:
            irrelevant_examples.append(
                {
                    "domain": sample_payload[i]["domain"],
                    "rank": sample_payload[i]["rank"],
                    "reason": cls.get("reason", ""),
                }
            )

    n = len(sample) - unclassified
    relevant_pct = (
        round((buckets["relevant"] + buckets["partially_relevant"]) / n * 100, 1)
        if n
        else 0.0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 25% of sampled referring domains classified as topically relevant or partially-relevant",
        passed=relevant_pct >= 25.0,
        evidence={
            "relevant_or_partial_count": buckets["relevant"] + buckets["partially_relevant"],
            "relevant_pct": relevant_pct,
            "sampled_domains": n,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-21",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "sampled_domains": n,
            "distribution": buckets,
            "relevant_pct": relevant_pct,
            "unclassified": unclassified,
            "relevant_examples": relevant_examples,
            "irrelevant_examples": irrelevant_examples,
            "topic_context_used": topic,
            "note": (
                "Topical-relevance classification is by domain name + "
                "rank (no page-content fetching). LLM heuristic recognises "
                "industry publications and recognisable platforms; "
                "obscure small sites typically classify as 'unknown'. "
                "Relevant domains carry materially more authority weight "
                "than the same rank from off-topic sources."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
    )


# ─── P3-34 — Hub page links ────────────────────────────────────────────────


@register_extractor("P3-34")
async def capture_p3_34(
    ctx: AdapterContext,
    site: SiteData,
    *,
    llm: LlmAdapter,
) -> CaptureRecord:
    """P3-34 — Hub page / resource page links (Probable, LLM-classified).

    Backlinks from resource-style hub pages (curated link lists,
    industry resource pages, awesome-style aggregators) carry high
    editorial-endorsement weight when topically relevant. Haiku
    classifies each referring domain as likely hub / non-hub based on
    domain name patterns.

    Pass: at least 3 referring domains classified as hub-style
    resource pages (some editorial-curation signal present in the
    profile).
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-34",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["no referring_domains"],
        )

    sample = refs[:50]
    sample_payload = [
        {
            "idx": i,
            "domain": (r.get("domain") or "")[:120],
            "rank": r.get("rank"),
            "backlinks": r.get("backlinks"),
        }
        for i, r in enumerate(sample)
    ]
    system_prompt = (
        "You are an SEO analyst classifying referring domains by likely "
        "page type. A 'hub page' or 'resource page' is a curated list / "
        "directory / aggregator page (e.g. 'awesome-x' GitHub lists, "
        "industry-resource pages, 'best tools for X' roundups, B2B "
        "service-provider directories like Clutch, GoodFirms, "
        "Techreviewer, DesignRush). A 'review' or 'editorial' site is "
        "NOT a hub. A blog post is NOT a hub. Reply ONLY with a JSON "
        "array."
    )
    user_prompt = (
        "For each referring domain below, return a JSON object with: "
        "`idx` (int), `is_hub` (boolean — true if this looks like a "
        "curated hub/resource/directory page), `confidence` (float "
        "0.0-1.0), and `reason` (short string, ≤ 100 chars). Return "
        "one object per input domain.\n\n"
        f"Referring domains:\n{_json.dumps(sample_payload, ensure_ascii=False)}"
    )

    classifications = await _call_haiku_json(
        llm, system_prompt=system_prompt, user_prompt=user_prompt
    )
    if classifications is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-34",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "LLM classifier unavailable (ANTHROPIC_API_KEY missing, "
                    "billing-blocked, or parse failure). Re-run audit with "
                    "credits available to populate this variable."
                ),
                "sampled_domains": len(sample),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["llm unavailable"],
        )

    by_idx = {int(c.get("idx", -1)): c for c in classifications if isinstance(c, dict)}
    hub_count = 0
    hub_examples: list[dict[str, Any]] = []
    unclassified = 0
    for i, r in enumerate(sample):
        cls = by_idx.get(i)
        if cls is None:
            unclassified += 1
            continue
        if cls.get("is_hub") is True:
            hub_count += 1
            if len(hub_examples) < 20:
                hub_examples.append(
                    {
                        "domain": sample_payload[i]["domain"],
                        "rank": sample_payload[i]["rank"],
                        "confidence": cls.get("confidence"),
                        "reason": cls.get("reason", ""),
                    }
                )

    n = len(sample) - unclassified

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 3 referring domains classified as hub/resource pages",
        passed=hub_count >= 3,
        evidence={
            "hub_count": hub_count,
            "sampled_domains": n,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-34",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "sampled_domains": n,
            "hub_count": hub_count,
            "hub_examples": hub_examples,
            "unclassified": unclassified,
            "note": (
                "Hub classification by LLM heuristic on domain names. "
                "B2B service-directory sites (Clutch, GoodFirms, "
                "Techreviewer, DesignRush) commonly classify as hubs. "
                "Domain-only signal: real verification requires manually "
                "visiting the referring page."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
    )


# ─── P3-36 — Guest post links ──────────────────────────────────────────────


@register_extractor("P3-36")
async def capture_p3_36(
    ctx: AdapterContext,
    site: SiteData,
    *,
    llm: LlmAdapter,
) -> CaptureRecord:
    """P3-36 — Guest post links (Probable, LLM-classified).

    Guest-post placements range from genuine editorial contributions
    to industry publications (high value) to paid links on networks
    that exist primarily to sell guest-post slots (Penguin risk).
    Haiku classifies each referring domain as likely guest-post
    network / accepts-guest-posts / regular-publisher based on
    domain-name patterns.

    Pass: <= 25% of sampled referring domains classified as
    guest-post-network style (volume of paid-guest-post-style linkers
    is bounded).
    """
    captured_at = _now()
    refs = site.referring_domains
    if not refs:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-36",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no referring_domains data — Backlinks API call failed or empty"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["no referring_domains"],
        )

    sample = refs[:50]
    sample_payload = [
        {
            "idx": i,
            "domain": (r.get("domain") or "")[:120],
            "rank": r.get("rank"),
            "backlinks": r.get("backlinks"),
        }
        for i, r in enumerate(sample)
    ]
    system_prompt = (
        "You are an SEO analyst classifying referring domains by likely "
        "guest-post characteristics. A 'guest-post network' is a site "
        "that primarily exists to host paid guest posts / SEO-driven "
        "contributor articles (low editorial bar, generic 'write for "
        "us' platforms, content farms accepting outside submissions). "
        "A real industry publication (e.g. TechCrunch, Forbes, "
        "established news sites) is NOT a guest-post network, even if "
        "they accept contributor content. A B2B directory is NOT a "
        "guest-post network. Reply ONLY with a JSON array."
    )
    user_prompt = (
        "For each referring domain below, return a JSON object with: "
        "`idx` (int), `is_guest_post_network` (boolean), `confidence` "
        "(float 0.0-1.0), and `reason` (short string, ≤ 100 chars). "
        "Return one object per input domain.\n\n"
        f"Referring domains:\n{_json.dumps(sample_payload, ensure_ascii=False)}"
    )

    classifications = await _call_haiku_json(
        llm, system_prompt=system_prompt, user_prompt=user_prompt
    )
    if classifications is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-36",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "LLM classifier unavailable (ANTHROPIC_API_KEY missing, "
                    "billing-blocked, or parse failure). Re-run audit with "
                    "credits available to populate this variable."
                ),
                "sampled_domains": len(sample),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
            errors=["llm unavailable"],
        )

    by_idx = {int(c.get("idx", -1)): c for c in classifications if isinstance(c, dict)}
    gp_count = 0
    gp_examples: list[dict[str, Any]] = []
    unclassified = 0
    for i, r in enumerate(sample):
        cls = by_idx.get(i)
        if cls is None:
            unclassified += 1
            continue
        if cls.get("is_guest_post_network") is True:
            gp_count += 1
            if len(gp_examples) < 25:
                gp_examples.append(
                    {
                        "domain": sample_payload[i]["domain"],
                        "rank": sample_payload[i]["rank"],
                        "confidence": cls.get("confidence"),
                        "reason": cls.get("reason", ""),
                    }
                )

    n = len(sample) - unclassified
    gp_pct = round(gp_count / n * 100, 1) if n else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="<= 25% of sampled referring domains classified as guest-post networks",
        passed=gp_pct <= 25.0,
        evidence={
            "guest_post_network_count": gp_count,
            "guest_post_pct": gp_pct,
            "sampled_domains": n,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-36",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "sampled_domains": n,
            "guest_post_network_count": gp_count,
            "guest_post_pct": gp_pct,
            "guest_post_examples": gp_examples,
            "unclassified": unclassified,
            "note": (
                "Domain-only classification; LLM flags name patterns "
                "consistent with paid-guest-post networks. Real "
                "verification requires inspecting the page (presence of "
                "byline + 'sponsored' / 'collaboration' / 'submit your "
                "article' indicators). Strong fail signal when guest-"
                "post networks dominate a profile."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["backlinks.referring_domains", "llm.anthropic_haiku"],
    )


# ─── P3-27 — Co-occurrences (brand + topic mentions on referring pages) ─────


@register_extractor("P3-27")
async def capture_p3_27(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-27 — Co-occurrences (Probable, requires referrer-page crawl).

    The variable measures whether the brand name and the site's
    topic-keywords appear together in the body text of referring
    pages — a strong contextual signal (the page treats the brand as
    a genuine topical reference, not just a footer logo link).

    Detecting this requires fetching and parsing the body text of
    each referring page. Our current audit fetches the audited site's
    own pages plus DataForSEO's aggregate backlink data, but it does
    NOT crawl referrer pages. Adding a 50-page external scrape pass
    would add ~30s + bandwidth cost; deferred until the platform
    decides whether to enable it as an optional deep-audit mode.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-27",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "co-occurrence detection requires crawling referring "
                "pages' body text. SEOMATE's H1 backlinks pillar reads "
                "DataForSEO aggregate data only; no referrer-page "
                "scrape pass is performed."
            ),
            "remediation": (
                "to populate this variable, add an optional referrer-crawl "
                "stage that fetches the top-N referring URLs (from the "
                "DataForSEO /backlinks endpoint) and runs brand + topic "
                "keyword presence detection on each page's body. ~50 "
                "fetches per audit, +30-60s wall time, ~negligible cost."
            ),
            "approximation_available_at": (
                "partial signal via P3-12 (anchor distribution — branded "
                "anchors imply contextual brand mention) and P3-21 "
                "(linking domain topical relevance — relevant domains "
                "are more likely to co-occur brand + topic)"
            ),
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[],
        errors=["requires referrer-page crawl"],
    )
