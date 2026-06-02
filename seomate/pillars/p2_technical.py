"""Pillar 2 — Technical SEO extractors.

Most extractors read from ``site.page_audits`` (DataForSEO Instant
Pages prefetch). Two add a direct HTTP fetch:

- P2-01 robots.txt configuration
- P2-02 XML sitemap validity (the URL list itself was already fetched
  during URL discovery; this extractor re-fetches to evaluate the
  sitemap's structural rules)

Variables operationalised here:

- P2-01 robots.txt configuration correctness    (Consensus, 10 rules)
- P2-02 XML sitemap presence and validity       (Consensus, 10 rules)
- P2-18 HTTPS / SSL certificate                 (Consensus)
- P2-23 Crawl depth from homepage               (Probable, link-graph BFS)
- P2-24 Status code distribution                (Consensus, 8 rules)
- P2-26 Internal broken links                   (Consensus, partial — DataForSEO flag aggregation only)
- P2-28 Orphan pages                            (Consensus, link-graph reachability)
- P2-29 HTML errors / W3C validation            (Probable, partial — DataForSEO `broken_resources` flag)
- P2-30 Page weight                             (Consensus, distribution)
- P2-43 Duplicate content handling at site level (Consensus, 7 rules)

Variables deferred to later batches because they need a different
adapter or endpoint:

- P2-08–14 Core Web Vitals + page-loading speed (need Page Speed
  Insights / Lighthouse adapter)
- P2-15–17 Mobile responsiveness / usability    (need PSI mobile audit)
- P2-22 JavaScript rendering pattern            (need rendered-vs-raw HTML diff)
- P2-25 Redirect chains                         (need explicit chain trace)
- P2-31–32 Image format / lazy loading          (need per-image metadata)
- P2-37 Pop-ups and intrusive interstitials     (need DOM inspection)
- P2-44–48 Tag manager / analytics / pixels     (deferred — see o1 §3.1)
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

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


def _unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
    reason: str,
) -> CaptureRecord:
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={"reason": reason},
        rules=None,
        evidence_weight=weight,
        data_sources=[],
        errors=[reason],
    )


# ─── P2-01 — robots.txt configuration correctness ───────────────────────────


@register_extractor("P2-01")
async def capture_p2_01(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-01 — robots.txt configuration correctness (Consensus, 10 rules).

    Rules implementable at H1a layer (file fetch + syntax + simple
    cross-check); cross-signal rules (vs noindex meta, GSC URL
    Inspection) are deferred to P2-04 indexation status.
    """
    captured_at = _now()
    parsed = urlsplit(site.primary_url)
    if not parsed.scheme or not parsed.netloc:
        return _unmeasurable(
            ctx, site, "P2-01", EvidenceWeight.CONSENSUS, captured_at,
            "primary_url is not a valid URL",
        )
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(robots_url)
    except httpx.RequestError as exc:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-01",
            captured_at=captured_at,
            status=CaptureStatus.ERROR,
            value={"robots_url": robots_url},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.fetch"],
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    if response.status_code != 200:
        rule_1 = RuleResult(
            rule_id=1,
            rule_text="robots.txt accessible at the root domain",
            passed=False,
            evidence={"robots_url": robots_url, "status_code": response.status_code},
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-01",
            captured_at=captured_at,
            status=CaptureStatus.FAILED,
            value={"robots_url": robots_url, "status_code": response.status_code},
            rules=[rule_1],
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.fetch"],
        )

    body = response.text
    lines = [line.strip() for line in body.splitlines()]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="robots.txt accessible at the root domain",
        passed=True,
        evidence={"robots_url": robots_url, "status_code": 200},
    )

    # Rule 2: parses cleanly
    bad_lines: list[dict[str, Any]] = []
    valid_directives = {
        "user-agent",
        "disallow",
        "allow",
        "sitemap",
        "crawl-delay",
        "host",
    }
    for i, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            bad_lines.append({"line_number": i, "content": line[:100]})
            continue
        directive = line.split(":", 1)[0].strip().lower()
        if directive not in valid_directives:
            bad_lines.append({"line_number": i, "directive": directive})
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Syntactically valid against RFC 9309",
        passed=len(bad_lines) == 0,
        evidence={"malformed_or_unknown_directives": bad_lines[:20]},
    )

    # Rule 3: no `User-agent: *` followed by `Disallow: /` (site-wide block)
    site_wide_block = _detect_site_wide_block(lines)
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No accidental site-wide block (User-agent: * + Disallow: /)",
        passed=not site_wide_block,
        evidence={"site_wide_block_detected": site_wide_block},
    )

    # Rule 6: at least one Sitemap: directive
    sitemaps = [
        line.split(":", 1)[1].strip()
        for line in lines
        if line.lower().startswith("sitemap:")
    ]
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="Sitemap reference present in robots.txt",
        passed=len(sitemaps) > 0,
        evidence={"sitemaps_declared": sitemaps},
    )

    # Rule 9: no CSS/JS/image resource blocking
    blocked_resources: list[str] = []
    in_star_block = False
    for line in lines:
        ll = line.lower()
        if ll.startswith("user-agent:"):
            in_star_block = ll.split(":", 1)[1].strip() == "*"
        elif in_star_block and ll.startswith("disallow:"):
            value = line.split(":", 1)[1].strip()
            if any(
                value.endswith(ext)
                for ext in (".css", ".js", "/css", "/js", ".png", ".jpg", ".webp")
            ):
                blocked_resources.append(value)
    rule_9 = RuleResult(
        rule_id=9,
        rule_text="No CSS/JS/image resource blocking that breaks rendering",
        passed=len(blocked_resources) == 0,
        evidence={"blocked_resource_patterns": blocked_resources},
    )

    # Rule 10: no reliance on Crawl-delay for Googlebot
    crawl_delay_for_googlebot = False
    in_googlebot = False
    for line in lines:
        ll = line.lower()
        if ll.startswith("user-agent:"):
            in_googlebot = ll.split(":", 1)[1].strip() in {"googlebot", "google"}
        elif in_googlebot and ll.startswith("crawl-delay:"):
            crawl_delay_for_googlebot = True
    rule_10 = RuleResult(
        rule_id=10,
        rule_text="No Crawl-delay directive for Googlebot (Google ignores it)",
        passed=not crawl_delay_for_googlebot,
        evidence={"googlebot_crawl_delay_present": crawl_delay_for_googlebot},
    )

    rules = [rule_1, rule_2, rule_3, rule_6, rule_9, rule_10]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "robots_url": robots_url,
            "size_bytes": len(body),
            "directive_lines": len([l for l in lines if l and not l.startswith("#")]),
            "sitemaps_declared": sitemaps,
            "rules_evaluated_at_h1a": [r.rule_id for r in rules],
            "rules_deferred": [4, 5, 7, 8],
            "deferred_reason": "Cross-signal rules (vs site URL inventory, vs noindex meta, bot-specific consistency) belong to P2-04 indexation status and P6-17 LLM-bot crawler access.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.fetch", "composition.robots_txt_parse"],
    )


