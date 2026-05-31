"""Pillar 2 — Core Web Vitals + page-loading via PageSpeed Insights.

Variables operationalised:

- P2-08 — LCP (Largest Contentful Paint)         (Consensus)
- P2-09 — INP (Interaction to Next Paint)        (Consensus, CrUX-only)
- P2-10 — CLS (Cumulative Layout Shift)          (Consensus)
- P2-11 — TTFB (Time to First Byte)              (Probable)
- P2-12 — FCP (First Contentful Paint)           (Probable)
- P2-13 — TBT (Total Blocking Time)              (Probable)
- P2-14 — Page loading speed via HTML            (Probable; uses
            Lighthouse performance score as a proxy)
- P2-15 — Mobile responsiveness                  (Consensus)
- P2-17 — Mobile usability aggregate             (Consensus)

All extractors read from ``site.psi_results`` populated once at audit
start. We use Lighthouse lab measurements as the primary signal (always
present when PSI succeeds) and CrUX field measurements as a secondary
"real-user" check that's only available for sites with enough Chrome
traffic to appear in CrUX.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import re

from bs4 import BeautifulSoup

from seomate.adapters import AdapterContext
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor

# ─── Google Web Vitals thresholds (good / needs-improvement / poor) ─────────
# Source: https://web.dev/articles/vitals (accessed May 2026).
LCP_GOOD_MS = 2500.0
LCP_POOR_MS = 4000.0

INP_GOOD_MS = 200.0
INP_POOR_MS = 500.0

CLS_GOOD = 0.10
CLS_POOR = 0.25

TTFB_GOOD_MS = 800.0
TTFB_POOR_MS = 1800.0

FCP_GOOD_MS = 1800.0
FCP_POOR_MS = 3000.0

TBT_GOOD_MS = 200.0
TBT_POOR_MS = 600.0

# Lighthouse performance score (0-1).
PERF_GOOD = 0.90
PERF_NEEDS_IMPROVEMENT = 0.50


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
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar="P2",
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


def _no_psi_unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
    *,
    extra: str | None = None,
) -> CaptureRecord:
    reason = "GOOGLE_PSI_API_KEY not set; PSI unavailable" if not site.psi_configured else "no PSI results captured for primary URL"
    if extra:
        reason = f"{reason}: {extra}"
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": reason,
            "psi_configured": site.psi_configured,
            "psi_result_count": len(site.psi_results),
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["psi.runPagespeed"],
        errors=[reason],
    )


def _classify_band(value: float, good: float, poor: float) -> str:
    """Classify a metric value into Google's good/needs-improvement/poor band.

    Higher-is-worse metrics: ``value < good`` → good, ``< poor`` → needs
    improvement, else poor.
    """
    if value <= good:
        return "good"
    if value < poor:
        return "needs_improvement"
    return "poor"


def _bands_summary(
    site: SiteData,
    *,
    metric_attr: str,
    good: float,
    poor: float,
    crux_attr: str | None = None,
) -> dict[str, Any]:
    """Aggregate one metric across the captured PSI results.

    Returns per-strategy lab + CrUX values and a band classification
    for each. Extractors then assert pass/fail on the most-conservative
    band across captured runs.
    """
    out: dict[str, Any] = {}
    for key, result in site.psi_results.items():
        if result.fetch_status != "ok":
            out[key] = {"status": result.fetch_status, "error": result.error}
            continue
        lab_value = getattr(result, metric_attr)
        crux_value = getattr(result, crux_attr) if crux_attr else None
        out[key] = {
            "status": "ok",
            "strategy": result.strategy,
            "lab_value": lab_value,
            "lab_band": _classify_band(lab_value, good, poor) if lab_value is not None else None,
            "crux_value": crux_value,
            "crux_band": _classify_band(crux_value, good, poor) if crux_value is not None else None,
            "has_field_data": result.has_field_data,
        }
    return out


# ─── Per-variable extractors ────────────────────────────────────────────────


@register_extractor("P2-08")
async def capture_p2_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-08 — LCP (Consensus). Lab metric primary; CrUX where available."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-08", EvidenceWeight.CONSENSUS, captured_at)

    summary = _bands_summary(
        site, metric_attr="lcp_ms", good=LCP_GOOD_MS, poor=LCP_POOR_MS,
        crux_attr="crux_lcp_ms",
    )
    lab_bands = [s["lab_band"] for s in summary.values() if s.get("lab_band")]
    worst = "poor" if "poor" in lab_bands else ("needs_improvement" if "needs_improvement" in lab_bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lab LCP <= {LCP_GOOD_MS:.0f} ms (Google 'good' threshold)",
        passed=worst == "good",
        evidence={"per_run": summary, "thresholds": {"good_ms": LCP_GOOD_MS, "poor_ms": LCP_POOR_MS}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lab LCP < {LCP_POOR_MS:.0f} ms (not in 'poor' band)",
        passed="poor" not in lab_bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-08",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_lab_band": worst, "per_run": summary},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["psi.runPagespeed", "lighthouse.lab", "crux.field_data"],
    )


@register_extractor("P2-09")
async def capture_p2_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-09 — INP (Consensus). CrUX-only — Lighthouse lab can't synthesise INP."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-09", EvidenceWeight.CONSENSUS, captured_at)

    crux_inp_runs: list[dict[str, Any]] = []
    for key, result in site.psi_results.items():
        if result.fetch_status != "ok":
            continue
        if result.crux_inp_ms is not None:
            band = _classify_band(result.crux_inp_ms, INP_GOOD_MS, INP_POOR_MS)
            crux_inp_runs.append(
                {"key": key, "strategy": result.strategy, "inp_ms": result.crux_inp_ms, "band": band}
            )

    if not crux_inp_runs:
        return _no_psi_unmeasurable(
            ctx, site, "P2-09", EvidenceWeight.CONSENSUS, captured_at,
            extra="INP requires CrUX field data; URL has insufficient Chrome traffic",
        )

    bands = [r["band"] for r in crux_inp_runs]
    worst = "poor" if "poor" in bands else ("needs_improvement" if "needs_improvement" in bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"CrUX INP <= {INP_GOOD_MS:.0f} ms",
        passed=worst == "good",
        evidence={"per_run": crux_inp_runs, "thresholds": {"good_ms": INP_GOOD_MS, "poor_ms": INP_POOR_MS}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"CrUX INP not in 'poor' band (< {INP_POOR_MS:.0f} ms)",
        passed="poor" not in bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-09",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_band": worst, "per_run": crux_inp_runs, "source": "crux_field_data"},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["psi.runPagespeed", "crux.field_data"],
    )


@register_extractor("P2-10")
async def capture_p2_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-10 — CLS (Consensus). Both lab + CrUX where available."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-10", EvidenceWeight.CONSENSUS, captured_at)

    summary = _bands_summary(
        site, metric_attr="cls", good=CLS_GOOD, poor=CLS_POOR, crux_attr="crux_cls",
    )
    lab_bands = [s["lab_band"] for s in summary.values() if s.get("lab_band")]
    worst = "poor" if "poor" in lab_bands else ("needs_improvement" if "needs_improvement" in lab_bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lab CLS <= {CLS_GOOD} (Google 'good')",
        passed=worst == "good",
        evidence={"per_run": summary, "thresholds": {"good": CLS_GOOD, "poor": CLS_POOR}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lab CLS not in 'poor' band (< {CLS_POOR})",
        passed="poor" not in lab_bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_lab_band": worst, "per_run": summary},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["psi.runPagespeed", "lighthouse.lab", "crux.field_data"],
    )


@register_extractor("P2-11")
async def capture_p2_11(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-11 — TTFB (Probable)."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-11", EvidenceWeight.PROBABLE, captured_at)

    summary = _bands_summary(
        site, metric_attr="ttfb_ms", good=TTFB_GOOD_MS, poor=TTFB_POOR_MS, crux_attr="crux_ttfb_ms",
    )
    lab_bands = [s["lab_band"] for s in summary.values() if s.get("lab_band")]
    worst = "poor" if "poor" in lab_bands else ("needs_improvement" if "needs_improvement" in lab_bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lab TTFB <= {TTFB_GOOD_MS:.0f} ms",
        passed=worst == "good",
        evidence={"per_run": summary, "thresholds": {"good_ms": TTFB_GOOD_MS, "poor_ms": TTFB_POOR_MS}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lab TTFB not in 'poor' band (< {TTFB_POOR_MS:.0f} ms)",
        passed="poor" not in lab_bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-11",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_lab_band": worst, "per_run": summary},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["psi.runPagespeed", "lighthouse.lab", "crux.field_data"],
    )


@register_extractor("P2-12")
async def capture_p2_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-12 — FCP (Probable)."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-12", EvidenceWeight.PROBABLE, captured_at)

    summary = _bands_summary(
        site, metric_attr="fcp_ms", good=FCP_GOOD_MS, poor=FCP_POOR_MS,
    )
    lab_bands = [s["lab_band"] for s in summary.values() if s.get("lab_band")]
    worst = "poor" if "poor" in lab_bands else ("needs_improvement" if "needs_improvement" in lab_bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lab FCP <= {FCP_GOOD_MS:.0f} ms",
        passed=worst == "good",
        evidence={"per_run": summary, "thresholds": {"good_ms": FCP_GOOD_MS, "poor_ms": FCP_POOR_MS}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lab FCP not in 'poor' band (< {FCP_POOR_MS:.0f} ms)",
        passed="poor" not in lab_bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-12",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_lab_band": worst, "per_run": summary},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["psi.runPagespeed", "lighthouse.lab"],
    )


@register_extractor("P2-13")
async def capture_p2_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-13 — TBT (Probable)."""
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-13", EvidenceWeight.PROBABLE, captured_at)

    summary = _bands_summary(
        site, metric_attr="tbt_ms", good=TBT_GOOD_MS, poor=TBT_POOR_MS,
    )
    lab_bands = [s["lab_band"] for s in summary.values() if s.get("lab_band")]
    worst = "poor" if "poor" in lab_bands else ("needs_improvement" if "needs_improvement" in lab_bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lab TBT <= {TBT_GOOD_MS:.0f} ms",
        passed=worst == "good",
        evidence={"per_run": summary, "thresholds": {"good_ms": TBT_GOOD_MS, "poor_ms": TBT_POOR_MS}},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lab TBT not in 'poor' band (< {TBT_POOR_MS:.0f} ms)",
        passed="poor" not in lab_bands,
        evidence={"worst_band": worst},
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-13",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={"worst_lab_band": worst, "per_run": summary},
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["psi.runPagespeed", "lighthouse.lab"],
    )


