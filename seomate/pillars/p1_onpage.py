"""Pillar 1 — On-Page SEO extractors.

All extractors here read from ``site.page_audits`` (pre-fetched by the
orchestrator) instead of calling DataForSEO directly. Adding a new
P1 variable that fits the cheap-layer pattern is now a fill-in:
implement the per-page checks, evaluate Step 1.5 rules, return a
CaptureRecord. No new API calls; no extra cost.

Variables operationalised in this module:

- P1-01 — Title presence and uniqueness         (Consensus, 6 rules)
- P1-02 — Title length 50–60 char target         (Contested,  per-page threshold)
- P1-07 — Meta description presence              (Consensus,  presence)
- P1-08 — Meta description length 140–160 target (Contested,  per-page threshold)
- P1-11 — H1 presence                            (Consensus,  presence)
- P1-12 — Single H1 per page                     (Contested,  count check)
- P1-20 — Canonical tag presence + self-reference (Consensus, multi-rule)

Variables that need a target keyword (P1-03, P1-04, P1-13, P1-14, P1-17)
are deferred until P0-13 (keyword-to-page mapping) is implemented.
Variables that need full document order (P1-15 heading hierarchy) are
deferred until we have a content-parsing layer that gives us heading
sequence; DataForSEO Instant Pages bucket tags by level, not by order.
"""
from __future__ import annotations

import re
from collections import defaultdict
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
from seomate.pillars._base import PageAudit, SiteData, register_extractor

# ─── Helpers ────────────────────────────────────────────────────────────────


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
        pillar="P1",
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


def _unmeasurable_when_no_audits(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
) -> CaptureRecord:
    """Build the canonical 'no page data available' capture for a P1 var."""
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={"reason": "no successful page audits available for the site"},
        rules=None,
        evidence_weight=weight,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "site.page_audits",
        ],
        errors=[
            f"page_audit_errors_count: {len(site.page_audit_errors)}",
        ]
        if site.page_audit_errors
        else ["site.page_audits is empty"],
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _grade_clean_rate(
    clean: int,
    total: int,
    *,
    pass_at: float = 0.9,
    partial_at: float = 0.7,
) -> CaptureStatus:
    """Grade a distribution variable by the share of pages/URLs meeting best practice.

    ``clean / total`` >= ``pass_at`` -> PASSED, >= ``partial_at`` -> PARTIAL,
    else FAILED. Callers handle the no-data case before calling this, so a
    PASSED from here means the site genuinely meets the bar, not merely that the
    metric was captured. Evidence weight (Contested/Probable) still conveys how
    much to trust the verdict; it no longer doubles as a reason to always pass.
    """
    if total <= 0:
        return CaptureStatus.UNMEASURABLE
    rate = clean / total
    if rate >= pass_at:
        return CaptureStatus.PASSED
    if rate >= partial_at:
        return CaptureStatus.PARTIAL
    return CaptureStatus.FAILED


# ─── P1-01 — Title presence and uniqueness ──────────────────────────────────


@register_extractor("P1-01")
async def capture_p1_01(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001 - data already pre-fetched
) -> CaptureRecord:
    """P1-01 — Title tag presence and uniqueness (Consensus, 6 Step 1.5 rules)."""
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-01", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]

    missing_title = [p.url for p in indexable if not _has_title(p)]
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every indexable page has a <title> element",
        passed=len(missing_title) == 0,
        evidence={
            "indexable_pages_audited": len(indexable),
            "pages_missing_title": missing_title,
        },
    )

    blank_title = [
        p.url for p in indexable if _has_title(p) and not (p.title or "").strip()
    ]
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Title text is non-empty (not whitespace, placeholder, or unrendered template)",
        passed=len(blank_title) == 0,
        evidence={"pages_with_blank_title": blank_title},
    )

    by_title: dict[str, list[str]] = defaultdict(list)
    for p in indexable:
        if p.title and p.title.strip():
            by_title[p.title.strip().lower()].append(p.url)
    duplicate_clusters = {t: us for t, us in by_title.items() if len(us) > 1}
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No two indexable pages share the same title",
        passed=len(duplicate_clusters) == 0,
        evidence={
            "duplicate_title_count": len(duplicate_clusters),
            "duplicate_title_clusters": duplicate_clusters,
        },
    )

    multi_title = [p.url for p in indexable if p.has_multiple_titles]
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Single <title> element per page (no duplicates in head)",
        passed=len(multi_title) == 0,
        evidence={"pages_with_multiple_title_elements": multi_title},
    )

    non_indexable_count = len(audits) - len(indexable)
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Title duplication on non-indexable pages does not count",
        passed=True,
        evidence={
            "total_pages_audited": len(audits),
            "indexable_pages": len(indexable),
            "non_indexable_pages": non_indexable_count,
        },
        notes="Indexability inferred from HTTP status, redirect status, and noindex directive.",
    )

    rule_6 = RuleResult(
        rule_id=6,
        rule_text="Failure modes produce distinct findings",
        passed=True,
        evidence={
            "rule_1_passed": rule_1.passed,
            "rule_2_passed": rule_2.passed,
            "rule_3_passed": rule_3.passed,
            "rule_4_passed": rule_4.passed,
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6]
    overall_pass = all(r.passed for r in (rule_1, rule_2, rule_3, rule_4))

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_audited": len(audits),
            "indexable_pages": len(indexable),
            "duplicate_title_clusters": list(duplicate_clusters.keys()),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.title_uniqueness_aggregation",
        ],
    )


# ─── P1-02 — Title length 50–60 character target ────────────────────────────


TITLE_LENGTH_MIN = 30        # too-short threshold
TITLE_LENGTH_OPTIMAL_LO = 50
TITLE_LENGTH_OPTIMAL_HI = 60
TITLE_LENGTH_MAX = 70        # too-long threshold (truncation likely)