def _detect_site_wide_block(lines: list[str]) -> bool:
    """True if any User-agent: * block contains Disallow: /."""
    in_star_block = False
    for line in lines:
        ll = line.lower()
        if ll.startswith("user-agent:"):
            in_star_block = ll.split(":", 1)[1].strip() == "*"
        elif in_star_block and ll.lower().strip() == "disallow: /":
            return True
    return False


# ─── P2-02 — XML sitemap presence and validity ──────────────────────────────


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")


@register_extractor("P2-02")
async def capture_p2_02(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-02 — XML sitemap presence and validity (Consensus, 10 rules)."""
    captured_at = _now()
    parsed = urlsplit(site.primary_url)
    if not parsed.scheme or not parsed.netloc:
        return _unmeasurable(
            ctx, site, "P2-02", EvidenceWeight.CONSENSUS, captured_at,
            "primary_url is not a valid URL",
        )
    base = f"{parsed.scheme}://{parsed.netloc}"

    sitemap_url: str | None = None
    sitemap_body: str = ""
    sitemap_status: int = 0
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for path in SITEMAP_PATHS:
            url = urljoin(base, path)
            try:
                response = await client.get(url)
            except httpx.RequestError:
                continue
            if response.status_code == 200 and response.text.strip():
                sitemap_url = url
                sitemap_body = response.text
                sitemap_status = 200
                break

    if sitemap_url is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-02",
            captured_at=captured_at,
            status=CaptureStatus.FAILED,
            value={
                "sitemap_url": None,
                "paths_tried": list(SITEMAP_PATHS),
            },
            rules=[
                RuleResult(
                    rule_id=1,
                    rule_text="Sitemap accessible at a conventional path",
                    passed=False,
                    evidence={"paths_tried": list(SITEMAP_PATHS)},
                )
            ],
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.fetch"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Sitemap accessible at a conventional path",
        passed=True,
        evidence={"sitemap_url": sitemap_url, "status_code": sitemap_status},
    )

    # Rule 2: valid XML
    parse_error: str | None = None
    root = None
    try:
        root = ET.fromstring(sitemap_body)
    except ET.ParseError as exc:
        parse_error = str(exc)
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Sitemap parses as valid XML",
        passed=parse_error is None,
        evidence={"parse_error": parse_error},
    )

    # Rule 3: within size limits (50K URLs / 50 MB uncompressed)
    size_bytes = len(sitemap_body.encode("utf-8"))
    url_count = len(site.urls)
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Within size limits (≤50K URLs, ≤50 MB)",
        passed=url_count <= 50_000 and size_bytes <= 50 * 1024 * 1024,
        evidence={
            "size_bytes": size_bytes,
            "url_count": url_count,
            "size_limit_bytes": 50 * 1024 * 1024,
            "url_limit": 50_000,
        },
    )

    # Rule 5: all listed URLs return 200 (cross-check against page_audits)
    not_200: list[dict[str, Any]] = []
    for u in site.urls:
        pa = site.page_audits.get(u)
        if pa is None:
            err = site.page_audit_errors.get(u, "no audit attempted")
            not_200.append({"url": u, "issue": f"no audit data: {err}"})
        elif pa.status_code != 200:
            not_200.append({"url": u, "status_code": pa.status_code})
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="All listed URLs return HTTP 200",
        passed=len(not_200) == 0,
        evidence={
            "non_200_urls": not_200[:50],
            "non_200_count": len(not_200),
        },
    )

    # Rule 7: <lastmod> populated where present
    lastmod_count = 0
    if root is not None:
        for u in root.findall(f"{{{SITEMAP_NS}}}url"):
            if u.find(f"{{{SITEMAP_NS}}}lastmod") is not None:
                lastmod_count += 1
    lastmod_pct = (lastmod_count / url_count * 100.0) if url_count else 0.0
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="<lastmod> populated on entries where applicable",
        passed=lastmod_count > 0,
        evidence={
            "urls_with_lastmod": lastmod_count,
            "urls_with_lastmod_pct": round(lastmod_pct, 1),
        },
        notes="Best-effort: missing lastmod is acceptable but rules out freshness signals.",
    )

    rules = [rule_1, rule_2, rule_3, rule_5, rule_7]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-02",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "sitemap_url": sitemap_url,
            "size_bytes": size_bytes,
            "url_count": url_count,
            "rules_evaluated_at_h1a": [r.rule_id for r in rules],
            "rules_deferred": [4, 6, 8, 9, 10],
            "deferred_reason": "Cross-signal rules (vs noindex meta, vs canonical, robots.txt reference, sitemap-index recursion) need cross-pillar joins to evaluate cleanly.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.fetch", "composition.sitemap_xml_parse"],
    )


# ─── P2-18 — HTTPS / SSL certificate ────────────────────────────────────────


@register_extractor("P2-18")
async def capture_p2_18(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-18 — HTTPS scheme on every URL (Consensus, basic check).

    The certificate-validity rule requires a TLS handshake inspection;
    that's beyond the cheap layer. We capture the HTTPS-scheme rule
    here and defer cert-chain validation to a later pass.
    """
    captured_at = _now()
    if not site.urls:
        return _unmeasurable(
            ctx, site, "P2-18", EvidenceWeight.CONSENSUS, captured_at,
            "no URLs discovered",
        )

    non_https = [u for u in site.urls if not u.lower().startswith("https://")]
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every URL uses HTTPS",
        passed=len(non_https) == 0,
        evidence={
            "urls_audited": len(site.urls),
            "non_https_urls": non_https[:50],
            "non_https_count": len(non_https),
        },
    )
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-18",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "urls_audited": len(site.urls),
            "non_https_count": len(non_https),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["composition.url_scheme_check"],
    )


