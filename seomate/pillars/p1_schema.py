"""Pillar 1 — Schema markup family (P1-21, P1-22, P1-47).

Lives in its own module rather than ``p1_onpage.py`` because the schema
extractors share a common parsed-structured-data view and a vocabulary
of helpers (Google required-property registry, type-appropriateness
mapping). Splitting them out keeps the on-page module focused on
title / description / heading / link checks.

Variables operationalised in this module:

- P1-21 — Schema markup type appropriateness (Consensus, 6 rules)
- P1-22 — Schema markup completeness and validity (Consensus, 9 rules)
- P1-47 — BreadcrumbList schema (Consensus, 8 rules)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from seomate.adapters import AdapterContext
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor
from seomate.utils.structured_data import SchemaBlock, StructuredData

# ─── Schema-type vocabulary ─────────────────────────────────────────────────

# Google's required properties per supported rich-result type.
# Sources: https://developers.google.com/search/docs/appearance/structured-data
# (per-type pages, accessed May 2026). "Required" means rich-result-eligible
# minimum — not strictly schema.org "required".
GOOGLE_REQUIRED_PROPERTIES: dict[str, set[str]] = {
    "Article": {"headline", "image", "datePublished", "author"},
    "NewsArticle": {"headline", "image", "datePublished", "author"},
    "BlogPosting": {"headline", "image", "datePublished", "author"},
    "Product": {"name", "image", "offers"},
    "Organization": {"name", "url"},
    "LocalBusiness": {"name", "address"},
    "Recipe": {"name", "image", "recipeIngredient", "recipeInstructions"},
    "Event": {"name", "startDate", "location"},
    "FAQPage": {"mainEntity"},
    "QAPage": {"mainEntity"},
    "BreadcrumbList": {"itemListElement"},
    "VideoObject": {"name", "description", "thumbnailUrl", "uploadDate"},
    "HowTo": {"name", "step"},
    "Person": {"name"},
    "WebSite": {"name", "url"},
    "WebPage": set(),
    "ProfilePage": {"mainEntity"},
}

# Recommended properties on top of required (Google's "recommended" list).
GOOGLE_RECOMMENDED_PROPERTIES: dict[str, set[str]] = {
    "Article": {"dateModified", "publisher", "mainEntityOfPage"},
    "NewsArticle": {"dateModified", "publisher", "mainEntityOfPage"},
    "BlogPosting": {"dateModified", "publisher", "mainEntityOfPage"},
    "Product": {"description", "brand", "review", "aggregateRating", "sku"},
    "Organization": {"logo", "sameAs", "contactPoint", "description"},
    "LocalBusiness": {
        "telephone", "openingHours", "geo", "priceRange", "image", "url",
    },
    "Recipe": {
        "author", "datePublished", "description", "nutrition", "totalTime",
    },
    "Event": {
        "description", "endDate", "image", "offers", "performer", "organizer",
    },
    "FAQPage": set(),
    "VideoObject": {"contentUrl", "duration", "publisher"},
    "Person": {"url", "image", "sameAs", "description", "jobTitle", "worksFor"},
}

# Generic / "you should choose something more specific" types. Page-level
# pages should use a more specific type when one fits.
GENERIC_SCHEMA_TYPES = frozenset({
    "Thing",
    "WebPage",
    "ItemPage",
    "CollectionPage",
})

# Schema types Google has explicitly cautioned against using broadly or
# whose abuse triggers manual actions. We surface them as evidence rather
# than auto-fail because legitimate uses exist; reviewers should sanity-check.
PROHIBITED_OR_RISKY_SCHEMA_TYPES = frozenset({
    "HowTo",       # severely restricted as of 2023; only real procedural content
    "FAQPage",     # restricted to authoritative sources; Google killed FAQ rich
                   # results in mainstream pages in 2023
})

# Page-type guesses. We don't have a dedicated page-classification layer
# yet, so we use URL-path heuristics; these are advisory, not load-bearing.
URL_PATTERN_TO_EXPECTED_TYPES: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (
        ("/blog/", "/news/", "/article/", "/articles/", "/posts/", "/post/"),
        frozenset({"Article", "NewsArticle", "BlogPosting"}),
    ),
    (
        ("/product/", "/products/", "/shop/"),
        frozenset({"Product"}),
    ),
    (
        ("/recipe/", "/recipes/"),
        frozenset({"Recipe"}),
    ),
    (
        ("/event/", "/events/"),
        frozenset({"Event"}),
    ),
    (
        ("/faq", "/faqs", "/help"),
        frozenset({"FAQPage", "QAPage"}),
    ),
    (
        ("/video/", "/videos/", "/watch/"),
        frozenset({"VideoObject"}),
    ),
    (
        ("/about/", "/team/", "/people/"),
        frozenset({"AboutPage", "ProfilePage", "Person"}),
    ),
    (
        ("/contact/", "/contact-us/"),
        frozenset({"ContactPage", "Organization", "LocalBusiness"}),
    ),
)

KNOWN_SCHEMA_TYPES = frozenset(
    list(GOOGLE_REQUIRED_PROPERTIES.keys())
    + [
        "Thing", "AboutPage", "ContactPage", "ItemPage", "CollectionPage",
        "ImageObject", "ListItem", "Offer", "AggregateRating", "Review",
        "Brand", "PostalAddress", "ContactPoint", "GeoCoordinates",
        "OpeningHoursSpecification", "Service", "MonetaryAmount",
        "PropertyValue", "Place", "SearchAction", "EntryPoint", "Question",
        "Answer", "ImageGallery", "Audience", "Action", "WebContent",
        # Common valid schema.org types that were missing -> were wrongly flagged
        # as "unrecognised/invented" (e.g. ItemList on a team/about page).
        "ItemList", "WebSite", "WebPage", "SiteNavigationElement", "Person",
        "VideoObject", "NewsArticle", "BlogPosting", "Rating",
    ]
)

# Authoritative same-as targets we recognise and value extra.
HIGH_VALUE_SAMEAS_HOSTS = (
    "wikipedia.org",
    "wikidata.org",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "github.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "crunchbase.com",
    "bloomberg.com",
    "google.com",  # for KG-MID URLs
    "orcid.org",
    "scholar.google.com",
)


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


def _schema_visible_match_rule(site: SiteData) -> RuleResult:
    """Build the P1-22 rule-7 / P6-19 rule-8 result from cached LLM evals.

    Sets ``evidence["conclusive"]`` so the caller can tell a real verdict from
    an absent or incomplete one. The rule cannot fail the variable for a missing
    API key (that would penalise the site for our own outage), so when it is not
    conclusive the caller degrades the capture to PARTIAL instead of PASSED.

    Asymmetry that matters: a failure can be proven from partial data, but the
    ABSENCE of failures cannot. If any page errored we do not know whether it
    would have failed, so "no failing pages" is only conclusive when every page
    returned a verdict. This is the exact defect that made a page which FAILED
    on 2026-07-20 merely ERROR on 2026-07-22, silently flipping the variable to
    passed with no site change.
    """
    evals = site.llm_evaluations.get("schema_visible_match", {})
    if not evals:
        return RuleResult(
            rule_id=7,
            rule_text="Schema content matches visible content (no hidden facts)",
            passed=True,
            evidence={
                "method": "deferred_until_anthropic_key_set",
                "evaluated_pages": 0,
                "conclusive": False,
            },
            notes=(
                "Not evaluated: the LLM evaluation layer was unavailable. Does not "
                "count toward the verdict; the capture degrades to PARTIAL. "
                "Configure ANTHROPIC_API_KEY to activate per-page evaluation."
            ),
        )
    failing: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []
    passing_count = 0
    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        if ev.passed:
            passing_count += 1
        else:
            failing.append(
                {
                    "url": url,
                    "confidence": ev.confidence,
                    "issues": list(ev.issues)[:5],
                    "rationale": ev.rationale,
                }
            )
    # A failure is definitive even with gaps; a clean sheet is only definitive
    # when every page returned a verdict.
    conclusive = bool(failing) or not errored
    return RuleResult(
        rule_id=7,
        rule_text="Schema content matches visible content (no hidden facts)",
        passed=len(failing) == 0,
        evidence={
            "method": "anthropic_llm_per_page_evaluation",
            "pages_evaluated": len(evals),
            "pages_passed": passing_count,
            "pages_failed": len(failing),
            "pages_errored": len(errored),
            "coverage_pct": round(
                100.0 * (passing_count + len(failing)) / max(1, len(evals)), 1
            ),
            "conclusive": conclusive,
            "failing_pages": failing[:25],
            "errored_pages": errored[:10],
        },
        notes=(
            "LLM-evaluated via batched Claude Haiku calls at audit start."
            if conclusive
            else (
                f"Inconclusive: no failing page found, but {len(errored)} page(s) "
                "returned no verdict, so absence of failure is unproven. Does not "
                "count toward the verdict; the capture degrades to PARTIAL."
            )
        ),
    )


def _expected_types_for(url: str) -> frozenset[str]:
    """Best-effort page-type classification by URL path."""
    path = (urlsplit(url).path or "/").lower()
    for needles, expected in URL_PATTERN_TO_EXPECTED_TYPES:
        if any(n in path for n in needles):
            return expected
    return frozenset()


def _is_homepage(url: str, site: SiteData) -> bool:
    """Treat the configured primary_url and bare-host variants as homepage."""
    parts = urlsplit(url)
    primary = urlsplit(site.primary_url)
    same_host = parts.netloc.lower().removeprefix("www.") == primary.netloc.lower().removeprefix("www.")
    path_root = parts.path in ("", "/", "/index.html", "/home")
    return same_host and path_root


def _per_page_value(sd: StructuredData) -> dict[str, Any]:
    """Trimmed view of one page's structured-data outcome for evidence."""
    return {
        "url": sd.url,
        "block_count": len(sd.blocks),
        "schema_org_blocks": len(sd.schema_org_blocks),
        "types_present": list(sd.all_types),
        "json_ld_parse_errors": list(sd.json_ld_parse_errors),
        "graph_ref_count": len(sd.graph_refs),
    }