@register_extractor("P1-02")
async def capture_p1_02(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-02 — Title length, 50–60 char target (Contested).

    Reports the per-page title-length distribution against thresholds
    practitioners use as a proxy for SERP truncation. Recorded as
    Contested because the 50–60 figure is observation-based, not
    Google-endorsed.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-02", EvidenceWeight.CONTESTED, captured_at
        )

    indexable_with_title = [p for p in audits if p.is_indexable and _has_title(p)]
    too_short = [
        {"url": p.url, "length": p.title_length}
        for p in indexable_with_title
        if p.title_length < TITLE_LENGTH_MIN
    ]
    in_optimal = [
        p.url
        for p in indexable_with_title
        if TITLE_LENGTH_OPTIMAL_LO <= p.title_length <= TITLE_LENGTH_OPTIMAL_HI
    ]
    in_acceptable_above = [
        {"url": p.url, "length": p.title_length}
        for p in indexable_with_title
        if TITLE_LENGTH_OPTIMAL_HI < p.title_length <= TITLE_LENGTH_MAX
    ]
    too_long = [
        {"url": p.url, "length": p.title_length}
        for p in indexable_with_title
        if p.title_length > TITLE_LENGTH_MAX
    ]

    n = len(indexable_with_title)
    optimal_pct = (len(in_optimal) / n * 100.0) if n else 0.0

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-02",
        captured_at=captured_at,
        status=_grade_clean_rate(n - len(too_short) - len(too_long), n),
        value={
            "indexable_pages_with_title": n,
            "in_optimal_range": len(in_optimal),
            "in_optimal_pct": round(optimal_pct, 1),
            "too_short_count": len(too_short),
            "too_short_urls": too_short,
            "above_optimal_but_acceptable": in_acceptable_above,
            "too_long_count": len(too_long),
            "too_long_urls": too_long,
            "thresholds": {
                "too_short_below": TITLE_LENGTH_MIN,
                "optimal_lo": TITLE_LENGTH_OPTIMAL_LO,
                "optimal_hi": TITLE_LENGTH_OPTIMAL_HI,
                "too_long_above": TITLE_LENGTH_MAX,
            },
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.title_length_buckets",
        ],
    )


# ─── P1-07 — Meta description presence ──────────────────────────────────────


@register_extractor("P1-07")
async def capture_p1_07(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-07 — Meta description presence (Consensus, single rule)."""
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-07", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    missing = [p.url for p in indexable if not _has_description(p)]
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every indexable page has a non-empty meta description",
        passed=len(missing) == 0,
        evidence={
            "indexable_pages_audited": len(indexable),
            "pages_missing_description": missing,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-07",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_missing_description": len(missing),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo.on_page.instant_pages",
        ],
    )


# ─── P1-08 — Meta description length ────────────────────────────────────────


DESC_LENGTH_MIN = 70
DESC_LENGTH_OPTIMAL_LO = 140
DESC_LENGTH_OPTIMAL_HI = 160
DESC_LENGTH_MAX = 200


@register_extractor("P1-08")
async def capture_p1_08(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-08 — Meta description length, 140–160 char target (Contested)."""
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-08", EvidenceWeight.CONTESTED, captured_at
        )

    indexable_with_desc = [
        p for p in audits if p.is_indexable and _has_description(p)
    ]
    too_short = [
        {"url": p.url, "length": p.description_length}
        for p in indexable_with_desc
        if p.description_length < DESC_LENGTH_MIN
    ]
    in_optimal = [
        p.url
        for p in indexable_with_desc
        if DESC_LENGTH_OPTIMAL_LO <= p.description_length <= DESC_LENGTH_OPTIMAL_HI
    ]
    too_long = [
        {"url": p.url, "length": p.description_length}
        for p in indexable_with_desc
        if p.description_length > DESC_LENGTH_MAX
    ]

    n = len(indexable_with_desc)
    optimal_pct = (len(in_optimal) / n * 100.0) if n else 0.0

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-08",
        captured_at=captured_at,
        status=_grade_clean_rate(n - len(too_short) - len(too_long), n),
        value={
            "indexable_pages_with_description": n,
            "in_optimal_range": len(in_optimal),
            "in_optimal_pct": round(optimal_pct, 1),
            "too_short_count": len(too_short),
            "too_short_urls": too_short,
            "too_long_count": len(too_long),
            "too_long_urls": too_long,
            "thresholds": {
                "too_short_below": DESC_LENGTH_MIN,
                "optimal_lo": DESC_LENGTH_OPTIMAL_LO,
                "optimal_hi": DESC_LENGTH_OPTIMAL_HI,
                "too_long_above": DESC_LENGTH_MAX,
            },
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.description_length_buckets",
        ],
    )


# ─── P1-11 — H1 presence ────────────────────────────────────────────────────