# ─── P2-23 — Crawl depth from homepage ──────────────────────────────────────

# Click-depth thresholds. Practitioners converge on "≤3 hops" as the
# desirable shallow tier for important pages; >5 hops is a recognised
# crawl-budget concern. Recorded as Probable because while Google
# acknowledges crawl budget exists, the exact depth thresholds are
# practitioner heuristics, not Google-published numbers.
CLICK_DEPTH_SHALLOW_MAX = 3
CLICK_DEPTH_DEEP_MIN = 6


@register_extractor("P2-23")
async def capture_p2_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-23 — Click depth from homepage (Probable, link-graph BFS).

    BFS from the configured ``primary_url`` over the internal link
    graph captured during HTML prefetch. Reports per-page depth and
    a distribution summary. Pages not reachable from the homepage
    appear as ``unreachable`` and feed P2-28's orphan check.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _unmeasurable(
            ctx, site, "P2-23", EvidenceWeight.PROBABLE, captured_at,
            "no link graph available — HTML prefetch produced no usable pages",
        )

    depths = site.link_graph.click_depth_from(site.primary_url)
    if not depths:
        return _unmeasurable(
            ctx, site, "P2-23", EvidenceWeight.PROBABLE, captured_at,
            "homepage URL not present in the link graph; cannot compute depth",
        )

    by_depth: Counter[int] = Counter(depths.values())
    max_depth = max(depths.values())
    unreachable = sorted(set(site.link_graph.pages) - set(depths.keys()))
    deep_pages = sorted(u for u, d in depths.items() if d >= CLICK_DEPTH_DEEP_MIN)
    shallow_count = sum(1 for d in depths.values() if d <= CLICK_DEPTH_SHALLOW_MAX)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Homepage is reachable in the link graph (depth 0 page exists)",
        passed=any(d == 0 for d in depths.values()),
        evidence={"primary_url": site.primary_url, "depth_zero_count": by_depth.get(0, 0)},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No page sits beyond a 5-hop click depth from the homepage",
        passed=len(deep_pages) == 0,
        evidence={
            "deep_pages": deep_pages,
            "deep_threshold_min_hops": CLICK_DEPTH_DEEP_MIN,
            "max_depth": max_depth,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Click-depth distribution is reasonably shallow (>= 50% of pages within 3 hops)",
        passed=(shallow_count / len(depths)) >= 0.5,
        evidence={
            "pages_within_3_hops": shallow_count,
            "pages_total_reachable": len(depths),
            "shallow_pct": round(shallow_count / len(depths) * 100, 1),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Every audited page is reachable from the homepage (no unreachable nodes)",
        passed=len(unreachable) == 0,
        evidence={
            "unreachable_pages": unreachable[:50],
            "unreachable_count": len(unreachable),
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_in_graph": site.link_graph.page_count,
            "pages_reachable_from_homepage": len(depths),
            "max_depth": max_depth,
            "depth_distribution": dict(sorted(by_depth.items())),
            "deep_pages_count": len(deep_pages),
            "deep_pages": deep_pages[:25],
            "unreachable_count": len(unreachable),
            "unreachable_sample": unreachable[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.link_graph_bfs",
        ],
    )


# ─── P2-28 — Orphan pages ───────────────────────────────────────────────────


@register_extractor("P2-28")
async def capture_p2_28(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-28 — Orphan pages (Consensus).

    A page is considered orphaned when it has zero inbound internal
    links AND is not reachable from the homepage in the link graph.
    The dual check is conservative: a page reachable only via redirect
    chain or only from the homepage's `<a href>` is *not* orphaned.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _unmeasurable(
            ctx, site, "P2-28", EvidenceWeight.CONSENSUS, captured_at,
            "no link graph available — HTML prefetch produced no usable pages",
        )

    orphans = site.link_graph.orphans(site.primary_url)
    no_inbound = [
        u for u in sorted(site.link_graph.pages)
        if site.link_graph.inbound_count(u) == 0
    ]
    depths = site.link_graph.click_depth_from(site.primary_url)
    unreachable = sorted(set(site.link_graph.pages) - set(depths.keys()))

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No page in the audited URL set has zero inbound internal links and is unreachable from the homepage",
        passed=len(orphans) == 0,
        evidence={
            "orphan_count": len(orphans),
            "orphans": orphans[:50],
            "method": "no_inbound_AND_not_reachable_from_homepage",
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Every page declared in the sitemap is reachable from the homepage (or has at least one inbound internal link)",
        passed=len(unreachable) == 0
        or all(site.link_graph.inbound_count(u) > 0 for u in unreachable),
        evidence={
            "unreachable_with_no_inbound": [
                u for u in unreachable
                if site.link_graph.inbound_count(u) == 0
            ][:50],
            "unreachable_count": len(unreachable),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Pages with zero inbound internal links are flagged for review",
        passed=True,
        evidence={
            "no_inbound_pages": no_inbound[:50],
            "no_inbound_count": len(no_inbound),
        },
        notes=(
            "Advisory: the homepage itself often has no internal inbound "
            "links from the audit set (it's the entry point); reviewers "
            "should ignore the homepage in this list."
        ),
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-28",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_in_graph": site.link_graph.page_count,
            "orphan_count": len(orphans),
            "orphans": orphans,
            "no_inbound_count": len(no_inbound),
            "unreachable_count": len(unreachable),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "composition.link_graph_orphan_detection",
        ],
    )


# ─── P2-24 — Status code distribution ───────────────────────────────────────


@register_extractor("P2-24")
async def capture_p2_24(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-24 — HTTP status code distribution (Consensus, 8 rules).

    Aggregates ``status_code`` across all PageAudits plus URLs that
    failed to fetch (which we treat as 0 / unreachable in the
    distribution).
    """
    captured_at = _now()
    if not site.page_audits and not site.page_audit_errors:
        return _unmeasurable(
            ctx, site, "P2-24", EvidenceWeight.CONSENSUS, captured_at,
            "no page audits captured",
        )

    statuses: list[int] = []
    fetch_failed: list[str] = []
    for u in site.urls:
        pa = site.page_audits.get(u)
        if pa is None:
            fetch_failed.append(u)
            continue
        statuses.append(pa.status_code)

    distribution = Counter(statuses)
    total_audited = sum(distribution.values())
    bad_count = sum(c for code, c in distribution.items() if code >= 400)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="200s dominate the distribution",
        passed=distribution.get(200, 0) / total_audited > 0.9 if total_audited else False,
        evidence={
            "200_count": distribution.get(200, 0),
            "200_pct": round(distribution.get(200, 0) / total_audited * 100, 1)
            if total_audited
            else 0,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Error rate (4xx + 5xx) below 5%",
        passed=(bad_count / total_audited < 0.05) if total_audited else False,
        evidence={
            "error_count": bad_count,
            "error_pct": round(bad_count / total_audited * 100, 2)
            if total_audited
            else 0,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="No 5xx server errors observed",
        passed=not any(500 <= code < 600 for code in distribution),
        evidence={
            "5xx_codes_present": sorted(
                [c for c in distribution if 500 <= c < 600]
            ),
        },
    )

    rules = [rule_1, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-24",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "urls_in_sitemap": len(site.urls),
            "audited": total_audited,
            "fetch_failed": len(fetch_failed),
            "fetch_failed_urls": fetch_failed[:20],
            "status_distribution": dict(sorted(distribution.items())),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P2-26 — Internal broken links (partial) ────────────────────────────────


@register_extractor("P2-26")
async def capture_p2_26(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-26 — Internal broken links (Consensus, partial coverage).

    Reports per-page ``broken_links`` flag from DataForSEO. Full
    coverage (count + URLs of broken outbound links) requires the
    full-site Pages endpoint and is deferred.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable(
            ctx, site, "P2-26", EvidenceWeight.CONSENSUS, captured_at,
            "no successful page audits",
        )

    flagged = [p.url for p in audits if p.broken_links_check]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-26",
        captured_at=captured_at,
        status=CaptureStatus.PASSED
        if len(flagged) == 0
        else CaptureStatus.PARTIAL,
        value={
            "pages_audited": len(audits),
            "pages_flagged_with_broken_links": flagged,
            "pages_flagged_count": len(flagged),
            "note": (
                "DataForSEO Instant Pages reports a per-page boolean only. "
                "Full coverage (counts + target URLs) lands in H1b composition "
                "layer when we add a full-site Pages-endpoint pass."
            ),
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P2-29 — HTML errors / W3C validation (partial) ─────────────────────────


@register_extractor("P2-29")
async def capture_p2_29(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-29 — Broken resources flag aggregation (Probable, partial).

    Full W3C validation is its own layer; here we report DataForSEO's
    per-page ``broken_resources`` flag (true when any referenced
    asset failed to load).
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _unmeasurable(
            ctx, site, "P2-29", EvidenceWeight.PROBABLE, captured_at,
            "no successful page audits",
        )

    flagged = [p.url for p in audits if p.broken_resources_check]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-29",
        captured_at=captured_at,
        status=CaptureStatus.PASSED
        if len(flagged) == 0
        else CaptureStatus.PARTIAL,
        value={
            "pages_audited": len(audits),
            "pages_flagged_with_broken_resources": flagged,
            "pages_flagged_count": len(flagged),
            "note": "Full W3C HTML validation is deferred to a later layer.",
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["dataforseo.on_page.instant_pages"],
    )


# ─── P2-30 — Page weight ────────────────────────────────────────────────────


PAGE_WEIGHT_OPTIMAL_HI_BYTES = 1_500_000   # 1.5 MB
PAGE_WEIGHT_TOO_HEAVY_BYTES = 3_000_000    # 3 MB


@register_extractor("P2-30")
async def capture_p2_30(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-30 — Page weight (Consensus).

    Total transfer weight (HTML + CSS + JS + images + fonts) read from the
    Lighthouse ``total-byte-weight`` audit in the PSI results we already
    fetch — no extra crawl or DataForSEO cost. (DataForSEO Instant Pages
    does NOT return sub-resource sizes even with load_resources=true;
    verified live 2026-06.) PSI runs on the primary URL(s), so this grades
    the sampled page(s), not the full-site distribution. Flags > 3 MB.
    """
    captured_at = _now()
    results = [
        r for r in site.psi_results.values()
        if r.fetch_status == "ok" and r.total_byte_weight_bytes is not None
    ]
    if not results:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-30",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no PSI/Lighthouse total-byte-weight available (PSI not run "
                    "for this site or returned no weight audit)"
                ),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["psi.runPagespeed", "lighthouse.total-byte-weight"],
            errors=["no PSI weight data"],
        )

    mb = 1024 * 1024
    good_bytes = 3 * mb
    poor_bytes = 5 * mb
    per_page = [
        {
            "url": r.url,
            "strategy": getattr(r.strategy, "value", str(r.strategy)),
            "total_bytes": r.total_byte_weight_bytes,
            "total_mb": round(r.total_byte_weight_bytes / mb, 2),
            "image_bytes": r.image_bytes,
            "image_mb": round(r.image_bytes / mb, 2) if r.image_bytes else None,
        }
        for r in results
    ]
    max_bytes = max(r.total_byte_weight_bytes for r in results)
    over_good = [p for p in per_page if p["total_bytes"] > good_bytes]
    over_poor = [p for p in per_page if p["total_bytes"] > poor_bytes]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Sampled page weight is <= 3 MB",
        passed=not over_good,
        evidence={"pages_over_3mb": over_good, "max_mb": round(max_bytes / mb, 2)},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No sampled page exceeds 5 MB",
        passed=not over_poor,
        evidence={"pages_over_5mb": over_poor},
    )
    if not over_good:
        status = CaptureStatus.PASSED
    elif not over_poor:
        status = CaptureStatus.PARTIAL
    else:
        status = CaptureStatus.FAILED

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-30",
        captured_at=captured_at,
        status=status,
        value={
            "per_page": per_page,
            "max_mb": round(max_bytes / mb, 2),
            "thresholds_mb": {"good": 3, "poor": 5},
            "scope": "PSI-sampled (primary URL + strategies), not full-site distribution",
        },
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "psi.runPagespeed", "lighthouse.total-byte-weight", "lighthouse.resource-summary",
        ],
    )


