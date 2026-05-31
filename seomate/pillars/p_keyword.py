"""Keyword + domain-rank extractors (P0 + partial P3).

Drives off the DataForSEO Labs ``ranked_keywords`` and
``domain_rank_overview`` endpoints — both pay-per-call from the
account balance, no Backlinks subscription required.

Variables operationalised:

- P0-02 — Search volume distribution across the site's keyword universe
- P0-03 — Keyword difficulty distribution
- P0-04 — Cost-per-click distribution (commercial-value indicator)
- P3-09 — Site-wide authority score (partial: organic-traffic proxy
            only; the full composition needs Backlinks subscription)

Keyword universe is auto-discovered from ``ranked_keywords`` until
P0-13 (curated keyword-to-page mapping) lands. The variable values
record this provenance so reviewers know they're looking at "what
Pixelette ranks for today" rather than "what Pixelette wants to rank
for".
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from seomate.adapters import AdapterContext
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor

# ─── Tunables ───────────────────────────────────────────────────────────────

# Universe-size floor: a site with fewer than 10 ranked keywords has
# either a very narrow topical focus or weak organic visibility.
KEYWORD_UNIVERSE_FLOOR = 10
KEYWORD_UNIVERSE_HEALTHY = 50

# Per-keyword search-volume bands.
SEARCH_VOLUME_MEANINGFUL = 50      # below this is essentially long-tail noise
SEARCH_VOLUME_HIGH = 1000          # head-term threshold

# Keyword difficulty bands (DataForSEO 0-100 scale).
KD_EASY_MAX = 30
KD_HARD_MIN = 70

# CPC bands (USD). Anything > $1 indicates real advertiser bidding,
# proxying for commercial intent.
CPC_COMMERCIAL_FLOOR = 1.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_record(
    *,
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    pillar: str,
    captured_at: datetime,
    status: CaptureStatus,
    value: dict[str, Any] | None,
    rules: list[RuleResult] | None,
    evidence_weight: EvidenceWeight,
    data_sources: list[str],
    cost_gbp: float = 0.0,
    errors: list[str] | None = None,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar=pillar,
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


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _no_keywords_unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    pillar: str,
    weight: EvidenceWeight,
    captured_at: datetime,
) -> CaptureRecord:
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        pillar=pillar,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": "no ranked keywords returned for this domain",
            "ranked_keywords_total": 0,
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["dataforseo_labs.ranked_keywords"],
        errors=["site.ranked_keywords is empty"],
    )


def _extract_metrics(item: dict) -> dict[str, Any]:
    """Pluck the fields we care about from a ranked_keywords item."""
    kw_data = item.get("keyword_data") or {}
    keyword = kw_data.get("keyword") or ""
    ki = kw_data.get("keyword_info") or {}
    kp = kw_data.get("keyword_properties") or {}
    serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
    return {
        "keyword": keyword,
        "search_volume": int(ki.get("search_volume") or 0),
        "cpc": float(ki.get("cpc") or 0.0),
        "keyword_difficulty": (
            int(kp.get("keyword_difficulty"))
            if kp.get("keyword_difficulty") is not None
            else None
        ),
        "rank_absolute": (
            int(serp.get("rank_absolute"))
            if serp.get("rank_absolute") is not None
            else None
        ),
        "url": serp.get("url"),
    }


# ─── P0-02 — Search volume distribution ─────────────────────────────────────


@register_extractor("P0-02")
async def capture_p0_02(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-02 — Search volume distribution across the site's keyword universe.

    Universe is auto-discovered via ``dataforseo_labs.ranked_keywords``
    (top 200 by search volume) until a curated keyword list lands.
    Reports the distribution and flags whether the universe is
    operationally meaningful (>= floor + non-trivial median volume).
    """
    captured_at = _now()
    items = site.ranked_keywords
    if not items:
        return _no_keywords_unmeasurable(
            ctx, site, "P0-02", "P0", EvidenceWeight.CONSENSUS, captured_at,
        )

    metrics = [_extract_metrics(i) for i in items]
    volumes = [m["search_volume"] for m in metrics]
    nonzero = [v for v in volumes if v > 0]
    meaningful = [v for v in volumes if v >= SEARCH_VOLUME_MEANINGFUL]
    head_terms = [v for v in volumes if v >= SEARCH_VOLUME_HIGH]
    median = _percentile(nonzero, 0.50) if nonzero else None
    p75 = _percentile(nonzero, 0.75) if nonzero else None
    total_monthly_opportunity = sum(volumes)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Keyword universe contains at least {KEYWORD_UNIVERSE_FLOOR} ranked terms",
        passed=len(metrics) >= KEYWORD_UNIVERSE_FLOOR,
        evidence={
            "ranked_keywords_total": len(metrics),
            "floor": KEYWORD_UNIVERSE_FLOOR,
            "healthy_threshold": KEYWORD_UNIVERSE_HEALTHY,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f">= 50% of ranked keywords have search volume >= {SEARCH_VOLUME_MEANINGFUL}/month",
        passed=(len(meaningful) / len(metrics)) >= 0.5 if metrics else False,
        evidence={
            "meaningful_volume_count": len(meaningful),
            "ranked_total": len(metrics),
            "threshold_meaningful": SEARCH_VOLUME_MEANINGFUL,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text=f"At least one head term in universe (volume >= {SEARCH_VOLUME_HIGH})",
        passed=len(head_terms) > 0,
        evidence={
            "head_term_count": len(head_terms),
            "head_threshold": SEARCH_VOLUME_HIGH,
        },
        notes="Head terms are not strictly required; some sites build authority through long-tail aggregation.",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    top_10_by_volume = sorted(metrics, key=lambda m: m["search_volume"], reverse=True)[:10]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-02",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "ranked_keywords_total": len(metrics),
            "nonzero_volume_count": len(nonzero),
            "meaningful_volume_count": len(meaningful),
            "head_term_count": len(head_terms),
            "median_volume": int(median) if median is not None else None,
            "p75_volume": int(p75) if p75 is not None else None,
            "max_volume": max(volumes) if volumes else 0,
            "total_monthly_opportunity": total_monthly_opportunity,
            "universe_provenance": "auto_discovered_from_ranked_keywords",
            "top_10_by_volume": top_10_by_volume,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo_labs.ranked_keywords"],
    )


# ─── P0-03 — Keyword difficulty distribution ────────────────────────────────


@register_extractor("P0-03")
async def capture_p0_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-03 — Keyword difficulty distribution (Probable).

    KD is provider-specific (DataForSEO 0-100 scale). Treat absolute
    values as estimates; the directional signal — which keywords are
    easier to rank for — is what we record.
    """
    captured_at = _now()
    items = site.ranked_keywords
    if not items:
        return _no_keywords_unmeasurable(
            ctx, site, "P0-03", "P0", EvidenceWeight.PROBABLE, captured_at,
        )

    metrics = [_extract_metrics(i) for i in items]
    kd_values = [m["keyword_difficulty"] for m in metrics if m["keyword_difficulty"] is not None]

    if not kd_values:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-03",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no keyword_difficulty values returned for any ranked keyword",
                "ranked_keywords_total": len(metrics),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["all keyword_difficulty values None"],
        )

    easy = [k for k in kd_values if k <= KD_EASY_MAX]
    hard = [k for k in kd_values if k >= KD_HARD_MIN]
    median = _percentile([float(k) for k in kd_values], 0.50)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"At least one easy-win keyword in universe (KD <= {KD_EASY_MAX})",
        passed=len(easy) > 0,
        evidence={
            "easy_count": len(easy),
            "easy_threshold": KD_EASY_MAX,
            "kd_count": len(kd_values),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Median keyword difficulty <= 60 (universe is achievable)",
        passed=median is not None and median <= 60,
        evidence={
            "median_kd": round(median, 1) if median is not None else None,
            "kd_count": len(kd_values),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text=f"Hard keywords (KD >= {KD_HARD_MIN}) are not majority of universe",
        passed=(len(hard) / len(kd_values)) < 0.5 if kd_values else False,
        evidence={
            "hard_count": len(hard),
            "hard_threshold": KD_HARD_MIN,
            "hard_pct": round(len(hard) / len(kd_values) * 100, 1) if kd_values else 0,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-03",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "kd_count": len(kd_values),
            "easy_count": len(easy),
            "hard_count": len(hard),
            "median_kd": round(median, 1) if median is not None else None,
            "min_kd": min(kd_values) if kd_values else None,
            "max_kd": max(kd_values) if kd_values else None,
            "thresholds": {"easy_max": KD_EASY_MAX, "hard_min": KD_HARD_MIN},
            "methodology": "DataForSEO Labs keyword_difficulty (0-100); estimate, not absolute",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo_labs.ranked_keywords"],
    )


# ─── P0-04 — Cost-per-click distribution ────────────────────────────────────


@register_extractor("P0-04")
async def capture_p0_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-04 — Cost-per-click distribution (Probable).

    CPC is a directly observable advertiser-bid signal — a proxy for
    commercial value of the keyword. High-CPC universe = strong
    transactional intent.
    """
    captured_at = _now()
    items = site.ranked_keywords
    if not items:
        return _no_keywords_unmeasurable(
            ctx, site, "P0-04", "P0", EvidenceWeight.PROBABLE, captured_at,
        )

    metrics = [_extract_metrics(i) for i in items]
    cpc_values = [m["cpc"] for m in metrics]
    paid = [c for c in cpc_values if c > 0]
    commercial = [c for c in cpc_values if c >= CPC_COMMERCIAL_FLOOR]
    median = _percentile(paid, 0.50) if paid else None
    avg = sum(paid) / len(paid) if paid else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one keyword in universe has a non-zero CPC (commercial relevance)",
        passed=len(paid) > 0,
        evidence={
            "paid_count": len(paid),
            "total": len(cpc_values),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"At least 20% of paid-CPC keywords have CPC >= ${CPC_COMMERCIAL_FLOOR}",
        passed=(len(commercial) / len(paid)) >= 0.2 if paid else False,
        evidence={
            "commercial_count": len(commercial),
            "paid_count": len(paid),
            "commercial_floor_usd": CPC_COMMERCIAL_FLOOR,
        },
        notes="Commercial-floor share is a soft signal; informational sites legitimately rank low-CPC.",
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-04",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "total_keywords": len(cpc_values),
            "paid_count": len(paid),
            "commercial_count": len(commercial),
            "avg_cpc_usd": round(avg, 2),
            "median_cpc_usd": round(median, 2) if median is not None else None,
            "max_cpc_usd": round(max(cpc_values), 2) if cpc_values else 0.0,
            "commercial_floor_usd": CPC_COMMERCIAL_FLOOR,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo_labs.ranked_keywords"],
    )


# ─── P3-09 — Site-wide authority score (partial: organic-traffic proxy) ─────


@register_extractor("P3-09")
async def capture_p3_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P3-09 — Site-wide authority score (Probable, PARTIAL composition).

    The full ``siteAuthority`` composition wants four signals:
    - Domain rating from Backlinks (gated on subscription — unavailable here)
    - Referring-domain quality distribution (same)
    - Brand search volume (P0-15 — not yet implemented)
    - Knowledge Graph entity status (P0-16 — gated on KG key)

    This implementation reports the **organic-traffic-proxy slice** we
    can capture today: ranked-keyword count + estimated traffic + rank
    distribution from ``domain_rank_overview``. Status is ``partial``
    until backlinks + brand + KG signals land.
    """
    captured_at = _now()
    overview = site.domain_rank_overview
    if overview is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P3-09",
            pillar="P3",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "domain_rank_overview not available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.domain_rank_overview"],
            errors=["site.domain_rank_overview is None"],
        )

    organic = (overview.get("metrics") or {}).get("organic") or {}
    keyword_count = int(organic.get("count") or 0)
    estimated_traffic = float(organic.get("etv") or 0.0)
    estimated_paid_value = float(organic.get("estimated_paid_traffic_cost") or 0.0)
    pos_distribution = {
        k: int(organic.get(k) or 0)
        for k in (
            "pos_1", "pos_2_3", "pos_4_10", "pos_11_20",
            "pos_21_30", "pos_31_40", "pos_41_50", "pos_51_60",
            "pos_61_70", "pos_71_80", "pos_81_90", "pos_91_100",
        )
    }
    top_10_count = sum(
        pos_distribution[k] for k in ("pos_1", "pos_2_3", "pos_4_10")
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has measurable organic visibility (>= 10 ranked keywords)",
        passed=keyword_count >= 10,
        evidence={"organic_keyword_count": keyword_count},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one keyword ranks in Google's top 10",
        passed=top_10_count > 0,
        evidence={
            "top_10_count": top_10_count,
            "pos_distribution": pos_distribution,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Estimated organic traffic value > 0 (site has measurable presence)",
        passed=estimated_traffic > 0,
        evidence={
            "estimated_monthly_traffic": estimated_traffic,
            "estimated_paid_traffic_cost_usd": estimated_paid_value,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Domain Rank score component (DEFERRED — requires Backlinks subscription)",
        passed=True,
        evidence={"method": "deferred_until_backlinks_subscription"},
        notes="Full siteAuthority composition needs Backlinks domain rating.",
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Knowledge Graph entity component (DEFERRED — requires GOOGLE_KG_API_KEY)",
        passed=True,
        evidence={"method": "deferred_until_kg_key_set"},
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5]
    # Hard rules: 1, 2, 3 (the slice we can actually measure now).
    # Status is partial because we deliberately can't compute the full
    # composition yet.
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed
    status = CaptureStatus.PARTIAL  # honest: we report what we can; full score needs backlinks

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P3-09",
        pillar="P3",
        captured_at=captured_at,
        status=status,
        value={
            "organic_keyword_count": keyword_count,
            "estimated_monthly_traffic": estimated_traffic,
            "estimated_paid_traffic_cost_usd": estimated_paid_value,
            "top_10_count": top_10_count,
            "pos_distribution": pos_distribution,
            "organic_traffic_proxy_pass": overall_pass,
            "missing_signals": [
                "backlinks.domain_rating",
                "backlinks.referring_domains_quality",
                "P0-15.brand_search_volume",
                "P0-16.kg_entity_match",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo_labs.domain_rank_overview"],
        errors=[
            "Status=partial: full siteAuthority composition needs backlinks subscription + KG key"
        ],
    )


# ─── P0-15 — Brand search volume baseline ───────────────────────────────────


@register_extractor("P0-15")
async def capture_p0_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-15 — Brand search volume baseline (Probable, single-snapshot).

    Reads from ``site.brand_keyword_volumes`` (Keyword Data API pre-
    fetch on brand variants). Reports the volume per variant. The
    "trajectory" half of the variable (growing / flat / declining)
    needs historical data — flagged as deferred until cross-audit
    snapshots accumulate.
    """
    captured_at = _now()
    volumes = site.brand_keyword_volumes
    if not volumes:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-15",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no brand keyword volume data returned (no brand configured or API error)",
                "brand": site.brand.name if site.brand else None,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo.keywords_data.google_ads.search_volume"],
            errors=["brand_keyword_volumes empty"],
        )

    per_variant = [
        {
            "keyword": r.get("keyword"),
            "search_volume": r.get("search_volume"),
            "cpc": r.get("cpc"),
            "competition": r.get("competition"),
        }
        for r in volumes
    ]
    variants_with_volume = [v for v in per_variant if isinstance(v.get("search_volume"), int) and v["search_volume"] > 0]
    total_brand_volume = sum(
        (v["search_volume"] or 0) for v in variants_with_volume
    )
    max_variant_volume = max(
        (v["search_volume"] for v in variants_with_volume), default=0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one brand variant has measurable monthly search volume",
        passed=len(variants_with_volume) >= 1,
        evidence={
            "variants_queried": len(per_variant),
            "variants_with_volume": len(variants_with_volume),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Top brand variant has at least 100 monthly searches",
        passed=max_variant_volume >= 100,
        evidence={
            "max_variant_volume": max_variant_volume,
            "threshold": 100,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Trajectory (growing / flat / declining) tracked over time",
        passed=True,
        evidence={"method": "deferred_until_cross_audit_snapshots_accumulate"},
        notes="Requires >= 2 audit snapshots; flagged as deferred on first audit.",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-15",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "brand": site.brand.name if site.brand else None,
            "variants_queried": len(per_variant),
            "total_monthly_brand_volume": total_brand_volume,
            "max_variant_volume": max_variant_volume,
            "per_variant": per_variant,
            "trajectory_status": "deferred_until_cross_audit_snapshots",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.keywords_data.google_ads.search_volume"],
    )