@register_extractor("P1-11")
async def capture_p1_11(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-11 — Every indexable page has at least one H1 (Consensus)."""
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-11", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    missing = [p.url for p in indexable if len(p.h1) == 0]
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every indexable page has at least one <h1>",
        passed=len(missing) == 0,
        evidence={
            "indexable_pages_audited": len(indexable),
            "pages_missing_h1": missing,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-11",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_missing_h1": len(missing),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-12 — Single H1 per page (Contested) ────────────────────────────────


@register_extractor("P1-12")
async def capture_p1_12(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-12 — Page contains exactly one <h1> (Contested).

    Practitioner consensus is "one H1 per page". Google has stated
    multiple H1s do not cause ranking issues. Recorded as Contested.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-12", EvidenceWeight.CONTESTED, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    multi = [
        {"url": p.url, "h1_count": len(p.h1)} for p in indexable if len(p.h1) > 1
    ]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-12",
        captured_at=captured_at,
        status=_grade_clean_rate(len(indexable) - len(multi), len(indexable)),
        value={
            "indexable_pages": len(indexable),
            "pages_with_multiple_h1": len(multi),
            "pages_with_multiple_h1_detail": multi,
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-20 — Canonical tag presence and self-reference ──────────────────────


@register_extractor("P1-20")
async def capture_p1_20(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-20 — Canonical tag presence and self-reference (Consensus, 8 rules).

    Implements the per-page subset of the Step 1.5 rules — those that
    can be evaluated from the Instant Pages output alone. Cross-signal
    consistency rules (sitemap match, internal-link target match, GSC
    canonical match) belong to P2-07 (canonicalisation conflicts) and
    are deferred to that variable.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-20", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]

    missing = [p.url for p in indexable if not p.canonical]
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Canonical tag is present on every indexable page",
        passed=len(missing) == 0,
        evidence={
            "indexable_pages_audited": len(indexable),
            "pages_missing_canonical": missing,
        },
    )

    non_absolute = [
        {"url": p.url, "canonical": p.canonical}
        for p in indexable
        if p.canonical and not _is_absolute_url(p.canonical)
    ]
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Canonical URL is absolute (includes scheme and host)",
        passed=len(non_absolute) == 0,
        evidence={"pages_with_non_absolute_canonical": non_absolute},
    )

    cross_ref = [
        {"url": p.url, "canonical": p.canonical}
        for p in indexable
        if p.canonical and not _urls_equivalent(p.canonical, p.url)
    ]
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Primary indexable pages canonicalise to themselves (self-reference)",
        passed=len(cross_ref) == 0,
        evidence={
            "pages_with_canonical_to_other": cross_ref[:50],
            "pages_with_canonical_to_other_count": len(cross_ref),
        },
        notes=(
            "Cross-references can be legitimate for known duplicates; this rule "
            "flags them so a human (or P2-07 canonicalisation conflicts) can "
            "verify the choice is intentional."
        ),
    )

    rules = [rule_1, rule_3, rule_5]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-20",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_missing_canonical": len(missing),
            "pages_canonicalising_elsewhere": len(cross_ref),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.canonical_self_reference_check",
        ],
    )


# ─── P1-16 — URL length ─────────────────────────────────────────────────────


URL_LENGTH_OPTIMAL_HI = 75      # practitioner ceiling for cleanliness
URL_LENGTH_TOO_LONG = 100       # genuinely long


@register_extractor("P1-16")
async def capture_p1_16(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-16 — URL length distribution (Contested).

    Reports per-page URL-length buckets. Google has stated URL length
    is not a direct ranking factor; this is captured for shareability /
    click-through framing rather than as a ranking signal.
    """
    captured_at = _now()
    if not site.urls:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no URLs discovered"},
            rules=None,
            evidence_weight=EvidenceWeight.CONTESTED,
            data_sources=["composition.url_parse"],
        )

    long_urls = [
        {"url": u, "length": len(u)}
        for u in site.urls
        if len(u) > URL_LENGTH_OPTIMAL_HI
    ]
    very_long_urls = [u for u in long_urls if u["length"] > URL_LENGTH_TOO_LONG]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-16",
        captured_at=captured_at,
        status=_grade_clean_rate(len(site.urls) - len(very_long_urls), len(site.urls)),
        value={
            "urls_audited": len(site.urls),
            "above_optimal_count": len(long_urls),
            "very_long_count": len(very_long_urls),
            "very_long_urls": very_long_urls[:50],
            "average_length": round(
                sum(len(u) for u in site.urls) / len(site.urls), 1
            ),
            "thresholds": {
                "optimal_max": URL_LENGTH_OPTIMAL_HI,
                "too_long_above": URL_LENGTH_TOO_LONG,
            },
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=["composition.url_parse"],
    )


# ─── P1-18 — URL path readability ───────────────────────────────────────────


# Patterns used by P1-18.
_RE_HAS_UPPER = re.compile(r"[A-Z]")
_RE_HAS_UNDERSCORE = re.compile(r"_")
_RE_DOUBLE_HYPHEN = re.compile(r"--")
_RE_FILE_EXT = re.compile(r"\.(html?|aspx?|php|cfm|jsp)$", re.IGNORECASE)
_RE_NUMERIC_ONLY = re.compile(r"^[0-9]+$")
_RE_UUID_LIKE = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    re.IGNORECASE,
)


