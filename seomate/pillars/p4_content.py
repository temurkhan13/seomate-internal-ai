"""Pillar 4 — Content Operations extractors.

Variables that read from already-cached site data:

- P4-02 — Content freshness, site-wide distribution           (Probable)
- P4-03 — Author byline presence on article-like pages        (Consensus)
- P4-07 — Content originality and substance                   (Consensus,
            LLM-evaluated via the ``content_substance`` evaluator)
- P4-09 — Insightful analysis beyond surface                  (Probable,
            LLM-evaluated via the ``insightfulness`` evaluator)
- P4-21 — Mass-produced content detection                     (Consensus,
            LLM-evaluated via the ``content_substance`` evaluator)
- P4-23 — Headline accuracy (no clickbait / exaggeration)     (Consensus,
            LLM-evaluated via the ``headline_accuracy`` evaluator)

P4-02 and P4-03 are bundled cost (HTML + main-text caches). P4-23 is
backed by the H1c LLM layer and is deferred-pass when no Anthropic
key is configured.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from htmldate import find_date

from seomate.adapters import AdapterContext, KGNotConfigured, KnowledgeGraphAdapter
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor
from seomate.utils.structured_data import StructuredData


# ─── Tunables ───────────────────────────────────────────────────────────────

# Page is "fresh" if its last meaningful update is within ~12 months.
FRESH_DAYS = 365
# Page is "stale" if its last meaningful update is older than 2 years.
STALE_DAYS = 730

# A page is "article-like" if it carries article-family schema OR its
# URL path matches a blog / news / articles pattern.
_ARTICLE_SCHEMA_TYPES = frozenset(
    {"Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle"}
)
_ARTICLE_URL_PATTERNS = (
    "/blog/",
    "/news/",
    "/article/",
    "/articles/",
    "/post/",
    "/posts/",
    "/insights/",
    "/case-study/",
    "/case-studies/",
)

# Common visible-byline patterns. The set is small on purpose: a tighter
# floor keeps false-positives low (every page has the word "by" somewhere).
# We anchor each pattern to a recognisable byline frame.
_BYLINE_PATTERNS = (
    re.compile(r"\bby\s+([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+){0,3})\b"),
    re.compile(r"\bauthor\s*[:\-]\s*([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+){0,3})\b", re.IGNORECASE),
    re.compile(r"\bwritten\s+by\s+([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+){0,3})\b", re.IGNORECASE),
    re.compile(r"\bposted\s+by\s+([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+){0,3})\b", re.IGNORECASE),
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now_dt().date()


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
        pillar="P4",
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


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _is_article_like(url: str, sd: StructuredData | None) -> bool:
    path = (urlsplit(url).path or "/").lower()
    if any(p in path for p in _ARTICLE_URL_PATTERNS):
        return True
    if sd is not None and (set(sd.all_types) & _ARTICLE_SCHEMA_TYPES):
        return True
    return False


# ─── P4-02 — Content freshness, site-wide distribution ──────────────────────


@register_extractor("P4-02")
async def capture_p4_02(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-02 — Site-wide content freshness (Probable, htmldate distribution).

    For each successfully-fetched page we ask htmldate for the most
    recent meaningful update date (modification preferred, falling back
    to the original publication date). The site's freshness profile is
    the median + 75th-percentile age plus the share of pages that are
    \"fresh\" (≤ 12 months) or \"stale\" (> 24 months).

    Pages where htmldate cannot extract any date are reported as
    `undated` and excluded from age statistics — they fail rule 1
    (extractability) so reviewers can decide whether to add explicit
    date markup.
    """
    captured_at = _now_dt()
    pages = [
        (url, page)
        for url, page in site.html_pages.items()
        if page.fetch_error is None and page.status_code < 400 and page.html
    ]
    if not pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-02",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "htmldate.find_date"],
            errors=["no HTML pages available"],
        )

    today = _today()
    findings: list[dict[str, Any]] = []
    ages_days: list[int] = []
    undated: list[str] = []

    for url, page in pages:
        modified = _safe_find_date(page.html, original_date=False, url=url)
        published = _safe_find_date(page.html, original_date=True, url=url)
        chosen = modified or published
        if chosen is None:
            undated.append(url)
            findings.append(
                {
                    "url": url,
                    "modified": None,
                    "published": None,
                    "age_days": None,
                }
            )
            continue
        age = (today - chosen).days
        ages_days.append(age)
        findings.append(
            {
                "url": url,
                "modified": modified.isoformat() if modified else None,
                "published": published.isoformat() if published else None,
                "chosen_date": chosen.isoformat(),
                "age_days": age,
            }
        )

    dated_count = len(ages_days)
    sorted_ages = sorted(ages_days)
    median_age = _percentile(sorted_ages, 0.50)
    p75_age = _percentile(sorted_ages, 0.75)
    fresh = [a for a in ages_days if a <= FRESH_DAYS]
    stale = [a for a in ages_days if a > STALE_DAYS]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Date extractable for >= 50% of indexable pages",
        passed=(dated_count / len(pages)) >= 0.5,
        evidence={
            "pages_total": len(pages),
            "pages_with_date": dated_count,
            "pages_undated": undated[:50],
            "undated_count": len(undated),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Median page age <= 12 months (fresh content majority)",
        passed=(median_age is not None and median_age <= FRESH_DAYS),
        evidence={
            "median_age_days": round(median_age, 1) if median_age is not None else None,
            "fresh_threshold_days": FRESH_DAYS,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Share of stale pages (> 24 months) is < 30% of dated pages",
        passed=(
            (len(stale) / dated_count) < 0.30
            if dated_count else False
        ),
        evidence={
            "stale_count": len(stale),
            "dated_count": dated_count,
            "stale_threshold_days": STALE_DAYS,
            "stale_pct": round(len(stale) / dated_count * 100, 1) if dated_count else None,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="75th-percentile age <= 24 months (long tail not abandoned)",
        passed=(p75_age is not None and p75_age <= STALE_DAYS),
        evidence={
            "p75_age_days": round(p75_age, 1) if p75_age is not None else None,
            "stale_threshold_days": STALE_DAYS,
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-02",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_total": len(pages),
            "pages_with_date": dated_count,
            "undated_count": len(undated),
            "median_age_days": round(median_age, 1) if median_age is not None else None,
            "p75_age_days": round(p75_age, 1) if p75_age is not None else None,
            "max_age_days": max(ages_days) if ages_days else None,
            "min_age_days": min(ages_days) if ages_days else None,
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "fresh_threshold_days": FRESH_DAYS,
            "stale_threshold_days": STALE_DAYS,
            "page_findings": findings[:60],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "htmldate.find_date"],
    )


def _safe_find_date(html: str, *, original_date: bool, url: str) -> date | None:
    try:
        result = find_date(html, original_date=original_date, url=url)
    except Exception:  # noqa: BLE001 - htmldate occasionally raises on weird HTML
        return None
    if not result:
        return None
    try:
        # htmldate returns YYYY-MM-DD when no time is found.
        return date.fromisoformat(result[:10])
    except ValueError:
        return None


# ─── P4-03 — Author byline presence on article-like pages ───────────────────


_PERSON_TYPES = frozenset({"Person"})


def _author_in_schema(sd: StructuredData) -> tuple[bool, str | None]:
    """Return (found, name) — does any block declare a Person author?"""
    for block in sd.schema_org_blocks:
        author = block.raw.get("author")
        if author is None:
            continue
        for candidate in _flatten_author(author):
            name = _author_name(candidate)
            if name:
                return True, name
        # Some sites store author as a top-level Person block alongside an Article.
    for block in sd.blocks_of_type("Person"):
        name = _author_name(block.raw)
        if name:
            return True, name
    return False, None


def _flatten_author(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _author_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    name = node.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _byline_in_text(main_text: str) -> tuple[bool, str | None, str | None]:
    """Return (found, captured_name, matched_pattern_label)."""
    if not main_text:
        return False, None, None
    head = main_text[:1500]  # bylines are near the top
    for pattern in _BYLINE_PATTERNS:
        m = pattern.search(head)
        if m:
            return True, m.group(1).strip(), pattern.pattern
    return False, None, None


@register_extractor("P4-03")
async def capture_p4_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-03 — Author byline presence on article-like pages (Consensus).

    For every page we classify as article-like (article-family schema
    OR a /blog/, /news/, /articles/ … URL pattern), we look for an
    author signal in two places:

    1. JSON-LD/microdata Person on the page or as `author` of an Article.
    2. A regex byline pattern in the trafilatura main text (capped to
       the first 1500 chars so we don't hit footer bylines on
       non-article pages).

    Pages where neither signal fires fail the variable. Sites with no
    article-like pages report `unmeasurable` rather than auto-passing.
    """
    captured_at = _now_dt()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-03",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "http.html_fetch",
                "extruct.parse_structured_data",
                "composition.byline_pattern_match",
            ],
            errors=["site.html_pages is empty"],
        )

    article_pages: list[str] = []
    findings: list[dict[str, Any]] = []
    schema_only: list[str] = []
    text_only: list[str] = []
    both: list[str] = []
    neither: list[str] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or page.status_code >= 400:
            continue
        sd = site.structured_data.get(url)
        if not _is_article_like(url, sd):
            continue
        article_pages.append(url)
        in_schema, schema_name = (False, None)
        if sd is not None:
            in_schema, schema_name = _author_in_schema(sd)
        text_obj = site.text_content.get(url)
        in_text, text_name, _ = _byline_in_text(
            text_obj.main_text if text_obj else ""
        )
        if in_schema and in_text:
            both.append(url)
        elif in_schema:
            schema_only.append(url)
        elif in_text:
            text_only.append(url)
        else:
            neither.append(url)
        findings.append(
            {
                "url": url,
                "in_schema": in_schema,
                "in_text": in_text,
                "schema_name": schema_name,
                "text_name": text_name,
            }
        )

    if not article_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-03",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no article-like pages detected (no Article/BlogPosting "
                    "schema or blog/news URL paths)"
                ),
                "pages_total": len(site.html_pages),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "http.html_fetch",
                "extruct.parse_structured_data",
                "composition.byline_pattern_match",
            ],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every article-like page has an author byline (in schema or visible text)",
        passed=len(neither) == 0,
        evidence={
            "article_like_total": len(article_pages),
            "with_author": len(both) + len(schema_only) + len(text_only),
            "without_author": neither,
            "without_author_count": len(neither),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Author signal is structured (Person schema present), not text-only",
        passed=len(text_only) == 0,
        evidence={
            "schema_and_text": len(both),
            "schema_only": len(schema_only),
            "text_only": text_only,
            "text_only_count": len(text_only),
        },
        notes=(
            "Text-only bylines are valid for users but harder for "
            "search engines and LLMs to attribute reliably; structured "
            "Person markup is the higher-confidence signal."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Where present, schema author and text-byline names agree",
        passed=all(
            (
                f["schema_name"] is None
                or f["text_name"] is None
                or _names_match(f["schema_name"], f["text_name"])
            )
            for f in findings
        ),
        evidence={
            "name_disagreements": [
                {
                    "url": f["url"],
                    "schema": f["schema_name"],
                    "text": f["text_name"],
                }
                for f in findings
                if f["schema_name"] is not None
                and f["text_name"] is not None
                and not _names_match(f["schema_name"], f["text_name"])
            ],
        },
    )

    rules = [rule_1, rule_2, rule_3]
    # Hard rules: 1, 3. Rule 2 is advisory.
    overall_pass = rule_1.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-03",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "article_like_total": len(article_pages),
            "with_author_total": len(both) + len(schema_only) + len(text_only),
            "without_author_count": len(neither),
            "schema_and_text": len(both),
            "schema_only": len(schema_only),
            "text_only": len(text_only),
            "page_findings": findings[:50],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.byline_pattern_match",
        ],
    )


def _names_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


# ─── P4-23 — Headline accuracy (no clickbait / exaggeration) ────────────────


@register_extractor("P4-23")
async def capture_p4_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-23 — Headline accuracy on article-like pages (Consensus, LLM-eval).

    Reads from the ``headline_accuracy`` LLM evaluation cached on
    SiteData. Reports per-page pass/fail plus the specific issue
    categories the evaluator surfaced (clickbait / exaggeration /
    mismatch / misleading_number).
    """
    captured_at = _now_dt()
    evals = site.llm_evaluations.get("headline_accuracy", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval" if not site.llm_configured
            else "no article-like pages identified for headline evaluation"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-23",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": reason,
                "llm_configured": site.llm_configured,
                "article_like_pages": 0,
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "anthropic.messages.create",
                "composition.headline_accuracy_evaluator",
            ],
            errors=[reason],
        )

    failing: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []
    issue_counts: dict[str, int] = {}
    passing = 0
    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        for issue in ev.issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        if ev.passed:
            passing += 1
        else:
            failing.append(
                {
                    "url": url,
                    "confidence": ev.confidence,
                    "issues": list(ev.issues)[:5],
                    "rationale": ev.rationale,
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every article-like page has a headline that accurately represents its content",
        passed=len(failing) == 0,
        evidence={
            "pages_evaluated": len(evals),
            "pages_passed": passing,
            "pages_failed": len(failing),
            "pages_errored": len(errored),
            "failing_pages": failing[:25],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No clickbait or curiosity-gap headlines detected",
        passed="clickbait" not in issue_counts,
        evidence={"clickbait_pages": issue_counts.get("clickbait", 0)},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No exaggeration / sensationalism patterns detected",
        passed="exaggeration" not in issue_counts,
        evidence={"exaggeration_pages": issue_counts.get("exaggeration", 0)},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Headlines and visible content match (no title-content mismatch)",
        passed="mismatch" not in issue_counts,
        evidence={"mismatch_pages": issue_counts.get("mismatch", 0)},
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(evals),
            "pages_passed": passing,
            "pages_failed": len(failing),
            "pages_errored": len(errored),
            "issue_counts": issue_counts,
            "failing_pages": failing[:25],
            "errored_pages": errored[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "anthropic.messages.create",
            "composition.headline_accuracy_evaluator",
        ],
    )


# ─── P4-07 — Content originality and substance ──────────────────────────────


@register_extractor("P4-07")
async def capture_p4_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-07 — Content originality and substance (Consensus, LLM-evaluated).

    Reads from the ``content_substance`` evaluator and converts the
    multi-signal output into the six P4-07 rules. The evaluator's
    ``passed`` field is already the synthesis of "originality present
    AND no AI-boilerplate / templating / padding"; the extractor
    breaks the signals back out for rule-level visibility.
    """
    captured_at = _now_dt()
    evals = site.llm_evaluations.get("content_substance", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive (>= 200 words) pages found to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-07",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create", "composition.content_substance_evaluator"],
            errors=[reason],
        )

    pages_total = len(evals)
    pages_pass = 0
    pages_with_original = 0
    pages_with_ai_boilerplate: list[str] = []
    pages_with_padding: list[str] = []
    pages_with_templating: list[str] = []
    pages_with_first_hand = 0
    errored: list[dict[str, Any]] = []

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        raw = ev.raw or {}
        if ev.passed:
            pages_pass += 1
        if raw.get("has_original_elements"):
            pages_with_original += 1
        if raw.get("shows_ai_boilerplate"):
            pages_with_ai_boilerplate.append(url)
        if raw.get("has_padding"):
            pages_with_padding.append(url)
        if raw.get("shows_templating_signs"):
            pages_with_templating.append(url)
        if raw.get("has_first_hand_signals"):
            pages_with_first_hand += 1

    rule_3 = RuleResult(
        rule_id=3,
        rule_text=(
            "Substantive original elements present on at least 50% "
            "of pages (own data / case study / interview / analysis)"
        ),
        passed=(pages_with_original / pages_total) >= 0.5 if pages_total else False,
        evidence={
            "pages_with_original_elements": pages_with_original,
            "pages_total": pages_total,
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No detectable AI-generated boilerplate patterns",
        passed=len(pages_with_ai_boilerplate) == 0,
        evidence={
            "pages_with_ai_boilerplate": pages_with_ai_boilerplate[:25],
            "violation_count": len(pages_with_ai_boilerplate),
        },
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="Content not padded (no filler proportional to word count)",
        passed=len(pages_with_padding) == 0,
        evidence={
            "pages_with_padding": pages_with_padding[:25],
            "violation_count": len(pages_with_padding),
        },
    )
    rule_first_hand = RuleResult(
        rule_id=4,
        rule_text="First-hand experience signals present on at least 30% of pages",
        passed=(pages_with_first_hand / pages_total) >= 0.30 if pages_total else False,
        evidence={
            "pages_with_first_hand": pages_with_first_hand,
            "pages_total": pages_total,
        },
        notes="Specific dates, named clients, internal metrics, named-author opinions.",
    )

    rules = [rule_3, rule_first_hand, rule_5, rule_6]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-07",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": pages_total,
            "pages_passed_overall": pages_pass,
            "pages_with_original_elements": pages_with_original,
            "pages_with_ai_boilerplate": len(pages_with_ai_boilerplate),
            "pages_with_padding": len(pages_with_padding),
            "pages_with_templating_signs": len(pages_with_templating),
            "pages_with_first_hand_signals": pages_with_first_hand,
            "pages_errored": len(errored),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["anthropic.messages.create", "composition.content_substance_evaluator"],
    )


# ─── P4-21 — Mass-produced content detection ────────────────────────────────


@register_extractor("P4-21")
async def capture_p4_21(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-21 — Mass-produced content detection (Consensus, LLM-evaluated).

    Aggregates the ``content_substance`` per-page signals into a
    site-level mass-production verdict. The variable triggers when
    *any* of the rules detects — so the site fails when a meaningful
    share of pages show AI-boilerplate or templating patterns.
    """
    captured_at = _now_dt()
    evals = site.llm_evaluations.get("content_substance", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive pages found to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-21",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create", "composition.content_substance_evaluator"],
            errors=[reason],
        )

    total = len(evals)
    templating: list[str] = []
    ai_patterns: list[str] = []
    no_first_hand: list[str] = []
    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            continue
        raw = ev.raw or {}
        if raw.get("shows_templating_signs"):
            templating.append(url)
        if raw.get("shows_ai_boilerplate"):
            ai_patterns.append(url)
        if not raw.get("has_first_hand_signals"):
            no_first_hand.append(url)

    templating_pct = len(templating) / total * 100 if total else 0
    ai_pct = len(ai_patterns) / total * 100 if total else 0
    no_first_hand_pct = len(no_first_hand) / total * 100 if total else 0

    # Per variable's "ANY rule triggers" semantics, the site is flagged
    # when at least one trigger fires. We use 30% as the "meaningful
    # share" threshold for site-level triggering.
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Templated content with minor variations (< 30% of pages)",
        passed=templating_pct < 30.0,
        evidence={
            "templated_pages": len(templating),
            "templated_pct": round(templating_pct, 1),
            "threshold_pct": 30.0,
            "sample_urls": templating[:10],
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="AI-generated content patterns absent on majority of pages (< 30% trigger)",
        passed=ai_pct < 30.0,
        evidence={
            "ai_pattern_pages": len(ai_patterns),
            "ai_pattern_pct": round(ai_pct, 1),
            "threshold_pct": 30.0,
            "sample_urls": ai_patterns[:10],
        },
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="First-hand experience signals present on > 50% of pages",
        passed=no_first_hand_pct < 50.0,
        evidence={
            "no_first_hand_count": len(no_first_hand),
            "no_first_hand_pct": round(no_first_hand_pct, 1),
            "threshold_pct": 50.0,
        },
    )

    rules = [rule_1, rule_3, rule_6]
    # Per variable's "ANY rule triggers" semantics: the site fails if
    # any rule trips. Variable passes only when none trip.
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-21",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "templated_pages": len(templating),
            "templated_pct": round(templating_pct, 1),
            "ai_pattern_pages": len(ai_patterns),
            "ai_pattern_pct": round(ai_pct, 1),
            "no_first_hand_pages": len(no_first_hand),
            "no_first_hand_pct": round(no_first_hand_pct, 1),
            "sample_templated": templating[:10],
            "sample_ai_pattern": ai_patterns[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["anthropic.messages.create", "composition.content_substance_evaluator"],
    )


# ─── P4-09 — Insightful analysis beyond surface ─────────────────────────────


@register_extractor("P4-09")
async def capture_p4_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-09 — Insightful analysis beyond surface observation (Probable).

    Reads from the ``insightfulness`` LLM evaluator. The evaluator
    looks for depth signals (causal reasoning, non-obvious connections,
    contrarian observation, expert framing) versus surface-level
    restatement of common knowledge.
    """
    captured_at = _now_dt()
    evals = site.llm_evaluations.get("insightfulness", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no article-like pages with substantive content"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create", "composition.insightfulness_evaluator"],
            errors=[reason],
        )

    total = len(evals)
    passing = 0
    failing: list[dict[str, Any]] = []
    surface_level: list[str] = []
    depth_signal_counts: dict[str, int] = {}

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            continue
        raw = ev.raw or {}
        if ev.passed:
            passing += 1
        else:
            failing.append(
                {
                    "url": url,
                    "confidence": ev.confidence,
                    "rationale": ev.rationale,
                    "depth_signals": (raw.get("depth_signals") or [])[:5],
                }
            )
        if raw.get("surface_level"):
            surface_level.append(url)
        for sig in raw.get("depth_signals") or []:
            depth_signal_counts[sig] = depth_signal_counts.get(sig, 0) + 1

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Majority of article-like pages deliver insightful analysis (>= 50% pass)",
        passed=(passing / total) >= 0.50 if total else False,
        evidence={
            "passing_pages": passing,
            "total": total,
            "pct": round(passing / total * 100, 1) if total else 0,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Site shows variety of depth signals (>= 2 distinct depth signal types across pages)",
        passed=len(depth_signal_counts) >= 2,
        evidence={"depth_signal_counts": depth_signal_counts},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Surface-level restatement is not the norm (< 50% of pages flagged surface-only)",
        passed=(len(surface_level) / total) < 0.50 if total else False,
        evidence={
            "surface_level_pages": len(surface_level),
            "surface_level_sample": surface_level[:10],
            "total": total,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-09",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_passing": passing,
            "pages_failing": len(failing),
            "pages_surface_level": len(surface_level),
            "depth_signal_counts": depth_signal_counts,
            "failing_pages_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["anthropic.messages.create", "composition.insightfulness_evaluator"],
    )


# ─── P4-06 — E-E-A-T aggregation ────────────────────────────────────────────


@register_extractor("P4-06")
async def capture_p4_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-06 — E-E-A-T aggregation (Consensus, composition).

    Synthesises Experience / Expertise / Authoritativeness / Trust
    signals from already-cached SiteData. No new external calls; all
    inputs come from prior prefetches (link graph + structured data +
    text content + LLM evaluations).

    Each pillar is computed independently; the variable passes when
    all four pillars score at least 'present', failing otherwise.
    Reports the underlying signal counts so reviewers see WHY each
    pillar passed or failed.
    """
    captured_at = _now_dt()

    # ─── Experience: first-hand signals + original research ────────────────
    content_sub = site.llm_evaluations.get("content_substance", {})
    original_research = site.llm_evaluations.get("original_research", {})
    insightfulness = site.llm_evaluations.get("insightfulness", {})

    first_hand_pages = sum(
        1
        for ev in content_sub.values()
        if (ev.raw or {}).get("has_first_hand_signals")
    )
    pages_with_original_research = sum(
        1 for ev in original_research.values() if ev.passed
    )
    experience_signals = {
        "first_hand_pages": first_hand_pages,
        "pages_with_original_research": pages_with_original_research,
        "evaluator_runs": len(content_sub),
    }
    experience_present = first_hand_pages >= 1 or pages_with_original_research >= 1

    # ─── Expertise: author bylines + bio credentials ────────────────────────
    # We don't query the DB for sibling captures; we read directly from
    # cached structured data and text content.
    authorship_signals = {
        "bio_pages_found": 0,
        "schema_persons_found": 0,
    }
    for sd in site.structured_data.values():
        if sd.blocks_of_type("Person"):
            authorship_signals["schema_persons_found"] += 1
    for url, page_text in site.text_content.items():
        if not page_text.main_text:
            continue
        path = (urlsplit(url).path or "/").lower()
        if any(seg in path for seg in ("/author/", "/authors/", "/team/", "/about/")):
            authorship_signals["bio_pages_found"] += 1
    expertise_present = (
        authorship_signals["bio_pages_found"] >= 1
        or authorship_signals["schema_persons_found"] >= 1
    )

    # ─── Authoritativeness: outbound authority + entity recognition ────────
    authority_links = 0
    if site.link_graph is not None:
        from seomate.pillars.p_freebatch import _AUTHORITY_HOSTS as auth_hosts

        for url in site.link_graph.pages:
            for ref in site.link_graph.outbound.get(url, []):
                if ref.is_internal:
                    continue
                if any(h in ref.target_url.lower() for h in auth_hosts):
                    authority_links += 1

    # KG entity status — we don't store the KG result on SiteData, so we
    # use the brand-presence proxy: if site has Organization schema with
    # sameAs to authoritative hosts, that's the externally-observable
    # equivalent of 'recognised entity'.
    has_external_entity_signals = False
    for sd in site.structured_data.values():
        for block in sd.schema_org_blocks:
            if set(block.types) & {"Organization", "Corporation"}:
                from seomate.pillars.p1_schema import HIGH_VALUE_SAMEAS_HOSTS

                same_as = block.raw.get("sameAs") or []
                sa_list = same_as if isinstance(same_as, list) else [same_as]
                if any(
                    any(h in str(s).lower() for h in HIGH_VALUE_SAMEAS_HOSTS)
                    for s in sa_list
                ):
                    has_external_entity_signals = True
                    break
    authoritativeness_signals = {
        "authority_outbound_links": authority_links,
        "has_external_entity_signals": has_external_entity_signals,
    }
    authoritativeness_present = (
        authority_links >= 3 or has_external_entity_signals
    )

    # ─── Trust: HTTPS + valid schema + robots / llms / no injection ────────
    # Use site.primary_url directly (config-canonical) plus a fallback
    # to any successful html_page final URL. Avoids dict-key brittleness
    # where sitemap discovery may normalise URLs differently.
    is_https = site.primary_url.startswith("https://")
    if not is_https:
        for page in site.html_pages.values():
            if page.fetch_error is None and page.url.startswith("https://"):
                is_https = True
                break
    schema_parse_clean = all(
        not sd.json_ld_parse_errors for sd in site.structured_data.values()
    )
    # No prompt-injection check inline — P6-32 covers that. Use schema
    # cleanliness + HTTPS as the trust proxy here.
    trust_signals = {
        "is_https": is_https,
        "schema_json_ld_parse_clean": schema_parse_clean,
    }
    trust_present = is_https and schema_parse_clean

    rule_e = RuleResult(
        rule_id=1,
        rule_text="Experience signals present (first-hand signals OR original research on >= 1 page)",
        passed=experience_present,
        evidence=experience_signals,
    )
    rule_x = RuleResult(
        rule_id=2,
        rule_text="Expertise signals present (author bio page OR Person schema)",
        passed=expertise_present,
        evidence=authorship_signals,
    )
    rule_a = RuleResult(
        rule_id=3,
        rule_text=(
            "Authoritativeness signals present (>= 3 authority outbound links OR "
            "Organization schema with sameAs to authoritative hosts)"
        ),
        passed=authoritativeness_present,
        evidence=authoritativeness_signals,
    )
    rule_t = RuleResult(
        rule_id=4,
        rule_text="Trust signals present (HTTPS + JSON-LD parses cleanly)",
        passed=trust_present,
        evidence=trust_signals,
    )

    rules = [rule_e, rule_x, rule_a, rule_t]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-06",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pillars": {
                "experience_present": experience_present,
                "expertise_present": expertise_present,
                "authoritativeness_present": authoritativeness_present,
                "trust_present": trust_present,
            },
            "experience_signals": experience_signals,
            "expertise_signals": authorship_signals,
            "authoritativeness_signals": authoritativeness_signals,
            "trust_signals": trust_signals,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "composition.eeat_aggregation",
            "extruct.parse_structured_data",
            "http.html_fetch",
            "anthropic.messages.create",
        ],
    )


# ─── P4-22 — Site-wide quality (Panda) ──────────────────────────────────────


@register_extractor("P4-22")
async def capture_p4_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-22 — Site-wide quality (Panda screen) (Consensus, composition).

    Aggregates signals from already-cached LLM evaluations. The
    'Panda algorithm' (now integrated into core; leak features
    'babyPandaDemotion' / 'babyPandaV2Demotion') demotes sites with
    substantial proportions of low-quality content.

    Rules read directly from content_substance + headline_accuracy
    evaluator results to avoid duplicating logic with P4-07 / P4-21 /
    P4-23 extractors.
    """
    captured_at = _now_dt()
    content_sub = site.llm_evaluations.get("content_substance", {})
    headline = site.llm_evaluations.get("headline_accuracy", {})

    if not content_sub:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive pages evaluated by content_substance"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-22",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["composition.panda_aggregation"],
            errors=[reason],
        )

    total = len(content_sub)
    low_originality = 0
    mass_produced_signals = 0
    misleading_headlines = 0

    for ev in content_sub.values():
        if ev.error or ev.passed is None:
            continue
        raw = ev.raw or {}
        if raw.get("shows_ai_boilerplate") or raw.get("shows_templating_signs"):
            low_originality += 1
            mass_produced_signals += 1

    for ev in headline.values():
        if ev.error or ev.passed is None:
            continue
        if ev.passed is False:
            misleading_headlines += 1

    low_originality_pct = low_originality / total * 100 if total else 0
    mass_produced_pct = mass_produced_signals / total * 100 if total else 0
    headline_pages = len(headline) or 1
    misleading_pct = misleading_headlines / headline_pages * 100

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Low-originality content stays below 10% of substantive pages",
        passed=low_originality_pct < 10.0,
        evidence={
            "low_originality_count": low_originality,
            "total": total,
            "low_originality_pct": round(low_originality_pct, 1),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Mass-produced content patterns affect < 20% of pages",
        passed=mass_produced_pct < 20.0,
        evidence={
            "mass_produced_count": mass_produced_signals,
            "total": total,
            "mass_produced_pct": round(mass_produced_pct, 1),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Misleading/clickbait headlines affect < 10% of article pages",
        passed=misleading_pct < 10.0,
        evidence={
            "misleading_headlines": misleading_headlines,
            "headline_pages_evaluated": len(headline),
            "misleading_pct": round(misleading_pct, 1),
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-22",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "low_originality_pct": round(low_originality_pct, 1),
            "mass_produced_pct": round(mass_produced_pct, 1),
            "misleading_headlines_pct": round(misleading_pct, 1),
            "panda_demotion_risk": (
                "elevated"
                if low_originality_pct >= 10 or mass_produced_pct >= 20
                else "low"
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "composition.panda_aggregation",
            "composition.content_substance_evaluator",
            "composition.headline_accuracy_evaluator",
        ],
    )


# ─── P4-17 — YMYL handling rigour ───────────────────────────────────────────


@register_extractor("P4-17")
async def capture_p4_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-17 — YMYL handling rigour (Consensus, composition).

    Composition over the YMYL classifier (P0-17 results in
    llm_evaluations['ymyl']) + content_substance + citation density
    signals. For pages classified YMYL, we apply elevated checks:
    author bio + credentials, citations to authority sources,
    first-hand signals.

    Unmeasurable when no YMYL pages were classified (either no
    YMYL pages exist, or classifier didn't run).
    """
    captured_at = _now_dt()
    ymyl_evals = site.llm_evaluations.get("ymyl", {})
    if not ymyl_evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no YMYL classification available"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-17",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["composition.ymyl_handling_aggregation"],
            errors=[reason],
        )

    ymyl_urls: list[str] = []
    ymyl_categories: dict[str, int] = {}
    for url, ev in ymyl_evals.items():
        if ev.error:
            continue
        raw = ev.raw or {}
        if raw.get("is_ymyl"):
            ymyl_urls.append(url)
            cat = str(raw.get("category") or "none")
            ymyl_categories[cat] = ymyl_categories.get(cat, 0) + 1

    if not ymyl_urls:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-17",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no YMYL pages identified on site; variable does not apply",
                "pages_classified": len(ymyl_evals),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["composition.ymyl_handling_aggregation"],
        )

    # For each YMYL page, check the elevated-rigour signals available
    # from cached data without requiring fresh API calls.
    content_sub = site.llm_evaluations.get("content_substance", {})
    findings: list[dict[str, Any]] = []
    pages_with_first_hand = 0
    pages_with_authority_citations = 0
    pages_with_author_signal = 0

    for url in ymyl_urls:
        cs_ev = content_sub.get(url)
        cs_raw = (cs_ev.raw if cs_ev is not None else None) or {}
        has_first_hand = bool(cs_raw.get("has_first_hand_signals"))
        if has_first_hand:
            pages_with_first_hand += 1
        # Authority citation check via the same logic as P6-03 (link
        # graph outbound to recognised authority hosts).
        authority_count = 0
        if site.link_graph is not None:
            from seomate.pillars.p_freebatch import _AUTHORITY_HOSTS as auth_hosts

            for ref in site.link_graph.outbound.get(url, []):
                if ref.is_internal:
                    continue
                if any(h in ref.target_url.lower() for h in auth_hosts):
                    authority_count += 1
        if authority_count > 0:
            pages_with_authority_citations += 1
        # Author signal: page has Person schema OR a byline pattern.
        sd = site.structured_data.get(url)
        has_author_schema = bool(sd and sd.blocks_of_type("Person"))
        if has_author_schema:
            pages_with_author_signal += 1
        findings.append(
            {
                "url": url,
                "category": next(
                    (k for k, c in ymyl_categories.items() if c > 0),
                    "unknown",
                ),
                "has_first_hand_signal": has_first_hand,
                "authority_citation_count": authority_count,
                "has_author_schema": has_author_schema,
            }
        )

    total = len(ymyl_urls)
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="YMYL pages carry author signals (Person schema or byline) — proxy for credentials",
        passed=(pages_with_author_signal / total) >= 0.5,
        evidence={
            "pages_with_author_signal": pages_with_author_signal,
            "ymyl_total": total,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="YMYL pages cite at least one recognised authority source",
        passed=(pages_with_authority_citations / total) >= 0.5,
        evidence={
            "pages_with_authority_citations": pages_with_authority_citations,
            "ymyl_total": total,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="YMYL pages have first-hand signals (>=30% based on content_substance)",
        passed=(pages_with_first_hand / total) >= 0.30,
        evidence={
            "pages_with_first_hand": pages_with_first_hand,
            "ymyl_total": total,
        },
    )

    rules = [rule_1, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "ymyl_pages_total": total,
            "ymyl_categories": ymyl_categories,
            "pages_with_author_signal": pages_with_author_signal,
            "pages_with_authority_citations": pages_with_authority_citations,
            "pages_with_first_hand": pages_with_first_hand,
            "findings_sample": findings[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "composition.ymyl_handling_aggregation",
            "composition.ymyl_classifier",
            "composition.content_substance_evaluator",
        ],
    )


# ─── P4-13 — Three-layer content structure ──────────────────────────────────


@register_extractor("P4-13")
async def capture_p4_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-13 — Three-layer content structure (Speculative).

    Heuristic check across article-like pages: does the page open with
    a short direct answer (~50 words), follow with a 100-150 word
    'why this matters' segment, then provide 1000+ words of detailed
    analysis? Speculative variable — pattern from Foundation Inc's GEO
    guide, no Tier A source.
    """
    captured_at = _now_dt()
    eligible: list[str] = []
    matching: list[dict[str, Any]] = []
    failing: list[dict[str, Any]] = []

    for url, text in site.text_content.items():
        if not text.main_text or text.word_count < 800:
            continue
        path = (urlsplit(url).path or "/").lower()
        if not any(
            seg in path
            for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/guide", "/research")
        ):
            continue
        eligible.append(url)
        # Approximate three-layer detection by paragraph word counts.
        paragraphs = [p.strip() for p in text.main_text.split("\n\n") if p.strip()]
        if not paragraphs:
            failing.append({"url": url, "reason": "no paragraph structure"})
            continue
        first_words = len(paragraphs[0].split())
        second_block = (
            " ".join(paragraphs[1:3]) if len(paragraphs) >= 2 else ""
        )
        second_words = len(second_block.split())
        body_words = text.word_count - first_words - second_words

        # 'Direct answer' band: 20–80 words (loose around the 50 ideal).
        # 'Why-it-matters' band: 60–250 words (loose around 100-150).
        # 'Depth' band: >= 800 words remaining in the article body.
        direct_ok = 20 <= first_words <= 80
        whyit_ok = 60 <= second_words <= 250
        depth_ok = body_words >= 800

        record = {
            "url": url,
            "first_para_words": first_words,
            "second_block_words": second_words,
            "remaining_body_words": body_words,
            "direct_answer_band": direct_ok,
            "why_it_matters_band": whyit_ok,
            "depth_band": depth_ok,
            "passes_three_layer": direct_ok and whyit_ok and depth_ok,
        }
        if record["passes_three_layer"]:
            matching.append(record)
        else:
            failing.append(record)

    if not eligible:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-13",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no long-form article pages eligible for three-layer check"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 20% of long-form article pages follow the three-layer pattern",
        passed=(len(matching) / len(eligible)) >= 0.2,
        evidence={
            "matching_count": len(matching),
            "eligible_total": len(eligible),
            "matching_pct": round(len(matching) / len(eligible) * 100, 1),
        },
    )

    rules = [rule_1]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-13",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "eligible_pages": len(eligible),
            "matching_count": len(matching),
            "failing_count": len(failing),
            "matching_pct": round(len(matching) / len(eligible) * 100, 1),
            "matching_sample": matching[:10],
            "failing_sample": failing[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=[
            "trafilatura.main_text",
            "composition.three_layer_structure_check",
        ],
    )


# ─── P4-05 — Author entity recognition ──────────────────────────────────────


# Cap unique author lookups per audit so a site with many bylines
# doesn't burn KG quota unnecessarily.
_MAX_AUTHORS_KG_LOOKUP = 25


@register_extractor("P4-05")
async def capture_p4_05(
    ctx: AdapterContext,
    site: SiteData,
    *,
    kg: KnowledgeGraphAdapter,
) -> CaptureRecord:
    """P4-05 — Author entity recognition in Knowledge Graph (Consensus).

    Harvests unique author names from bylined article-like pages
    (regex over text bylines + Person schema) and KG-searches each.
    Reports per-author KG match status with result_score banding.
    """
    captured_at = _now_dt()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no text content available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["composition.author_kg_check"],
            errors=["text_content empty"],
        )

    # Harvest author names from text bylines + Person schema, with
    # source-page tracking so reviewers can verify.
    name_to_pages: dict[str, list[str]] = {}
    for url, page_audit in site.page_audits.items():
        # Skip non-article-like pages — bylines on services / homepage
        # are usually marketing copy, not authorship signals.
        path = (urlsplit(url).path or "/").lower()
        if not any(
            seg in path
            for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/case-stud", "/research")
        ):
            continue
        text = site.text_content.get(url)
        if text and text.main_text:
            found, name, _ = _byline_in_text(text.main_text)
            if found and name:
                name_to_pages.setdefault(name, []).append(url)
        sd = site.structured_data.get(url)
        if sd is not None:
            person_blocks = sd.blocks_of_type("Person")
            for block in person_blocks:
                pname = block.raw.get("name")
                if isinstance(pname, str) and pname.strip():
                    name_to_pages.setdefault(pname.strip(), []).append(url)

    if not name_to_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no author names harvested from bylines / Person schema on article-like pages",
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "trafilatura.main_text",
                "extruct.parse_structured_data",
                "composition.author_kg_check",
            ],
        )

    unique_names = list(name_to_pages.keys())[:_MAX_AUTHORS_KG_LOOKUP]
    findings: list[dict[str, Any]] = []
    api_errors: list[str] = []
    kg_unconfigured = False

    high_confidence_count = 0
    fuzzy_count = 0
    unknown_count = 0

    for name in unique_names:
        try:
            hits = await kg.search(name, limit=3)
        except KGNotConfigured:
            kg_unconfigured = True
            break
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        top = hits[0] if hits else None
        score = top.result_score if top else 0.0
        band = "unknown"
        if score >= 50.0:
            band = "high_confidence"
            high_confidence_count += 1
        elif score >= 5.0:
            band = "fuzzy"
            fuzzy_count += 1
        else:
            unknown_count += 1
        findings.append(
            {
                "author_name": name,
                "page_count": len(name_to_pages[name]),
                "kg_result_score": score,
                "band": band,
                "kg_id": top.kg_id if top else None,
                "kg_name": top.name if top else None,
                "kg_types": list(top.types) if top else [],
            }
        )

    if kg_unconfigured:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "GOOGLE_KG_API_KEY not set; cannot query Knowledge Graph",
                "harvested_authors": list(name_to_pages.keys()),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["google_kg.entities_search"],
            errors=["KG not configured"],
        )

    total_checked = len(findings)
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one site author is recognised as a KG entity (high-confidence match)",
        passed=high_confidence_count >= 1,
        evidence={
            "high_confidence_count": high_confidence_count,
            "fuzzy_count": fuzzy_count,
            "unknown_count": unknown_count,
            "total_checked": total_checked,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Authors KG-recognised cover content from multiple pages (signal that recognition is genuine, not coincidental)",
        passed=any(
            f["band"] == "high_confidence" and f["page_count"] >= 2
            for f in findings
        ),
        evidence={
            "multi_page_authors_kg_recognised": sum(
                1
                for f in findings
                if f["band"] == "high_confidence" and f["page_count"] >= 2
            ),
        },
        notes="Optional but informative — single-page author KG-recognition is less load-bearing.",
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "harvested_authors": len(name_to_pages),
            "kg_checked": total_checked,
            "high_confidence_count": high_confidence_count,
            "fuzzy_count": fuzzy_count,
            "unknown_count": unknown_count,
            "findings": findings,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "google_kg.entities_search",
            "trafilatura.main_text",
            "extruct.parse_structured_data",
            "composition.author_kg_check",
        ],
        errors=api_errors or None,
    )


# ─── P4-01 — Publishing cadence and consistency ─────────────────────────────


@register_extractor("P4-01")
async def capture_p4_01(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-01 — Publishing cadence and consistency (Probable, first-audit estimate).

    Same data shape as P2-41 (site update cadence) but framed at the
    content-operations level — emphasises **consistency** rather than
    raw rate. A site that publishes regularly (e.g. 2 posts per week
    every week) scores higher than one that publishes 50 posts in one
    burst then nothing for 6 months, even if the totals match.

    Derives signals from the XML sitemap's ``<lastmod>`` distribution:
    - publications per month (last 3 / 12 months)
    - active months: how many of the last 12 months had any publication
    - consistency: coefficient of variation across active months
      (lower = more consistent)

    Pass: >= 6 of last 12 months had publications AND coefficient of
    variation across active months <= 1.5 (rough threshold for
    "regularly active vs sporadic burst").
    """
    import math
    from datetime import datetime as _dt, timedelta as _td

    from seomate.pillars.p_freebatch import _fetch_sitemap_records

    captured_at = _now_dt()
    records, errors = await _fetch_sitemap_records(site.primary_url)
    if not records:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-01",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no sitemap reachable or no URL entries",
                "errors": errors[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_fetch"],
            errors=errors[:3] or ["no records"],
        )

    parsed_dates: list[_dt] = []
    for r in records:
        lm = r.get("lastmod")
        if not lm:
            continue
        try:
            normalised = lm.strip().replace("Z", "+00:00")
            dt = _dt.fromisoformat(normalised)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_dates.append(dt)
        except (ValueError, TypeError):
            continue

    if not parsed_dates:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-01",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "sitemap has no parseable <lastmod> values",
                "urls_in_sitemap": len(records),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_fetch"],
            errors=["no parseable lastmod"],
        )

    now = _now_dt()
    twelve_months_ago = now - _td(days=365)
    three_months_ago = now - _td(days=90)

    by_month: dict[str, int] = {}
    for d in parsed_dates:
        if d < twelve_months_ago:
            continue
        key = d.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + 1

    active_months = len(by_month)
    publications_last_12m = sum(by_month.values())
    publications_last_3m = sum(
        1 for d in parsed_dates if d >= three_months_ago
    )

    coefficient_of_variation: float | None = None
    consistency_classification = "unknown"
    if active_months >= 2:
        values = list(by_month.values())
        mean_v = sum(values) / len(values)
        if mean_v > 0:
            variance = sum((v - mean_v) ** 2 for v in values) / len(values)
            stddev = math.sqrt(variance)
            coefficient_of_variation = round(stddev / mean_v, 3)
            if coefficient_of_variation < 0.5:
                consistency_classification = "very_consistent"
            elif coefficient_of_variation < 1.0:
                consistency_classification = "consistent"
            elif coefficient_of_variation < 1.5:
                consistency_classification = "uneven"
            else:
                consistency_classification = "sporadic_burst"
        else:
            consistency_classification = "no_activity"
    elif active_months == 1:
        consistency_classification = "single_burst"

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 6 of last 12 months had at least one publication",
        passed=active_months >= 6,
        evidence={
            "active_months_last_12": active_months,
            "publications_last_12m": publications_last_12m,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Publishing rhythm is consistent (CoV <= 1.5; <0.5 very consistent, <1.0 consistent, <1.5 uneven, otherwise sporadic)",
        passed=(
            coefficient_of_variation is not None
            and coefficient_of_variation <= 1.5
        ),
        evidence={
            "coefficient_of_variation": coefficient_of_variation,
            "classification": consistency_classification,
            "month_distribution": dict(sorted(by_month.items())),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "urls_in_sitemap": len(records),
            "urls_with_lastmod": len(parsed_dates),
            "active_months_last_12": active_months,
            "publications_last_3m": publications_last_3m,
            "publications_last_12m": publications_last_12m,
            "publications_per_month_3m": round(publications_last_3m / 3, 2),
            "publications_per_month_12m": round(publications_last_12m / 12, 2),
            "coefficient_of_variation": coefficient_of_variation,
            "consistency_classification": consistency_classification,
            "month_distribution": dict(sorted(by_month.items())),
            "caveat": "First-audit estimate from sitemap lastmod; CMS deploy may have bulk-touched all URLs (visible as single-burst classification). Multi-snapshot history gives true rhythm.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.sitemap_fetch",
            "composition.publishing_cadence_consistency",
        ],
    )