def _no_pages_unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
) -> CaptureRecord:
    """Unmeasurable when we have no successfully-fetched pages to inspect."""
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": "no successfully-fetched HTML pages available",
            "html_pages_total": len(site.html_pages),
            "html_pages_failed": sum(
                1 for h in site.html_pages.values() if h.fetch_error is not None
            ),
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["http.html_fetch", "extruct.parse_structured_data"],
        errors=["site.successful_structured_data is empty"],
    )


# ─── P1-21 — Schema markup type appropriateness ─────────────────────────────


@register_extractor("P1-21")
async def capture_p1_21(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-21 — Schema markup type appropriateness (Consensus, 6 rules).

    Aggregates per-page schema-type findings into a site-wide pass/fail.
    Page-type heuristics are URL-path-based; if a page's path doesn't
    match any known pattern, the appropriateness check for that page is
    skipped (recorded as `expected_types: []`) rather than fabricated.
    """
    captured_at = _now()
    pages = site.successful_structured_data
    if not pages:
        return _no_pages_unmeasurable(
            ctx, site, "P1-21", EvidenceWeight.CONSENSUS, captured_at
        )

    pages_with_schema: list[StructuredData] = [p for p in pages if p.schema_org_blocks]
    pages_without_schema = [p.url for p in pages if not p.schema_org_blocks]

    misleading: list[dict[str, Any]] = []
    generic_only: list[str] = []
    prohibited: list[dict[str, Any]] = []
    unknown_types: list[dict[str, Any]] = []
    page_findings: list[dict[str, Any]] = []

    for page in pages_with_schema:
        types = set(page.all_types)
        expected = _expected_types_for(page.url)
        non_generic_types = types - GENERIC_SCHEMA_TYPES
        if expected and not (types & expected):
            misleading.append(
                {
                    "url": page.url,
                    "expected_types": sorted(expected),
                    "found_types": sorted(types),
                }
            )
        if not non_generic_types and types:
            generic_only.append(page.url)
        risky_here = sorted(types & PROHIBITED_OR_RISKY_SCHEMA_TYPES)
        if risky_here:
            prohibited.append({"url": page.url, "risky_types": risky_here})
        unrecognised = sorted(types - KNOWN_SCHEMA_TYPES)
        if unrecognised:
            unknown_types.append({"url": page.url, "types": unrecognised})
        page_findings.append(
            {
                **_per_page_value(page),
                "expected_types": sorted(expected),
                "non_generic_types": sorted(non_generic_types),
            }
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one schema type present on every successfully-fetched page",
        passed=len(pages_without_schema) == 0,
        evidence={
            "pages_total": len(pages),
            "pages_with_schema": len(pages_with_schema),
            "pages_without_schema": pages_without_schema,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Schema types present align with the page's content category (URL-path heuristic)",
        passed=len(misleading) == 0,
        evidence={
            "misleading": misleading,
            "misleading_count": len(misleading),
            "method": "url_path_pattern_match",
        },
        notes=(
            "URL-path heuristic only; pages whose path doesn't match any known "
            "pattern are skipped in this rule rather than guessed."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No misleading or invented type declarations (every type is a recognised schema.org type)",
        passed=len(unknown_types) == 0,
        evidence={
            "unrecognised": unknown_types,
            "unrecognised_count": len(unknown_types),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Schema is more specific than bare WebPage / Thing where a specific type fits",
        passed=len(generic_only) == 0,
        evidence={
            "generic_only_pages": generic_only,
            "generic_types": sorted(GENERIC_SCHEMA_TYPES),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Multiple types per page are composed via @graph rather than competing duplicates",
        passed=True,  # Soft signal; we record graph-ref counts rather than fail.
        evidence={
            "pages_with_graph_refs": sum(
                1 for p in pages_with_schema if p.graph_refs
            ),
            "pages_with_multiple_types_no_graph": sum(
                1
                for p in pages_with_schema
                if len(p.all_types) > 1 and not p.graph_refs
            ),
        },
        notes="Soft check: many sites legitimately use multiple disconnected blocks; recorded for advisory.",
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="No prohibited / restricted types declared on inappropriate content (HowTo, FAQPage)",
        passed=len(prohibited) == 0,
        evidence={
            "prohibited_findings": prohibited,
            "restricted_types": sorted(PROHIBITED_OR_RISKY_SCHEMA_TYPES),
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6]
    overall_pass = (
        rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed and rule_6.passed
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-21",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_total": len(pages),
            "pages_with_schema": len(pages_with_schema),
            "pages_without_schema_count": len(pages_without_schema),
            "all_types_seen": sorted({t for p in pages_with_schema for t in p.all_types}),
            "page_findings": page_findings,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.schema_type_appropriateness",
        ],
    )


# ─── P1-22 — Schema markup completeness and validity ────────────────────────


def _absolute_urlish(value: Any) -> bool:
    """Crude check: a URL property should look absolute."""
    if not isinstance(value, str):
        return False
    return value.startswith(("http://", "https://", "//"))


def _required_violations(block: SchemaBlock) -> list[dict[str, Any]]:
    """Return the per-type required-property gaps for a schema block."""
    out: list[dict[str, Any]] = []
    raw_keys = {k for k in block.raw.keys() if not k.startswith("@")}
    for t in block.types:
        required = GOOGLE_REQUIRED_PROPERTIES.get(t)
        if required is None:
            continue
        missing = sorted(required - raw_keys)
        if missing:
            out.append({"type": t, "missing_required": missing})
    return out


def _recommended_gaps(block: SchemaBlock) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw_keys = {k for k in block.raw.keys() if not k.startswith("@")}
    for t in block.types:
        recommended = GOOGLE_RECOMMENDED_PROPERTIES.get(t)
        if recommended is None:
            continue
        missing = sorted(recommended - raw_keys)
        if missing:
            out.append({"type": t, "missing_recommended": missing})
    return out


@register_extractor("P1-22")
async def capture_p1_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-22 — Schema markup completeness and validity (Consensus, 9 rules).

    Validity here = parseable, schema.org context, recognised type,
    URL-shaped properties absolute, required Google rich-result props
    populated. We can't run Google's Rich Results Test offline, but we
    enforce its required-property registry so the variable provides a
    defensible structural validity check.

    "Schema content matches visible content" (rule 7) is partially
    enforceable without LLM help — we surface it as a noted soft
    check rather than a hard pass/fail.
    """
    captured_at = _now()
    pages = site.successful_structured_data
    if not pages:
        return _no_pages_unmeasurable(
            ctx, site, "P1-22", EvidenceWeight.CONSENSUS, captured_at
        )

    pages_with_parse_errors: list[dict[str, Any]] = []
    blocks_total = 0
    blocks_schema_org = 0
    blocks_with_required_gaps: list[dict[str, Any]] = []
    blocks_with_recommended_gaps: list[dict[str, Any]] = []
    non_absolute_urls: list[dict[str, Any]] = []
    multi_block_no_graph: list[dict[str, Any]] = []
    blocks_unrecognised_type: list[dict[str, Any]] = []

    for page in pages:
        if page.json_ld_parse_errors:
            pages_with_parse_errors.append(
                {"url": page.url, "errors": list(page.json_ld_parse_errors)}
            )
        page_blocks = page.blocks
        blocks_total += len(page_blocks)
        for block in page_blocks:
            if block.is_schema_org:
                blocks_schema_org += 1
            req = _required_violations(block)
            if req:
                blocks_with_required_gaps.append(
                    {"url": page.url, "syntax": block.syntax, "violations": req}
                )
            rec = _recommended_gaps(block)
            if rec:
                blocks_with_recommended_gaps.append(
                    {"url": page.url, "syntax": block.syntax, "missing": rec}
                )
            for url_field in ("url", "logo", "image", "sameAs"):
                v = block.raw.get(url_field)
                if isinstance(v, str) and v and not _absolute_urlish(v):
                    non_absolute_urls.append(
                        {
                            "url": page.url,
                            "syntax": block.syntax,
                            "field": url_field,
                            "value": v,
                        }
                    )
            unknown = sorted(set(block.types) - KNOWN_SCHEMA_TYPES)
            if unknown:
                blocks_unrecognised_type.append(
                    {
                        "url": page.url,
                        "syntax": block.syntax,
                        "unknown_types": unknown,
                    }
                )

        if len(page_blocks) > 1 and not page.graph_refs:
            # Page has multiple structured-data blocks but they don't share
            # any @id references. Soft signal — many sites legitimately do
            # this — but worth surfacing.
            multi_block_no_graph.append(
                {
                    "url": page.url,
                    "block_count": len(page_blocks),
                    "types": list(page.all_types),
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="JSON-LD blocks parse without syntax errors site-wide",
        passed=len(pages_with_parse_errors) == 0,
        evidence={
            "pages_with_parse_errors": pages_with_parse_errors,
            "pages_total": len(pages),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Every type declared is a recognised schema.org type",
        passed=len(blocks_unrecognised_type) == 0,
        evidence={
            "unrecognised_typed_blocks": blocks_unrecognised_type,
            "unrecognised_count": len(blocks_unrecognised_type),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="@context resolves to schema.org for blocks declared as schema",
        passed=blocks_schema_org > 0 if blocks_total > 0 else True,
        evidence={
            "blocks_total": blocks_total,
            "blocks_schema_org": blocks_schema_org,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Google-required properties populated for each declared type",
        passed=len(blocks_with_required_gaps) == 0,
        evidence={
            "required_property_gaps": blocks_with_required_gaps,
            "gap_count": len(blocks_with_required_gaps),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Google-recommended properties populated where applicable (advisory)",
        passed=True,
        evidence={
            "recommended_property_gaps": blocks_with_recommended_gaps,
            "advisory_count": len(blocks_with_recommended_gaps),
        },
        notes="Recommended properties are advisory; absence does not fail the variable.",
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="URL-shaped properties (url, logo, image, sameAs) are absolute",
        passed=len(non_absolute_urls) == 0,
        evidence={
            "non_absolute_url_fields": non_absolute_urls,
            "violation_count": len(non_absolute_urls),
        },
    )
    rule_7 = _schema_visible_match_rule(site)
    rule_8 = RuleResult(
        rule_id=8,
        rule_text="No spam patterns (keyword-stuffed properties, fabricated reviews)",
        passed=True,
        evidence={
            "method": "deferred_to_h1c_llm_evaluation",
        },
        notes="Spam detection deferred to H1c LLM evaluation.",
    )
    rule_9 = RuleResult(
        rule_id=9,
        rule_text=(
            "Where multiple schema blocks coexist on a page, they are "
            "interconnected via @graph + @id rather than being competing duplicates"
        ),
        passed=len(multi_block_no_graph) == 0,
        evidence={
            "multi_block_no_graph_pages": multi_block_no_graph,
            "soft_signal_count": len(multi_block_no_graph),
        },
        notes="Soft signal: many sites use disconnected blocks legitimately.",
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6, rule_7, rule_8, rule_9]
    # Hard rules for pass/fail: 1, 2, 3, 4, 6, 7 (rule 7 is LLM-backed).
    # Rule 7 only counts when it reached a conclusive verdict. When it did not
    # (LLM layer unavailable, or gaps that make "no failures" unprovable) it is
    # excluded from the verdict and the capture degrades to PARTIAL below, so an
    # LLM outage can never manufacture a clean PASS.
    llm_conclusive = bool(rule_7.evidence.get("conclusive", True))
    overall_pass = (
        rule_1.passed
        and rule_2.passed
        and rule_3.passed
        and rule_4.passed
        and rule_6.passed
        and (rule_7.passed if llm_conclusive else True)
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-22",
        captured_at=captured_at,
        # A deterministic failure is still a genuine failure. But we cannot claim
        # a full PASS while an LLM-backed rule went unevaluated, so that case is
        # PARTIAL, matching how the fully-LLM variables degrade.
        status=(
            (CaptureStatus.PASSED if llm_conclusive else CaptureStatus.PARTIAL)
            if overall_pass
            else CaptureStatus.FAILED
        ),
        value={
            "schema_visible_match_conclusive": llm_conclusive,
            "pages_total": len(pages),
            "blocks_total": blocks_total,
            "blocks_schema_org": blocks_schema_org,
            "pages_with_parse_errors_count": len(pages_with_parse_errors),
            "required_property_gap_count": len(blocks_with_required_gaps),
            "recommended_property_gap_count": len(blocks_with_recommended_gaps),
            "non_absolute_url_count": len(non_absolute_urls),
            "unrecognised_type_block_count": len(blocks_unrecognised_type),
            "multi_block_no_graph_count": len(multi_block_no_graph),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "google.rich_results_required_properties_registry",
        ],
    )


# ─── P1-47 — Breadcrumb navigation and BreadcrumbList schema ────────────────


def _breadcrumb_items(block: SchemaBlock) -> list[dict[str, Any]]:
    raw_items = block.raw.get("itemListElement")
    if not isinstance(raw_items, list):
        return []
    out: list[dict[str, Any]] = []
    for el in raw_items:
        if isinstance(el, dict):
            out.append(el)
    return out


@register_extractor("P1-47")
async def capture_p1_47(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-47 — Breadcrumb navigation and BreadcrumbList schema (Consensus).

    BreadcrumbList is expected on every non-homepage URL. With only a
    homepage in the URL set we record `unmeasurable` because there's
    nothing meaningful to evaluate. With non-homepage pages, we check
    presence + structural validity (positions sequential from 1, items
    have name + item URL, URLs absolute). Visible-vs-schema match is
    deferred — needs DOM extraction we don't have offline.
    """
    captured_at = _now()
    pages = site.successful_structured_data
    if not pages:
        return _no_pages_unmeasurable(
            ctx, site, "P1-47", EvidenceWeight.CONSENSUS, captured_at
        )

    non_homepage = [p for p in pages if not _is_homepage(p.url, site)]
    if not non_homepage:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-47",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "only homepage was fetched; breadcrumbs apply to non-homepage URLs",
                "pages_total": len(pages),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "http.html_fetch",
                "extruct.parse_structured_data",
            ],
            errors=["no non-homepage URLs in the audit set"],
        )

    pages_with_bc: list[dict[str, Any]] = []
    pages_without_bc: list[str] = []
    structural_violations: list[dict[str, Any]] = []
    short_breadcrumbs: list[dict[str, Any]] = []

    for page in non_homepage:
        bc_blocks = page.blocks_of_type("BreadcrumbList")
        if not bc_blocks:
            pages_without_bc.append(page.url)
            continue
        primary = bc_blocks[0]
        items = _breadcrumb_items(primary)
        positions = [
            it.get("position")
            for it in items
            if isinstance(it.get("position"), int)
        ]
        sequential = positions == list(range(1, len(positions) + 1)) if positions else False
        names_present = all(isinstance(it.get("name"), str) for it in items)
        item_urls = []
        for it in items:
            v = it.get("item")
            if isinstance(v, dict):
                v = v.get("@id") or v.get("url")
            if isinstance(v, str):
                item_urls.append(v)
        urls_absolute = all(_absolute_urlish(u) for u in item_urls)

        if not (sequential and names_present and urls_absolute):
            structural_violations.append(
                {
                    "url": page.url,
                    "positions_sequential_from_1": sequential,
                    "all_items_have_name": names_present,
                    "all_item_urls_absolute": urls_absolute,
                    "item_count": len(items),
                }
            )

        if len(items) < 2:
            short_breadcrumbs.append({"url": page.url, "items": len(items)})

        pages_with_bc.append(
            {
                "url": page.url,
                "items": len(items),
                "positions": positions,
                "all_items_have_name": names_present,
                "all_item_urls_absolute": urls_absolute,
                "positions_sequential_from_1": sequential,
            }
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Visible breadcrumb trail present (deferred — needs rendered DOM)",
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_or_dom_extraction"},
        notes="Visible breadcrumb detection needs rendered DOM; not available offline.",
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="BreadcrumbList schema present on every non-homepage URL",
        passed=len(pages_without_bc) == 0,
        evidence={
            "non_homepage_total": len(non_homepage),
            "pages_with_breadcrumblist": len(pages_with_bc),
            "pages_without_breadcrumblist": pages_without_bc,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Visible and schema breadcrumbs match (deferred to H1c)",
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_evaluation"},
        notes="Comparison of rendered text vs schema deferred to H1c.",
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Breadcrumbs include Home + at least one ancestor (item count >= 2)",
        passed=len(short_breadcrumbs) == 0,
        evidence={
            "short_breadcrumbs": short_breadcrumbs,
            "violation_count": len(short_breadcrumbs),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Each item declares position + name + item URL",
        passed=all(
            v["all_items_have_name"]
            and v["positions_sequential_from_1"]
            and v["all_item_urls_absolute"]
            for v in pages_with_bc
        ),
        evidence={
            "pages_with_violations": [
                v for v in pages_with_bc
                if not (
                    v["all_items_have_name"]
                    and v["positions_sequential_from_1"]
                    and v["all_item_urls_absolute"]
                )
            ],
        },
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="Order matches navigation hierarchy (deferred — needs site graph)",
        passed=True,
        evidence={"method": "deferred_to_h1b_link_graph"},
        notes="Hierarchy alignment needs the link-graph layer; deferred to H1b.",
    )
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="Schema validates: positions sequential from 1, item URLs absolute",
        passed=len(structural_violations) == 0,
        evidence={
            "structural_violations": structural_violations,
            "violation_count": len(structural_violations),
        },
    )
    rule_8 = RuleResult(
        rule_id=8,
        rule_text="BreadcrumbList type recognised",
        passed=True,
        evidence={"checked": True},
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6, rule_7, rule_8]
    overall_pass = rule_2.passed and rule_4.passed and rule_5.passed and rule_7.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-47",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "non_homepage_pages": len(non_homepage),
            "pages_with_breadcrumblist": len(pages_with_bc),
            "pages_without_breadcrumblist": len(pages_without_bc),
            "structural_violations": len(structural_violations),
            "short_breadcrumb_pages": len(short_breadcrumbs),
            "page_findings": pages_with_bc,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.breadcrumblist_validation",
        ],
    )