@register_extractor("P1-18")
async def capture_p1_18(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-18 — URL path readability (Probable, 8 Step 1.5 rules)."""
    captured_at = _now()
    if not site.urls:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no URLs discovered"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["composition.url_parse"],
        )

    # Aggregate per-rule violations across all URLs.
    rule_violations: dict[int, list[str]] = {i: [] for i in range(1, 9)}
    for u in site.urls:
        path = urlsplit(u).path or ""
        # Rule 1: all-lowercase
        if _RE_HAS_UPPER.search(path):
            rule_violations[1].append(u)
        # Rule 2: hyphens not underscores
        if _RE_HAS_UNDERSCORE.search(path):
            rule_violations[2].append(u)
        # Rule 3: no double hyphens or trailing hyphens
        if (
            _RE_DOUBLE_HYPHEN.search(path)
            or path.endswith("-")
            or path.startswith("-")
        ):
            rule_violations[3].append(u)
        # Rule 4: no UUIDs
        if _RE_UUID_LIKE.search(path):
            rule_violations[4].append(u)
        # Rule 5: no raw numeric-only slugs (last segment)
        last = path.rstrip("/").rsplit("/", 1)[-1] if path else ""
        if last and _RE_NUMERIC_ONLY.match(last):
            rule_violations[5].append(u)
        # Rule 6: no query-parameter primary URLs
        if urlsplit(u).query:
            rule_violations[6].append(u)
        # Rule 7: no file extensions on content URLs
        if _RE_FILE_EXT.search(path):
            rule_violations[7].append(u)
        # Rule 8: words look real (heuristic: at least one alpha character)
        if last and not re.search(r"[a-zA-Z]", last):
            rule_violations[8].append(u)

    rule_titles = [
        "All-lowercase paths (no mixed case)",
        "Hyphens, not underscores, as word separators",
        "No double hyphens or trailing/leading hyphens",
        "No UUIDs or random hex strings in slugs",
        "No raw numeric-only slugs",
        "No query parameters on primary content URLs",
        "No legacy file extensions (.html, .aspx, .php) on content URLs",
        "Slug words are recognisable (contain at least one alphabetic character)",
    ]
    rules = [
        RuleResult(
            rule_id=i + 1,
            rule_text=rule_titles[i],
            passed=len(rule_violations[i + 1]) == 0,
            evidence={
                "violation_count": len(rule_violations[i + 1]),
                "sample_violations": rule_violations[i + 1][:10],
            },
        )
        for i in range(8)
    ]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-18",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "urls_audited": len(site.urls),
            "total_violations": sum(
                len(v) for v in rule_violations.values()
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["composition.url_parse"],
    )


# ─── P1-19 — URL depth from root ────────────────────────────────────────────


URL_DEPTH_OPTIMAL_MAX = 3       # within ~3 clicks from home
URL_DEPTH_TOO_DEEP = 5


@register_extractor("P1-19")
async def capture_p1_19(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-19 — URL depth from root (Probable, distribution).

    Reports the per-URL path-segment depth distribution. Cross-pillar:
    click-graph depth (the more meaningful measure) lands in P2 work.
    """
    captured_at = _now()
    if not site.urls:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no URLs discovered"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["composition.url_parse"],
        )

    depths: list[int] = []
    too_deep: list[dict[str, Any]] = []
    for u in site.urls:
        path = urlsplit(u).path or "/"
        d = len([s for s in path.split("/") if s])
        depths.append(d)
        if d > URL_DEPTH_TOO_DEEP:
            too_deep.append({"url": u, "depth": d})

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-19",
        captured_at=captured_at,
        status=_grade_clean_rate(len(site.urls) - len(too_deep), len(site.urls)),
        value={
            "urls_audited": len(site.urls),
            "max_depth": max(depths) if depths else 0,
            "average_depth": round(sum(depths) / len(depths), 2)
            if depths
            else 0,
            "depth_histogram": dict(sorted(_histogram(depths).items())),
            "too_deep_count": len(too_deep),
            "too_deep_urls": too_deep[:50],
            "thresholds": {
                "optimal_max": URL_DEPTH_OPTIMAL_MAX,
                "too_deep_above": URL_DEPTH_TOO_DEEP,
            },
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["composition.url_parse"],
    )


# ─── P1-27 — Outbound link count ────────────────────────────────────────────