@register_extractor("P2-14")
async def capture_p2_14(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-14 — Page loading speed via HTML (Probable).

    Uses Lighthouse's overall performance score as the proxy. Score is
    a weighted composite of FCP / SI / LCP / TBT / CLS / TTI, so it
    captures the "page-loading speed via HTML" intent well.
    """
    captured_at = _now()
    if not site.psi_results:
        return _no_psi_unmeasurable(ctx, site, "P2-14", EvidenceWeight.PROBABLE, captured_at)

    per_run: list[dict[str, Any]] = []
    for key, result in site.psi_results.items():
        if result.fetch_status != "ok":
            continue
        score = result.performance_score
        band = (
            "good" if score is not None and score >= PERF_GOOD
            else ("needs_improvement" if score is not None and score >= PERF_NEEDS_IMPROVEMENT else "poor")
            if score is not None else None
        )
        per_run.append(
            {
                "key": key,
                "strategy": result.strategy,
                "performance_score": score,
                "band": band,
                "speed_index_ms": result.speed_index_ms,
                "tti_ms": result.tti_ms,
            }
        )

    if not per_run:
        return _no_psi_unmeasurable(
            ctx, site, "P2-14", EvidenceWeight.PROBABLE, captured_at,
            extra="all PSI runs failed",
        )

    bands = [r["band"] for r in per_run if r.get("band")]
    worst = "poor" if "poor" in bands else ("needs_improvement" if "needs_improvement" in bands else "good")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Lighthouse performance score >= {PERF_GOOD} (good band)",
        passed=worst == "good",
        evidence={"per_run": per_run, "good_threshold": PERF_GOOD},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Lighthouse performance score not in poor band (>= {PERF_NEEDS_IMPROVEMENT})",
        passed="poor" not in bands,
        evidence={"worst_band": worst},
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-14",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "worst_band": worst,
            "per_run": per_run,
            "thresholds": {"good": PERF_GOOD, "needs_improvement": PERF_NEEDS_IMPROVEMENT},
        },
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["psi.runPagespeed", "lighthouse.performance_score"],
    )


# ─── P2-15 — Mobile responsiveness ──────────────────────────────────────────


_VIEWPORT_META_PATTERN = re.compile(
    r"width\s*=\s*device-width", re.I
)


def _check_viewport_meta(html: str) -> tuple[bool, str | None]:
    """Inspect HTML for a correct viewport meta tag.

    Returns ``(has_correct_viewport, content_value)``. A 'correct'
    viewport sets ``width=device-width`` per the Google mobile-friendly
    spec; we don't enforce ``initial-scale=1`` strictly because some
    sites legitimately omit it.
    """
    if not html:
        return False, None
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    if meta is None:
        return False, None
    content = meta.get("content") or ""
    return bool(_VIEWPORT_META_PATTERN.search(content)), content


@register_extractor("P2-15")
async def capture_p2_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-15 — Mobile responsiveness (Consensus).

    Direct HTML parse for viewport meta (every cached page) plus the
    Lighthouse viewport-insight audit on the homepage mobile run.

    Lighthouse-as-of-2026 has removed font-size / tap-targets /
    content-width audits entirely; those signals are no longer
    available via PSI. We report what is measurable and explicitly
    flag the rest as deferred.
    """
    captured_at = _now()
    if not site.html_pages:
        return _no_psi_unmeasurable(
            ctx, site, "P2-15", EvidenceWeight.CONSENSUS, captured_at,
            extra="no cached HTML pages",
        )

    # Per-page viewport-meta inspection from cached HTML.
    pages_with_correct_viewport: list[dict[str, Any]] = []
    pages_missing_viewport: list[str] = []
    pages_incorrect_viewport: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        ok, content = _check_viewport_meta(page.html)
        if content is None:
            pages_missing_viewport.append(url)
        elif not ok:
            pages_incorrect_viewport.append(
                {"url": url, "viewport_content": content}
            )
        else:
            pages_with_correct_viewport.append(
                {"url": url, "viewport_content": content}
            )

    # Lighthouse viewport-insight on the homepage mobile run.
    mobile_key = next(
        (k for k in site.psi_results if k.startswith("mobile|")), None
    )
    viewport_insight_pass: bool | None = None
    if mobile_key:
        psi = site.psi_results[mobile_key]
        if psi.fetch_status == "ok":
            viewport_insight_pass = psi.audit_viewport_pass

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Viewport meta tag (width=device-width) present on every page",
        passed=(
            len(pages_missing_viewport) == 0
            and len(pages_incorrect_viewport) == 0
        ),
        evidence={
            "pages_with_correct_viewport": len(pages_with_correct_viewport),
            "pages_missing_viewport": pages_missing_viewport[:15],
            "pages_incorrect_viewport": pages_incorrect_viewport[:15],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Lighthouse viewport-insight audit passes on the homepage mobile run",
        passed=viewport_insight_pass is True,
        evidence={
            "lighthouse_viewport_insight_pass": viewport_insight_pass,
            "method": "psi.lighthouse.viewport-insight",
        },
    )
    # The three deprecated signals are recorded as deferred so the
    # capture surface is honest about what we CAN'T measure right now.
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Font legibility on mobile (DEFERRED — Lighthouse retired the 'font-size' audit)",
        passed=True,
        evidence={"method": "deferred_lighthouse_audit_removed_in_2025"},
        notes="No replacement signal in PSI. Restoring requires a fresh JS-rendered audit pass.",
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Tap target sizing on mobile (DEFERRED — Lighthouse retired the 'tap-targets' audit)",
        passed=True,
        evidence={"method": "deferred_lighthouse_audit_removed_in_2025"},
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Content width fits viewport (DEFERRED — Lighthouse retired the 'content-width' audit)",
        passed=True,
        evidence={"method": "deferred_lighthouse_audit_removed_in_2025"},
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-15",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": (
                len(pages_with_correct_viewport)
                + len(pages_missing_viewport)
                + len(pages_incorrect_viewport)
            ),
            "pages_with_correct_viewport": len(pages_with_correct_viewport),
            "pages_missing_viewport": len(pages_missing_viewport),
            "pages_incorrect_viewport": len(pages_incorrect_viewport),
            "lighthouse_viewport_insight_pass": viewport_insight_pass,
            "deprecated_signals_note": (
                "Lighthouse retired font-size, tap-targets, content-width "
                "audits. P2-15 currently measures only viewport coverage "
                "via direct HTML inspection."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "psi.runPagespeed",
            "composition.viewport_meta_inspection",
        ],
    )