# ─── P2-43 — Duplicate content handling at site level ───────────────────────


_RE_SESSION_ID = re.compile(
    r"[?&](PHPSESSID|JSESSIONID|sid|session_id|sessionid)=", re.IGNORECASE
)
_RE_TRACKING_PARAM = re.compile(
    r"[?&](utm_[a-z_]+|fbclid|gclid|gbraid|wbraid|mc_cid|mc_eid|igshid)=",
    re.IGNORECASE,
)
_RE_PRINT = re.compile(r"/print/?(?:[?#]|$)|/print/.+", re.IGNORECASE)
_RE_SORT_FILTER = re.compile(r"[?&](sort|filter|order|orderby|view)=", re.IGNORECASE)


@register_extractor("P2-43")
async def capture_p2_43(
    ctx: AdapterContext,
    site: SiteData,
    *,
    dataforseo: DataForSEOAdapter,  # noqa: ARG001
) -> CaptureRecord:
    """P2-43 — Duplicate content handling at site level (Consensus, 7 rules)."""
    captured_at = _now()
    if not site.urls:
        return _unmeasurable(
            ctx, site, "P2-43", EvidenceWeight.CONSENSUS, captured_at,
            "no URLs discovered",
        )

    session_id_urls = [u for u in site.urls if _RE_SESSION_ID.search(u)]
    tracking_param_urls = [u for u in site.urls if _RE_TRACKING_PARAM.search(u)]
    sort_filter_urls = [u for u in site.urls if _RE_SORT_FILTER.search(u)]
    pagination_urls = [u for u in site.urls if "?page=" in u or "&page=" in u]
    print_urls = [u for u in site.urls if _RE_PRINT.search(u)]
    https_urls = [u for u in site.urls if u.lower().startswith("https://")]
    http_urls = [u for u in site.urls if u.lower().startswith("http://")]
    netlocs = {urlsplit(u).netloc.lower() for u in site.urls}

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No session IDs in indexable URLs",
        passed=len(session_id_urls) == 0,
        evidence={"urls_with_session_id": session_id_urls[:20]},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No tracking parameters on canonical URLs (utm_*, fbclid, gclid, ...)",
        passed=len(tracking_param_urls) == 0,
        evidence={"urls_with_tracking_params": tracking_param_urls[:20]},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Sort/filter parameters not appearing in canonical sitemap URLs",
        passed=len(sort_filter_urls) == 0,
        evidence={"urls_with_sort_filter_params": sort_filter_urls[:20]},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Pagination URLs handled (none in sitemap is acceptable; if present, paginated should self-canonical)",
        passed=True,  # Presence alone doesn't fail; cross-check with canonical happens in P1-20
        evidence={
            "paginated_urls_in_sitemap_count": len(pagination_urls),
            "paginated_urls_sample": pagination_urls[:10],
        },
        notes="The deeper check (paginated URLs canonicalise correctly) belongs to P1-20.",
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No print versions in indexable sitemap URLs",
        passed=len(print_urls) == 0,
        evidence={"urls_with_print_pattern": print_urls[:20]},
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="HTTP and HTTPS not both indexable (HTTPS-only)",
        passed=len(http_urls) == 0,
        evidence={
            "https_count": len(https_urls),
            "http_count": len(http_urls),
            "http_urls_sample": http_urls[:10],
        },
    )
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="One canonical host variant (www OR non-www, not both)",
        passed=len(netlocs) <= 1,
        evidence={"distinct_netlocs": sorted(netlocs)},
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6, rule_7]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-43",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "urls_audited": len(site.urls),
            "rules_failed": [r.rule_id for r in rules if not r.passed],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["composition.url_pattern_analysis"],
    )