@register_extractor("P1-27")
async def capture_p1_27(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-27 — Outbound link count distribution (Contested).

    Google has stated outbound link count does not dilute authority
    in the way some practitioner sources claim. Captured for
    completeness; recommendations from this variable should be framed
    as content-quality signal, not link-juice management.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-27", EvidenceWeight.CONTESTED, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    counts = [p.external_links_count for p in indexable]
    pages_with_zero = [p.url for p in indexable if p.external_links_count == 0]
    very_high = [
        {"url": p.url, "external_links_count": p.external_links_count}
        for p in indexable
        if p.external_links_count > 100
    ]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-27",
        captured_at=captured_at,
        # Descriptive only: Google states outbound link COUNT is not a ranking
        # factor and zero-outbound is not inherently bad. Recorded, not graded.
        status=CaptureStatus.NOT_APPLICABLE,
        value={
            "indexable_pages": len(indexable),
            "average_external_links": round(sum(counts) / len(counts), 1)
            if counts
            else 0,
            "max_external_links": max(counts) if counts else 0,
            "pages_with_zero_external_links": pages_with_zero[:50],
            "pages_with_zero_count": len(pages_with_zero),
            "pages_with_high_external_links": very_high[:20],
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-30 — Image dimensions and weight (advisory) ─────────────────────────


@register_extractor("P1-30")
async def capture_p1_30(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-30 — Image counts + size aggregate (Consensus, advisory).

    Records image counts and total weight from DataForSEO. NOTE:
    ``images_size`` requires ``load_resources=true`` to populate; the
    cheap-layer call we make leaves it at 0. Image-weight optimisation
    recommendations therefore need a follow-up audit pass — flagged in
    the value block.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-30", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    image_counts = [p.images_count for p in indexable]
    image_sizes_present = sum(1 for p in indexable if p.images_size_bytes > 0)
    very_image_heavy = [
        {"url": p.url, "images_count": p.images_count}
        for p in indexable
        if p.images_count > 50
    ]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-30",
        captured_at=captured_at,
        status=CaptureStatus.PARTIAL if image_sizes_present == 0 else CaptureStatus.PASSED,
        value={
            "indexable_pages": len(indexable),
            "average_images_per_page": round(
                sum(image_counts) / len(image_counts), 1
            )
            if image_counts
            else 0,
            "max_images_on_a_page": max(image_counts) if image_counts else 0,
            "very_image_heavy_pages": very_image_heavy[:20],
            "image_size_data_available": image_sizes_present > 0,
            "note": (
                "image COUNTS are measured; image SIZE (bytes) needs the full "
                "DataForSEO OnPage Resources crawl. Verified live that Instant "
                "Pages load_resources=true returns images_size=0, so size-based "
                "image-weight diagnostics are not available on this path."
            ),
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
        errors=None
        if image_sizes_present > 0
        else ["images_size unpopulated; image-weight rule not evaluable"],
    )


# ─── P1-31 — Open Graph tags ────────────────────────────────────────────────


_OG_REQUIRED_PROPS = ("og:title", "og:description", "og:image", "og:type", "og:url")
_OG_VALID_TYPES = {
    "website",
    "article",
    "video.movie",
    "video.episode",
    "video.tv_show",
    "video.other",
    "book",
    "profile",
    "music.song",
    "music.album",
    "music.playlist",
    "music.radio_station",
}


@register_extractor("P1-31")
async def capture_p1_31(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-31 — Open Graph tag correctness (Probable, 8 Step 1.5 rules).

    Implements the metadata-only rules; rules requiring live image
    fetches (image dimensions, image-resolves-to-200) are deferred.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-31", EvidenceWeight.PROBABLE, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]

    missing_core: list[dict[str, Any]] = []
    bad_url: list[dict[str, Any]] = []
    bad_type: list[dict[str, Any]] = []
    title_size_issues: list[dict[str, Any]] = []
    desc_size_issues: list[dict[str, Any]] = []
    pages_no_og: list[str] = []

    for p in indexable:
        og = dict(p.og_tags)
        if not og:
            pages_no_og.append(p.url)
            continue
        missing_for_page = [k for k in _OG_REQUIRED_PROPS if k not in og]
        if missing_for_page:
            missing_core.append({"url": p.url, "missing": missing_for_page})

        og_url = og.get("og:url", "")
        if og_url and not _urls_equivalent(og_url, p.url):
            bad_url.append({"url": p.url, "og_url": og_url})

        og_type = og.get("og:type", "")
        if og_type and og_type not in _OG_VALID_TYPES:
            bad_type.append({"url": p.url, "og_type": og_type})

        og_title = og.get("og:title") or ""
        if og_title and (len(og_title) < 20 or len(og_title) > 80):
            title_size_issues.append(
                {"url": p.url, "og_title_length": len(og_title)}
            )
        og_desc = og.get("og:description") or ""
        if og_desc and (len(og_desc) < 50 or len(og_desc) > 250):
            desc_size_issues.append(
                {"url": p.url, "og_description_length": len(og_desc)}
            )

    pages_with_og = len(indexable) - len(pages_no_og)
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Five core OG properties present (og:title, og:description, og:image, og:type, og:url)",
        passed=len(missing_core) == 0 and len(pages_no_og) == 0,
        evidence={
            "indexable_pages": len(indexable),
            "pages_with_og_tags": pages_with_og,
            "pages_without_any_og_tags": pages_no_og[:50],
            "pages_missing_core_props": missing_core[:50],
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="og:url is absolute and self-referential",
        passed=len(bad_url) == 0,
        evidence={"pages_with_mismatched_og_url": bad_url[:50]},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="og:type is one of the canonical OG types",
        passed=len(bad_type) == 0,
        evidence={"pages_with_invalid_og_type": bad_type[:50]},
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="og:title is 20–80 characters",
        passed=len(title_size_issues) == 0,
        evidence={"pages_with_og_title_size_issue": title_size_issues[:50]},
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="og:description is 50–250 characters",
        passed=len(desc_size_issues) == 0,
        evidence={"pages_with_og_description_size_issue": desc_size_issues[:50]},
    )
    rules = [rule_1, rule_3, rule_4, rule_5, rule_6]
    overall_pass = all(r.passed for r in rules)
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-31",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_with_og_tags": pages_with_og,
            "pages_without_any_og_tags": len(pages_no_og),
            "rules_failed": [r.rule_id for r in rules if not r.passed],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-32 — Twitter Card tags ──────────────────────────────────────────────


_TWITTER_CARD_TYPES = {"summary", "summary_large_image", "app", "player"}


@register_extractor("P1-32")
async def capture_p1_32(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-32 — Twitter Card tags (Probable).

    Twitter falls back to Open Graph when Twitter-specific tags are
    absent, so passing OG (P1-31) is acceptable as a fallback per the
    taxonomy. We capture both the explicit Twitter tag presence and
    whether the OG fallback is sufficient.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-32", EvidenceWeight.PROBABLE, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    pages_with_twitter_tags = 0
    pages_with_og_fallback_only = 0
    pages_with_neither = 0
    bad_card_type: list[dict[str, Any]] = []

    for p in indexable:
        tw = dict(p.twitter_tags)
        og = dict(p.og_tags)
        has_twitter = bool(tw)
        has_og = bool(og)
        if has_twitter:
            pages_with_twitter_tags += 1
            card_type = tw.get("twitter:card", "")
            if card_type and card_type not in _TWITTER_CARD_TYPES:
                bad_card_type.append({"url": p.url, "twitter:card": card_type})
        elif has_og:
            pages_with_og_fallback_only += 1
        else:
            pages_with_neither += 1

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-32",
        captured_at=captured_at,
        # Probable + advisory: the ecosystem accepts OG fallback so a
        # page with OG only is fine. Only "neither" is a true failure.
        status=CaptureStatus.PASSED
        if pages_with_neither == 0 and len(bad_card_type) == 0
        else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_with_explicit_twitter_tags": pages_with_twitter_tags,
            "pages_relying_on_og_fallback": pages_with_og_fallback_only,
            "pages_with_neither": pages_with_neither,
            "pages_with_invalid_twitter_card_type": bad_card_type[:50],
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-33 — Robots meta tag ────────────────────────────────────────────────


@register_extractor("P1-33")
async def capture_p1_33(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-33 — Robots meta tag correctness (Consensus).

    Captures the per-page robots directive. Rules requiring
    cross-signal verification (X-Robots-Tag header, robots.txt
    consistency, GSC URL Inspection match) belong to P2-04 indexation
    status and are deferred to that variable.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-33", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    accidental_noindex: list[str] = []
    pages_with_robots: list[dict[str, Any]] = []
    for p in indexable:
        if p.meta_robots:
            pages_with_robots.append({"url": p.url, "robots": p.meta_robots})
            if "noindex" in p.meta_robots.lower():
                accidental_noindex.append(p.url)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No accidental noindex on indexable pages",
        passed=len(accidental_noindex) == 0,
        evidence={
            "pages_with_noindex_but_classified_indexable": accidental_noindex,
        },
        notes=(
            "Indexability is computed from status, redirect, and noindex "
            "directives; this rule double-checks the classification by "
            "scanning robots meta directly."
        ),
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-33",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_with_robots_directive": len(pages_with_robots),
            "robots_directives_sampled": pages_with_robots[:20],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-34 — Content depth / word count ─────────────────────────────────────


WORD_COUNT_THIN_BELOW = 150
WORD_COUNT_OPTIMAL_LO = 600
WORD_COUNT_OPTIMAL_HI = 2500


@register_extractor("P1-34")
async def capture_p1_34(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-34 — Content depth / word count (Probable, distribution).

    Word count itself is not a Google-endorsed ranking factor; it's
    captured here as a proxy for topical depth. Comparison against
    SERP-competitor average belongs to P4-08 and lands later.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-34", EvidenceWeight.PROBABLE, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    counts = [p.plain_text_word_count for p in indexable]
    thin = [
        {"url": p.url, "word_count": p.plain_text_word_count}
        for p in indexable
        if p.plain_text_word_count < WORD_COUNT_THIN_BELOW
    ]
    in_optimal = [
        p.url
        for p in indexable
        if WORD_COUNT_OPTIMAL_LO
        <= p.plain_text_word_count
        <= WORD_COUNT_OPTIMAL_HI
    ]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-34",
        captured_at=captured_at,
        status=_grade_clean_rate(len(indexable) - len(thin), len(indexable)),
        value={
            "indexable_pages": len(indexable),
            "average_word_count": round(sum(counts) / len(counts), 0)
            if counts
            else 0,
            "median_word_count": _median(counts),
            "thin_content_count": len(thin),
            "thin_content_pages": thin[:50],
            "in_optimal_range": len(in_optimal),
            "thresholds": {
                "thin_below": WORD_COUNT_THIN_BELOW,
                "optimal_lo": WORD_COUNT_OPTIMAL_LO,
                "optimal_hi": WORD_COUNT_OPTIMAL_HI,
            },
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-51 — Reading level / readability ────────────────────────────────────


@register_extractor("P1-51")
async def capture_p1_51(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-51 — Reading level / readability (Probable, 5 indices).

    Reports the Flesch-Kincaid, Coleman-Liau, Dale-Chall, SMOG, and
    Automated Readability indices per page plus per-site averages.
    No pass/fail — appropriate level depends on audience (consumer
    blog vs technical documentation).
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-51", EvidenceWeight.PROBABLE, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]

    def _avg(values: list[float | None]) -> float | None:
        clean = [v for v in values if v is not None]
        if not clean:
            return None
        return round(sum(clean) / len(clean), 2)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-51",
        captured_at=captured_at,
        # Descriptive only: appropriate reading level is audience-dependent
        # (consumer blog vs technical docs); no universal pass/fail bar.
        status=CaptureStatus.NOT_APPLICABLE,
        value={
            "indexable_pages": len(indexable),
            "site_averages": {
                "flesch_kincaid": _avg([p.flesch_kincaid for p in indexable]),
                "coleman_liau": _avg([p.coleman_liau for p in indexable]),
                "dale_chall": _avg([p.dale_chall for p in indexable]),
                "smog": _avg([p.smog for p in indexable]),
                "automated_readability": _avg(
                    [p.automated_readability for p in indexable]
                ),
            },
            "interpretation_note": (
                "Flesch-Kincaid lower = easier (target ~60–70 for general "
                "consumer copy, ~30–50 for technical content). The other "
                "four indices report grade level (lower = easier)."
            ),
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P1-52 — Grammar and spelling ───────────────────────────────────────────


@register_extractor("P1-52")
async def capture_p1_52(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P1-52 — Spelling errors (Consensus, narrowed).

    DataForSEO's Hunspell-based ``meta.spell.misspelled`` is what we
    have access to at this layer. Grammar (LanguageTool) is deferred
    until H1c LLM-evaluation layer where we already pay for an LLM
    pass over content.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable_when_no_audits(
            ctx, site, "P1-52", EvidenceWeight.CONSENSUS, captured_at
        )

    indexable = [p for p in audits if p.is_indexable]
    pages_with_misspellings: list[dict[str, Any]] = []
    for p in indexable:
        if p.misspelled_words:
            pages_with_misspellings.append(
                {
                    "url": p.url,
                    "language": p.spell_language,
                    "misspelled_count": len(p.misspelled_words),
                    "sample": list(p.misspelled_words)[:10],
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Pages have no detected spelling errors (Hunspell)",
        passed=len(pages_with_misspellings) == 0,
        evidence={
            "pages_with_misspellings_count": len(pages_with_misspellings),
            "pages_with_misspellings": pages_with_misspellings[:50],
        },
        notes=(
            "Hunspell is dictionary-based and produces false positives on "
            "brand names, technical jargon, and capitalised acronyms. "
            "Grammar checks are deferred to H1c LLM-evaluation layer."
        ),
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-52",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "indexable_pages": len(indexable),
            "pages_with_misspellings": len(pages_with_misspellings),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── Local helpers ──────────────────────────────────────────────────────────


def _has_title(p: PageAudit) -> bool:
    return p.title is not None and p.title != ""


def _has_description(p: PageAudit) -> bool:
    return p.description is not None and p.description.strip() != ""


def _is_absolute_url(url: str) -> bool:
    parts = urlsplit(url)
    return bool(parts.scheme and parts.netloc)


def _urls_equivalent(a: str, b: str) -> bool:
    """Compare two URLs ignoring trailing slash and case-folding the host."""
    pa, pb = urlsplit(a), urlsplit(b)
    return (
        pa.scheme.lower() == pb.scheme.lower()
        and pa.netloc.lower() == pb.netloc.lower()
        and pa.path.rstrip("/") == pb.path.rstrip("/")
        and pa.query == pb.query
    )


def _histogram(values: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def _median(values: list[int]) -> int | float:
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


# ─── P1-23 — Internal link inbound count ────────────────────────────────────

# Inbound-link thresholds. Practitioners commonly cite "a page should
# have at least one or two inbound internal links" as the floor for
# discoverability; higher counts indicate more authority concentration.
# Recorded as Consensus because the underlying mechanism (Google uses
# internal-link graph for PageRank-style authority computation) is
# documented in Google's own guidance and the 2024 Content Warehouse
# leak's `pageRankNS` feature names.
INBOUND_FLOOR = 1
INBOUND_HEALTHY = 3


@register_extractor("P1-23")
async def capture_p1_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-23 — Internal link inbound count (Consensus, link-graph composition).

    For every page in the link graph, counts the number of internal
    links pointing to it from other pages on the same site. Reports
    distribution + per-page list with thresholds. Excludes the
    homepage from the inbound floor check because the homepage's
    internal inbound count is often zero by design (the entry point).
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-23",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available — HTML prefetch empty"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "composition.link_graph_inbound_count"],
            errors=["site.link_graph is None or empty"],
        )

    primary_canonical = _canonical_homepage(site)
    per_page_counts: list[tuple[str, int]] = []
    pages_below_floor: list[str] = []
    pages_at_zero: list[str] = []

    for url in sorted(site.link_graph.pages):
        count = site.link_graph.inbound_count(url)
        per_page_counts.append((url, count))
        if url == primary_canonical:
            continue  # homepage exempt from the floor check
        if count == 0:
            pages_at_zero.append(url)
        if count < INBOUND_FLOOR:
            pages_below_floor.append(url)

    counts_only = [c for _, c in per_page_counts]
    avg = (sum(counts_only) / len(counts_only)) if counts_only else 0.0
    max_count = max(counts_only) if counts_only else 0
    median = _median(counts_only)
    healthy_count = sum(1 for c in counts_only if c >= INBOUND_HEALTHY)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every non-homepage page has at least one internal link pointing to it",
        passed=len(pages_below_floor) == 0,
        evidence={
            "pages_below_floor": pages_below_floor[:50],
            "below_floor_count": len(pages_below_floor),
            "floor_threshold": INBOUND_FLOOR,
            "homepage_exempt": primary_canonical,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Inbound-link distribution is non-degenerate (at least one page receives 3+ inbound links)",
        passed=healthy_count > 0,
        evidence={
            "pages_with_healthy_inbound": healthy_count,
            "healthy_threshold": INBOUND_HEALTHY,
            "max_inbound_count": max_count,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Pages with zero internal inbound links are flagged for review",
        passed=True,
        evidence={
            "pages_at_zero_inbound": pages_at_zero[:50],
            "pages_at_zero_count": len(pages_at_zero),
        },
        notes="Advisory: zero-inbound pages either need link integration or shouldn't be in the audit set.",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    # Top 10 most-linked pages — useful evidence for human reviewers.
    top_inbound = sorted(per_page_counts, key=lambda t: t[1], reverse=True)[:10]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_in_graph": site.link_graph.page_count,
            "avg_inbound": round(avg, 2),
            "median_inbound": median,
            "max_inbound": max_count,
            "pages_below_floor_count": len(pages_below_floor),
            "pages_at_zero_count": len(pages_at_zero),
            "healthy_inbound_count": healthy_count,
            "top_10_most_linked": [
                {"url": u, "inbound": c} for u, c in top_inbound
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.link_graph_inbound_count"],
    )


def _canonical_homepage(site: SiteData) -> str:
    """Find the homepage entry in the link graph, accounting for www / trailing-slash."""
    if site.link_graph is None:
        return ""
    from urllib.parse import urlsplit
    target_parts = urlsplit(site.primary_url)
    target_host = (target_parts.netloc or "").lower().removeprefix("www.")
    target_path = (target_parts.path or "/").rstrip("/") or "/"
    for url in site.link_graph.pages:
        p = urlsplit(url)
        if (p.netloc or "").lower().removeprefix("www.") == target_host:
            path = (p.path or "/").rstrip("/") or "/"
            if path == target_path:
                return url
    return ""


# ─── P1-37 — Entity match score ─────────────────────────────────────────────


@register_extractor("P1-37")
async def capture_p1_37(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-37 — Entity match score (Probable).

    Approximates the per-page entity-match signal via the existing
    ``topic_depth`` LLM evaluator, which (per page) asks Claude to:
    1. Identify the page's primary topic
    2. Enumerate 5-8 canonical subtopics for that topic
    3. Mark which subtopics the page actually addresses substantively

    Subtopics ARE entities for the page's topic. ``coverage_pct``
    (subtopics-covered / canonical-subtopics × 100) is the entity
    match score. Pages with low coverage are missing entities the
    target query implies.

    Pass: site median entity-match coverage_pct >= 70 across
    evaluated pages (taxonomy doesn't specify a hard threshold;
    70 mirrors the existing TopicDepth pass criterion).

    Note: taxonomy's P1-37 specifies entity-match against a
    target-query entity set. Our composition uses the page's
    OWN canonical-subtopic set as ground truth, which is a related
    but narrower signal. True per-query entity match requires
    Knowledge Graph lookup per ranked keyword + LLM extraction of
    page entities — flagged as a future extension.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("topic_depth", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no long-form pages (>=400 words on /blog/, /article/, /guide/ paths) for topic_depth eval"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-37",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create", "composition.topic_depth_evaluator"],
            errors=[reason],
        )

    coverages: list[int] = []
    page_findings: list[dict[str, Any]] = []
    errored_count = 0
    for url, ev in evals.items():
        if ev.error or ev.raw is None:
            errored_count += 1
            continue
        raw = ev.raw or {}
        coverage_pct = raw.get("coverage_pct")
        if not isinstance(coverage_pct, (int, float)):
            errored_count += 1
            continue
        coverages.append(int(coverage_pct))
        page_findings.append(
            {
                "url": url,
                "primary_topic": raw.get("primary_topic"),
                "coverage_pct": int(coverage_pct),
                "canonical_subtopics": raw.get("canonical_subtopics", []),
                "subtopics_covered": raw.get("subtopics_covered", []),
                "subtopics_missing": [
                    s for s in (raw.get("canonical_subtopics") or [])
                    if s not in (raw.get("subtopics_covered") or [])
                ],
                "confidence": ev.confidence,
            }
        )

    if not coverages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-37",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no usable topic_depth eval results",
                "errored_count": errored_count,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create"],
            errors=["no parseable coverage_pct"],
        )

    sorted_cov = sorted(coverages)
    median_cov = sorted_cov[len(sorted_cov) // 2]
    mean_cov = round(sum(coverages) / len(coverages), 1)
    weak_pages = sorted(page_findings, key=lambda p: p["coverage_pct"])[:10]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site median entity-match coverage_pct >= 70",
        passed=median_cov >= 70,
        evidence={
            "median_coverage_pct": median_cov,
            "mean_coverage_pct": mean_cov,
            "pages_evaluated": len(coverages),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 25% of pages have coverage_pct < 50 (severe entity gap)",
        passed=(
            len([c for c in coverages if c < 50]) / len(coverages) <= 0.25
        ),
        evidence={
            "severe_gap_count": len([c for c in coverages if c < 50]),
            "severe_gap_pct": round(
                len([c for c in coverages if c < 50]) / len(coverages) * 100, 1
            ),
            "weakest_pages": weak_pages[:5],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-37",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(coverages),
            "median_coverage_pct": median_cov,
            "mean_coverage_pct": mean_cov,
            "weakest_pages": weak_pages,
            "note": (
                "Reuses topic_depth evaluator's subtopic coverage as proxy "
                "for entity match. Subtopics are page-own canonical entities; "
                "true per-query entity match would need KG-driven entity set "
                "per ranked keyword + LLM extraction of page entities. The "
                "current signal is honest about what it measures."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.topic_depth_evaluator",
        ],
    )


# ─── P1-10 — Snippet prefix character count ────────────────────────────────


@register_extractor("P1-10")
async def capture_p1_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-10 — Snippet prefix character count (Speculative, leak feature).

    Approximates the leaked Google ``snippetPrefixCharCount`` by
    reading the actual SERP snippet text Google renders for each
    ranked page. From each prefetched SERP, find the organic row that
    matches our domain (if present) and measure its snippet length.

    Pass: every queried keyword where our domain ranks has a snippet
    prefix length recorded. (Watchlist variable — taxonomy notes this
    is a leak-feature approximation, not a Google-endorsed ranking
    signal. Recorded for completeness.)
    """
    captured_at = _now()
    serps = site.serp_results or {}
    if not serps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERP prefetch results available"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["serp.google.organic"],
            errors=["no SERPs"],
        )

    our_host = site.domain.lower().removeprefix("www.")
    findings: list[dict[str, Any]] = []
    lengths: list[int] = []
    queries_with_us: list[str] = []
    queries_without_us: list[str] = []
    for kw, result in serps.items():
        items = result.get("items") or []
        our_row = None
        for item in items:
            if item.get("type") != "organic":
                continue
            domain = (item.get("domain") or "").lower().removeprefix("www.")
            if our_host in domain:
                our_row = item
                break
        if our_row is None:
            queries_without_us.append(kw)
            continue
        queries_with_us.append(kw)
        snippet = (our_row.get("description") or our_row.get("snippet") or "").strip()
        snippet_len = len(snippet)
        lengths.append(snippet_len)
        findings.append(
            {
                "keyword": kw,
                "ranking_url": our_row.get("url"),
                "rank_absolute": our_row.get("rank_absolute"),
                "snippet_chars": snippet_len,
                "snippet_text": snippet[:160] + ("..." if snippet_len > 160 else ""),
            }
        )

    if not lengths:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "site does not rank in top organic results for any queried keyword",
                "queries_attempted": len(serps),
                "queries_without_us": queries_without_us,
            },
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["serp.google.organic"],
            errors=["no ranking matches"],
        )

    sorted_l = sorted(lengths)
    median = sorted_l[len(sorted_l) // 2]
    mean = round(sum(lengths) / len(lengths), 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Snippet prefix length recorded for every keyword where the site ranks",
        passed=len(findings) > 0,
        evidence={
            "queries_with_recorded_snippet": len(findings),
            "queries_we_dont_rank_on": len(queries_without_us),
        },
        notes="Speculative leak-feature approximation; recorded for completeness, not used for operational scoring per taxonomy.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-10",
        captured_at=captured_at,
        # Descriptive only: a leaked-feature approximation the taxonomy marks as
        # non-operational. Snippet length recorded, not graded pass/fail.
        status=CaptureStatus.NOT_APPLICABLE,
        value={
            "queries_with_ranking_snippet": len(findings),
            "queries_we_dont_rank_on_count": len(queries_without_us),
            "median_snippet_chars": median,
            "mean_snippet_chars": mean,
            "min_snippet_chars": sorted_l[0],
            "max_snippet_chars": sorted_l[-1],
            "findings": findings[:15],
            "watchlist": True,
            "note": (
                "Watchlist per taxonomy — leak-feature approximation, "
                "no Tier-A endorsement of snippet prefix length as a "
                "ranking signal. Recorded for completeness."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=["serp.google.organic", "composition.snippet_prefix_measurement"],
    )