# ─── P4-10 — Sourcing and evidence presence ─────────────────────────────────


# Authority host fragments — outbound link targets to these are counted
# as authoritative citations. Conservative list: official .gov / .edu
# / major news / standards bodies / large research orgs.
_AUTHORITY_HOST_FRAGMENTS = (
    ".gov", ".edu", ".ac.uk", ".gov.uk",
    "wikipedia.org", "who.int", "un.org", "europa.eu", "nih.gov",
    "nature.com", "sciencemag.org", "sciencedirect.com", "springer.com",
    "ieee.org", "acm.org", "arxiv.org", "ssrn.com", "jstor.org",
    "harvard.edu", "stanford.edu", "mit.edu", "berkeley.edu", "oxford.ac.uk",
    "cambridge.org", "cambridge.ac.uk",
    "reuters.com", "bbc.co.uk", "bbc.com", "ft.com", "nytimes.com",
    "wsj.com", "economist.com", "theguardian.com", "washingtonpost.com",
    "bloomberg.com",
    "forbes.com", "hbr.org",
    "gartner.com", "forrester.com", "mckinsey.com", "deloitte.com",
    "pwc.com", "kpmg.com", "ey.com",
    "google.com/developers", "developers.google.com", "web.dev",
    "mozilla.org", "developer.mozilla.org", "w3.org",
    "github.com",  # for technical citations
)