# ─── P2-05 — Crawl budget utilisation (partial) ────────────────────────────


# URL parameter patterns that commonly create infinite crawl spaces
# when not robots-blocked.
_INFINITE_SPACE_PARAM_PATTERNS = (
    "?s=", "?q=", "?search=", "?query=",          # search-result URLs
    "?date=", "?year=", "?month=",                 # calendar widgets
    "?sort=", "?order=", "?orderby=",              # sort variants
    "?filter=", "?facet=", "?refine=",             # facet navigation
    "?session=", "?sid=", "?jsessionid=",          # session IDs
    "?utm_", "?gclid=", "?fbclid=",                # tracking parameters
    "?ref=", "?source=", "?campaign=",             # referral tracking
    "&s=", "&q=", "&date=", "&filter=",            # same patterns mid-URL
)


@register_extractor("P2-05")
async def capture_p2_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-05 — Crawl budget utilisation (Probable, partial measurement).

    The full variable measures Google's actual crawl efficiency from
    Search Console Crawl Stats — owner-only data we don't have. What
    we CAN measure from the audit's own crawl + parsed HTML:

    - **Rule 1 proxy**: status-code distribution across our 58-page
      crawl (4xx/5xx rate as a proxy for crawl waste)
    - **Rule 7 proxy**: scan our pages' outbound internal links for
      URL parameter patterns characteristic of infinite-space sources

    Pass:
    - Crawled-page 4xx/5xx rate <= 5% (proxy for rule 1)
    - <= 2 URL patterns flagged as infinite-space candidates (proxy
      for rule 7)
    """
    captured_at = _now()
    audits = list(site.page_audits.values())
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo.on_page.instant_pages", "composition.url_patterns"],
            errors=["no page audits"],
        )

    total_audited = len(audits)
    error_count = sum(
        1 for a in audits if a.fetch_error is not None or a.status_code >= 400
    )
    error_pct = round(error_count / total_audited * 100, 1) if total_audited else 0.0
    error_urls = [
        {"url": a.url, "status_code": a.status_code, "fetch_error": a.fetch_error}
        for a in audits
        if a.fetch_error is not None or a.status_code >= 400
    ][:15]

    # Rule 7: detect infinite-space URL patterns in the link graph
    infinite_space_hits: dict[str, list[str]] = {}
    if site.link_graph is not None:
        for source_url, refs_list in site.link_graph.outbound.items():
            for ref in refs_list:
                target = getattr(ref, "target_url", None) or ""
                lower_target = target.lower()
                for pattern in _INFINITE_SPACE_PARAM_PATTERNS:
                    if pattern in lower_target:
                        hits = infinite_space_hits.setdefault(pattern, [])
                        if len(hits) < 5:
                            hits.append(target)
                        break

    infinite_space_pattern_count = len(infinite_space_hits)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Audited-crawl 4xx/5xx rate <= 5% (proxy — real check needs GSC Crawl Stats)",
        passed=error_pct <= 5.0,
        evidence={
            "error_count": error_count,
            "error_pct": error_pct,
            "total_audited": total_audited,
        },
    )
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="<= 2 URL patterns flagged as infinite-space candidates in internal-link graph",
        passed=infinite_space_pattern_count <= 2,
        evidence={
            "pattern_count": infinite_space_pattern_count,
            "patterns_detected": sorted(infinite_space_hits.keys()),
        },
    )

    rules = [rule_1, rule_7]
    overall = rule_1.passed and rule_7.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "measurement_scope": "partial",
            "rules_evaluated": [1, 7],
            "rules_owner_data_required": [2, 3, 4, 5, 6],
            "owner_data_remediation": (
                "rules 2-6 measure actual crawler behaviour (canonical "
                "vs duplicate target rate, parameter-variant crawl, "
                "frequency-vs-cadence match, deep-page crawl, resource "
                "vs HTML balance). These require Google Search Console "
                "Crawl Stats API access. Connect a verified GSC property "
                "in a future platform release to populate."
            ),
            "audited_pages": total_audited,
            "error_count": error_count,
            "error_pct": error_pct,
            "error_urls_sample": error_urls,
            "infinite_space_pattern_count": infinite_space_pattern_count,
            "infinite_space_patterns": infinite_space_hits,
            "see_also": "P1-20 (canonical coverage), P2-04 (indexation status)",
            "note": (
                "Partial measurement: this audit can detect the SHAPE "
                "of crawl-budget waste (error pages, infinite spaces) "
                "from external evidence but cannot read Google's actual "
                "crawl log. A clean partial result is necessary but not "
                "sufficient for full pass. Cross-reference GSC Crawl "
                "Stats for the authoritative view."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.link_graph_url_patterns",
        ],
    )