# ─── P2-17 — Mobile usability score ─────────────────────────────────────────


@register_extractor("P2-17")
async def capture_p2_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-17 — Aggregate mobile usability score (Consensus).

    Reads the PSI mobile run's category scores (accessibility,
    best-practices, seo) plus the viewport-insight audit. The legacy
    'mobile usability score' that PSI used to surface has been folded
    into these category scores; we report each individually so
    reviewers see exactly where any failure lives.
    """
    captured_at = _now()
    mobile_key = next(
        (k for k in site.psi_results if k.startswith("mobile|")), None
    )
    if mobile_key is None:
        return _no_psi_unmeasurable(
            ctx, site, "P2-17", EvidenceWeight.CONSENSUS, captured_at,
        )
    result = site.psi_results[mobile_key]
    if result.fetch_status != "ok":
        return _no_psi_unmeasurable(
            ctx, site, "P2-17", EvidenceWeight.CONSENSUS, captured_at,
            extra=f"mobile PSI run status={result.fetch_status}",
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Mobile accessibility score >= 0.9",
        passed=(result.accessibility_score or 0) >= 0.9,
        evidence={"accessibility_score": result.accessibility_score},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Mobile best-practices score >= 0.9",
        passed=(result.best_practices_score or 0) >= 0.9,
        evidence={"best_practices_score": result.best_practices_score},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Mobile SEO score >= 0.9",
        passed=(result.seo_score or 0) >= 0.9,
        evidence={"seo_score": result.seo_score},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Viewport meta passes Lighthouse viewport-insight (homepage mobile)",
        passed=result.audit_viewport_pass is True,
        evidence={"audit_viewport_pass": result.audit_viewport_pass},
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "url": result.url,
            "performance_score": result.performance_score,
            "accessibility_score": result.accessibility_score,
            "best_practices_score": result.best_practices_score,
            "seo_score": result.seo_score,
            "viewport_insight_pass": result.audit_viewport_pass,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "psi.runPagespeed",
            "lighthouse.categories.mobile",
        ],
    )