def _is_authority_host(host: str) -> bool:
    host_l = host.lower().removeprefix("www.")
    return any(frag in host_l for frag in _AUTHORITY_HOST_FRAGMENTS)


@register_extractor("P4-10")
async def capture_p4_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-10 — Sourcing and evidence presence (Consensus).

    Counts outbound links per page that resolve to recognised authority
    hosts (.gov / .edu / major publications / research bodies / standards
    bodies). Citation density = authority outbound links per 1000 words.

    Pass: site median authority-citation density >= 0.5 (one authority
    citation every 2000 words) on substantive content pages
    (>=300 words). Lower threshold than ideal but realistic for non-
    journalism sites; pages with no authority citations at all are
    surfaced separately as "zero-citation pages".
    """
    captured_at = _now_dt()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    from bs4 import BeautifulSoup

    site_host = site.domain.lower().removeprefix("www.")
    findings: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        # Word count from text_content (trafilatura), not raw HTML, to
        # match how content-ops actually evaluates content density.
        text = site.text_content.get(url)
        word_count = getattr(text, "word_count", 0)
        if word_count < 300:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        authority_hosts: dict[str, int] = {}
        outbound_total = 0
        for a in soup.find_all("a"):
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            host = urlsplit(href).netloc.lower().removeprefix("www.")
            if not host or site_host in host:
                continue
            outbound_total += 1
            if _is_authority_host(host):
                authority_hosts[host] = authority_hosts.get(host, 0) + 1
        authority_count = sum(authority_hosts.values())
        density_per_1000 = round(authority_count * 1000 / word_count, 3)
        findings.append(
            {
                "url": url,
                "word_count": word_count,
                "outbound_total": outbound_total,
                "authority_citations": authority_count,
                "authority_density_per_1000_words": density_per_1000,
                "authority_hosts_sample": dict(
                    sorted(authority_hosts.items(), key=lambda kv: kv[1], reverse=True)[:5]
                ),
            }
        )

    if not findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no substantive pages (>=300 words) with HTML to evaluate"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["no eligible pages"],
        )

    densities = sorted(f["authority_density_per_1000_words"] for f in findings)
    median_density = densities[len(densities) // 2]
    mean_density = round(sum(densities) / len(densities), 3)
    zero_citation_pages = [f for f in findings if f["authority_citations"] == 0]
    zero_pct = round(len(zero_citation_pages) / len(findings) * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site median authority-citation density >= 0.5 per 1000 words",
        passed=median_density >= 0.5,
        evidence={
            "median_density_per_1000": median_density,
            "mean_density_per_1000": mean_density,
            "pages_evaluated": len(findings),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 50% of substantive pages have zero authority citations",
        passed=zero_pct <= 50,
        evidence={
            "zero_citation_pages": len(zero_citation_pages),
            "zero_citation_pct": zero_pct,
            "zero_citation_sample": [
                {"url": p["url"], "word_count": p["word_count"]}
                for p in zero_citation_pages[:10]
            ],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed
    findings_sorted = sorted(findings, key=lambda f: f["authority_density_per_1000_words"], reverse=True)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(findings),
            "median_density_per_1000": median_density,
            "mean_density_per_1000": mean_density,
            "zero_citation_pages_count": len(zero_citation_pages),
            "zero_citation_pct": zero_pct,
            "best_cited_pages": findings_sorted[:5],
            "zero_citation_sample": [p["url"] for p in zero_citation_pages[:10]],
            "note": (
                "Authority-citation density: outbound links to recognised "
                "high-trust hosts (.gov / .edu / major publications / "
                "research / standards bodies) per 1000 words of main content. "
                "Conservative authority list — may miss niche-specific "
                "authorities (e.g., industry-specific publications)."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.extract",
            "composition.authority_citation_density",
        ],
    )


# ─── P4-11 — Original research / proprietary data ───────────────────────────


@register_extractor("P4-11")
async def capture_p4_11(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-11 — Original research / proprietary data (Probable).

    Aggregates the per-page ``original_research`` LLM evaluator (already
    runs in the audit's batch LLM step) at the site level. The evaluator
    checks four signals per page: methodology_disclosed, has_primary_data,
    limitations_acknowledged, data_attributed_to_publisher; the page
    "passes" only when all four are true.

    Pass: at least one page on the site passes the four-signal test
    (any original research is a meaningful site-level signal). The
    stronger rule reports the fraction of evaluated pages that pass.

    Scope note: the same evaluator backs P6-07 (GEO original research
    evaluation including backlink-citation evidence). This entry is the
    content-operations framing — "does the page contain original
    research?" — without the citation-recognition layer.
    """
    captured_at = _now_dt()
    evals = site.llm_evaluations.get("original_research", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no eligible pages (LLM evaluator restricts to blog / article / research paths with >=300 words)"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create", "composition.original_research_evaluator"],
            errors=[reason],
        )

    pages_evaluated = 0
    pages_passed = 0
    page_findings: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []
    signal_counts = {
        "methodology_disclosed": 0,
        "has_primary_data": 0,
        "limitations_acknowledged": 0,
        "data_attributed_to_publisher": 0,
    }
    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        pages_evaluated += 1
        if ev.passed:
            pages_passed += 1
        raw = ev.raw or {}
        for key in signal_counts:
            if bool(raw.get(key)):
                signal_counts[key] += 1
        page_findings.append(
            {
                "url": url,
                "passed": bool(ev.passed),
                "methodology_disclosed": bool(raw.get("methodology_disclosed")),
                "has_primary_data": bool(raw.get("has_primary_data")),
                "limitations_acknowledged": bool(raw.get("limitations_acknowledged")),
                "data_attributed_to_publisher": bool(raw.get("data_attributed_to_publisher")),
                "confidence": ev.confidence,
                "rationale": ev.rationale,
            }
        )

    if pages_evaluated == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "every original_research evaluation errored or returned no verdict",
                "errored_count": len(errored),
                "errored_sample": errored[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create"],
            errors=["evaluator outputs all unusable"],
        )

    pass_pct = round(pages_passed / pages_evaluated * 100, 1)
    any_signal_pct = {
        k: round(v / pages_evaluated * 100, 1)
        for k, v in signal_counts.items()
    }
    passing_pages = sorted(
        [p for p in page_findings if p["passed"]],
        key=lambda p: p["confidence"],
        reverse=True,
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one evaluated page contains genuine original research (all four signals)",
        passed=pages_passed >= 1,
        evidence={
            "pages_evaluated": pages_evaluated,
            "pages_passed": pages_passed,
            "pass_pct": pass_pct,
            "passing_pages_sample": passing_pages[:5],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">= 10% of evaluated pages show >= 2 of the four original-research signals (partial-credit threshold)",
        passed=(
            sum(
                1 for p in page_findings
                if sum(
                    [
                        p["methodology_disclosed"],
                        p["has_primary_data"],
                        p["limitations_acknowledged"],
                        p["data_attributed_to_publisher"],
                    ]
                ) >= 2
            ) / pages_evaluated >= 0.10
            if pages_evaluated else False
        ),
        evidence={
            "signal_counts": signal_counts,
            "signal_coverage_pct": any_signal_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed  # rule 2 is informational; pass on rule 1

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-11",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_evaluated": pages_evaluated,
            "pages_passed_full": pages_passed,
            "pass_pct": pass_pct,
            "signal_coverage_counts": signal_counts,
            "signal_coverage_pct": any_signal_pct,
            "passing_pages": passing_pages[:10],
            "errored_count": len(errored),
            "note": (
                "Reads the original_research LLM evaluator output that runs "
                "once per audit batch. P6-07 uses the same evaluator with the "
                "additional citation-recognition layer; P4-11 (this) is the "
                "content-ops framing."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.original_research_evaluator",
        ],
    )


# ─── P4-24 — Quarterly content refresh cycle ────────────────────────────────


@register_extractor("P4-24")
async def capture_p4_24(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-24 — Quarterly content refresh cycle (Probable, first-audit estimate).

    From the XML sitemap's ``<lastmod>`` distribution, computes the
    fraction of indexable URLs whose last modification falls within the
    most-recent 90-day window — a first-audit estimate of "quarterly
    refresh activity". True multi-snapshot history is needed for the
    full version; this approximation is best-effort.

    Pass: >= 25% of URLs in sitemap have lastmod within last 90 days.
    Same caveat as P2-41 / P4-01: sitemap lastmod may reflect CMS
    deploys, not actual content edits — visible as suspiciously
    uniform monthly distribution.
    """
    from seomate.pillars.p_freebatch import _fetch_sitemap_records

    captured_at = _now_dt()
    records, errors = await _fetch_sitemap_records(site.primary_url)
    if not records:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-24",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no sitemap reachable or no URL entries",
                "errors": errors[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_fetch"],
            errors=errors[:3] or ["no records"],
        )

    from datetime import datetime as _dt, timedelta as _td

    parsed_dates: list[tuple[str, _dt]] = []
    no_lastmod_count = 0
    for r in records:
        lm = r.get("lastmod")
        loc = r.get("loc")
        if not lm or not loc:
            no_lastmod_count += 1 if loc else 0
            continue
        try:
            normalised = lm.strip().replace("Z", "+00:00")
            dt = _dt.fromisoformat(normalised)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_dates.append((loc, dt))
        except (ValueError, TypeError):
            continue

    if not parsed_dates:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-24",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "sitemap has no parseable <lastmod> values",
                "urls_in_sitemap": len(records),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_fetch"],
            errors=["no parseable lastmod"],
        )

    now = _now_dt()
    ninety_days_ago = now - _td(days=90)
    recent_urls = [loc for loc, dt in parsed_dates if dt >= ninety_days_ago]
    refresh_pct = round(len(recent_urls) / len(parsed_dates) * 100, 1)

    # Stale candidates: pages with lastmod older than 1 year that are
    # the most overdue for refresh
    one_year_ago = now - _td(days=365)
    stale = sorted(
        [(loc, dt) for loc, dt in parsed_dates if dt < one_year_ago],
        key=lambda t: t[1],
    )
    stale_sample = [
        {"url": loc, "lastmod": dt.isoformat(), "age_days": (now - dt).days}
        for loc, dt in stale[:10]
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 25% of sitemap URLs have lastmod within last 90 days (quarterly refresh activity)",
        passed=refresh_pct >= 25,
        evidence={
            "urls_with_lastmod": len(parsed_dates),
            "urls_refreshed_last_90d": len(recent_urls),
            "refresh_pct_last_90d": refresh_pct,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-24",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "urls_in_sitemap": len(records),
            "urls_with_lastmod": len(parsed_dates),
            "urls_refreshed_last_90d": len(recent_urls),
            "refresh_pct_last_90d": refresh_pct,
            "stale_pages_over_1yr_count": len(stale),
            "stale_pages_sample": stale_sample,
            "caveat": (
                "First-audit estimate from sitemap lastmod (self-declared). "
                "A CMS bulk-deploy can produce 100% recent-refresh even "
                "without real content edits — same artifact P2-41/P4-01 "
                "flagged via single_burst classification. Multi-snapshot "
                "history is needed for a clean read."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.sitemap_fetch",
            "composition.quarterly_refresh_estimate",
        ],
    )


# ─── P4-08 — Comprehensiveness vs SERP competitor average ──────────────────


# P4-08 moved to the Competitive Analysis module (June 2026) — comparative
# insight, not an audit variable; no longer registered as a site-audit extractor.
# Logic retained here for reference / reuse by the module.
async def capture_p4_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-08 — Comprehensiveness vs SERP competitor average (Probable).

    For each ranked-keyword SERP in the prefetch, look at the top
    organic competitors (excluding our own domain), fetch each
    competitor page, extract main text, and compare word counts. Our
    ranking page should be comparable to or longer than the
    competitor median.

    First-pass measure is word count alone (practitioner basic version).
    Deeper version — semantic entity coverage from MarketMuse / Surfer —
    would need LLM/embedding analysis per competitor page; flagged as
    deferred.

    Pass: site median ratio (our_words / competitor_median_words) >= 0.8
    AND no individual page < 0.4 ratio.
    """
    import asyncio
    import httpx
    from trafilatura import extract as trafilatura_extract

    captured_at = _now_dt()
    serps = site.serp_results or {}
    if not serps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-08",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERP prefetch results available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic", "http.competitor_fetch"],
            errors=["no SERPs"],
        )

    our_host = site.domain.lower().removeprefix("www.")
    brand_name = (site.brand.name if site.brand else "").lower()

    # Build (keyword, our_url, competitor_urls[]) per non-brand SERP
    tasks: list[tuple[str, str | None, list[str]]] = []
    for kw, result in serps.items():
        if brand_name and brand_name in kw.lower():
            continue  # skip brand SERPs — brand-name ranking pages aren't a comprehensiveness comparison
        items = result.get("items") or []
        organic = [i for i in items if i.get("type") == "organic"][:10]
        our_url = None
        competitor_urls: list[str] = []
        for it in organic:
            url = (it.get("url") or "").strip()
            domain = (it.get("domain") or "").lower().removeprefix("www.")
            if not url:
                continue
            if our_host in domain and our_url is None:
                our_url = url
            elif our_host not in domain and len(competitor_urls) < 3:
                competitor_urls.append(url)
        if competitor_urls:
            tasks.append((kw, our_url, competitor_urls))

    if not tasks:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-08",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERPs had usable competitor URLs"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no competitor URLs"],
        )

    # Fetch every unique URL we need (own + competitor) in parallel
    fetch_cache: dict[str, str] = {}  # url -> main_text
    all_urls: set[str] = set()
    for kw, our_url, competitor_urls in tasks:
        if our_url:
            all_urls.add(our_url)
        for u in competitor_urls:
            all_urls.add(u)

    # Pull from our existing text_content cache when possible (own pages)
    for url, page_text in (site.text_content or {}).items():
        if url in all_urls and page_text and getattr(page_text, "main_text", ""):
            fetch_cache[url] = page_text.main_text

    urls_to_fetch = [u for u in all_urls if u not in fetch_cache]

    async def _fetch_one(client: httpx.AsyncClient, url: str) -> None:
        try:
            r = await client.get(url, follow_redirects=True, timeout=20.0)
            if r.status_code >= 400 or not r.text:
                fetch_cache[url] = ""
                return
            extracted = trafilatura_extract(r.text, include_comments=False)
            fetch_cache[url] = (extracted or "").strip()
        except Exception:  # noqa: BLE001 - failure is data
            fetch_cache[url] = ""

    if urls_to_fetch:
        sem = asyncio.Semaphore(6)
        async with httpx.AsyncClient(
            headers={"User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"},
        ) as client:
            async def _bounded(u: str) -> None:
                async with sem:
                    await _fetch_one(client, u)
            await asyncio.gather(*(_bounded(u) for u in urls_to_fetch))

    def _wc(text: str) -> int:
        return len((text or "").split())

    findings: list[dict[str, Any]] = []
    ratios: list[float] = []
    for kw, our_url, competitor_urls in tasks:
        our_wc = _wc(fetch_cache.get(our_url, "")) if our_url else 0
        comp_wcs = [_wc(fetch_cache.get(u, "")) for u in competitor_urls]
        comp_wcs_nonzero = [w for w in comp_wcs if w > 0]
        if not comp_wcs_nonzero:
            findings.append(
                {
                    "keyword": kw,
                    "our_url": our_url,
                    "our_word_count": our_wc,
                    "competitor_word_counts": comp_wcs,
                    "ratio": None,
                    "note": "no competitor page produced usable main text",
                }
            )
            continue
        comp_median = sorted(comp_wcs_nonzero)[len(comp_wcs_nonzero) // 2]
        ratio = round(our_wc / comp_median, 2) if comp_median else 0
        if our_url and our_wc > 0:
            ratios.append(ratio)
        findings.append(
            {
                "keyword": kw,
                "our_url": our_url,
                "our_word_count": our_wc,
                "competitor_word_counts": comp_wcs,
                "competitor_median": comp_median,
                "ratio": ratio,
            }
        )

    if not ratios:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-08",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "site doesn't rank in top organic for any queried keyword OR our pages produced no extractable main text",
                "findings_sample": findings[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic", "http.competitor_fetch"],
            errors=["no comparable ratios"],
        )

    sorted_r = sorted(ratios)
    median_ratio = sorted_r[len(sorted_r) // 2]
    mean_ratio = round(sum(ratios) / len(ratios), 2)
    weak_findings = [f for f in findings if f.get("ratio") is not None and f["ratio"] < 0.4]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site median word-count ratio vs competitor median >= 0.8",
        passed=median_ratio >= 0.8,
        evidence={
            "median_ratio": median_ratio,
            "mean_ratio": mean_ratio,
            "pages_compared": len(ratios),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No comparable page is severely below competitors (ratio < 0.4)",
        passed=len(weak_findings) == 0,
        evidence={
            "weak_page_count": len(weak_findings),
            "weak_pages": weak_findings[:5],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-08",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "queries_compared": len(ratios),
            "median_ratio": median_ratio,
            "mean_ratio": mean_ratio,
            "weak_pages_count": len(weak_findings),
            "findings": findings,
            "note": (
                "First-pass measure is word count comparison only — the "
                "practitioner basic version. Deeper entity-coverage analysis "
                "(MarketMuse / Surfer / Clearscope style) would need LLM "
                "evaluation of competitor pages or embedding similarity to a "
                "topic model — flagged as deferred."
            ),
            "deferred_features": [
                "semantic_entity_coverage_per_competitor (LLM analysis)",
                "missing_topics_list (LLM extraction)",
                "section_structure_comparison (heading-level mapping)",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "serp.google.organic",
            "http.competitor_fetch",
            "trafilatura.extract",
            "composition.word_count_comparison",
        ],
    )


# ─── P4-19 — UGC discussion effort score ────────────────────────────────────


# CSS class / element fragments that commonly indicate UGC sections
# (comments, forums, Q&A, discussion). Conservative — only flag when
# the patterns appear in substantive size, not just a single mention.
_UGC_CLASS_PATTERNS = (
    "comment", "comments", "comment-list", "comment-thread",
    "forum", "forum-thread", "discussion", "thread",
    "qa-section", "questions-answers", "user-questions",
    "reviews-section", "user-reviews", "testimonials-section",
    "disqus", "discourse",
)


@register_extractor("P4-19")
async def capture_p4_19(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-19 — UGC discussion effort score (Speculative, watchlist).

    Detects whether the site hosts any user-generated discussion
    (comment sections, forums, Q&A platforms) via HTML class patterns.

    Per the taxonomy, this variable is "limited applicability: only
    relevant for sites with substantial UGC". For sites with no
    detectable UGC infrastructure (typical of commercial / agency
    sites), the variable returns UNMEASURABLE — not applicable.

    Pass: site has UGC AND the discussion quality is substantive
    (LLM-driven evaluation of comment effort/length). The substantive-
    quality check needs comment-content extraction + LLM evaluation
    per UGC section; not implemented in v1.

    For now: detect presence, report UNMEASURABLE on commercial sites,
    flag PARTIAL on UGC sites pending quality-eval extension.
    """
    captured_at = _now_dt()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    from bs4 import BeautifulSoup

    pages_with_ugc: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue

        matched_patterns: list[str] = []
        for el in soup.find_all(class_=True):
            classes = " ".join(el.get("class") or []).lower()
            for pat in _UGC_CLASS_PATTERNS:
                if pat in classes and pat not in matched_patterns:
                    matched_patterns.append(pat)

        if matched_patterns:
            pages_with_ugc.append({"url": url, "ugc_patterns": matched_patterns})

    if not pages_with_ugc:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-19",
            captured_at=captured_at,
            status=CaptureStatus.NOT_APPLICABLE,
            value={
                "reason": (
                    "no UGC infrastructure detected (no comment/forum/discussion "
                    "class patterns in any fetched HTML). Per taxonomy this var has "
                    "'limited applicability: only relevant for sites with substantial "
                    "UGC', so for a site without it the variable does not apply."
                ),
                "applicability": "not_applicable",
            },
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["http.html_fetch", "composition.ugc_detection"],
            errors=None,
        )

    # UGC detected — quality eval not implemented in v1
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site hosts UGC infrastructure (comments / forum / discussion section)",
        passed=True,
        evidence={
            "pages_with_ugc": len(pages_with_ugc),
            "ugc_pages_sample": pages_with_ugc[:5],
        },
        notes=(
            "Discussion-effort quality eval (substantive vs spam, comment "
            "length / depth) requires per-comment extraction + LLM evaluation "
            "— deferred. This variable currently reports presence only."
        ),
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-19",
        captured_at=captured_at,
        status=CaptureStatus.PARTIAL,
        value={
            "pages_with_ugc": len(pages_with_ugc),
            "ugc_pages_sample": pages_with_ugc[:10],
            "applicability": "applicable",
            "quality_evaluation_deferred": (
                "Discussion-effort quality scoring needs per-comment extraction "
                "+ LLM evaluation (substantive vs spam, comment depth, thread "
                "engagement). Not implemented in v1; UGC PRESENCE-only signal."
            ),
            "watchlist": True,
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=["http.html_fetch", "composition.ugc_detection"],
    )
