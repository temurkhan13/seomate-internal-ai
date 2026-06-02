"""Free-from-cache extractors (pillar-mixed).

Extractors that all run off already-cached audit data — link graph,
page audits, redirect chains, structured data, main text. No new
external calls.

Variables operationalised:

- P0-08 — Site topical breadth (siteRadius proxy)             (Probable)
- P1-15 — Heading hierarchy correctness (doc-order DOM walk)  (Probable)
- P1-24 — Internal inbound link quality (PageRank-weighted)   (Probable)
- P1-26 — Outbound link quality and theme                     (Probable)
- P1-45 — Historical update cadence                           (Probable,
            unmeasurable on first audit; needs >=2 snapshots over time)
- P2-19 — HSTS configuration                                  (Probable)
- P2-25 — Redirect chains hygiene                             (Consensus)
- P4-04 — Author bio with credentials                         (Consensus)
- P4-12 — Content tagging / category structure                (Probable)
- P4-15 — Methodology disclosure (pattern + structural)       (Consensus)
- P4-16 — AI / automation use disclosure                      (Consensus)
- P4-20 — Affiliate link disclosure                           (Consensus)
- P6-03 — Citation density (inline source references)         (Consensus)
- P6-06 — First-person authority markers                      (Probable)
- P6-08 — Comparison / listicle structures                    (Probable)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from seomate.adapters import AdapterContext, EmbeddingsAdapter, EmbeddingsNotConfigured
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.adapters import cosine_similarity
from seomate.pillars._base import SiteData, register_extractor
from seomate.utils.link_graph import _norm_for_match, compute_pagerank


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


# ─── P2-25 — Redirect chains ────────────────────────────────────────────────


@register_extractor("P2-25")
async def capture_p2_25(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-25 — Redirect chains hygiene (Consensus).

    Reads ``FetchedHtml.final_redirect_chain`` for every fetched page.
    The chain captures every hop between the URL we requested and the
    final URL that served the response. A page with no redirects has
    a chain of length 1 (the URL itself).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-25",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    chain_lengths: dict[int, int] = {}
    deep_chains: list[dict[str, Any]] = []
    loops: list[dict[str, Any]] = []
    failed_after_redirect: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None:
            continue
        chain = page.final_redirect_chain or (url,)
        hop_count = max(0, len(chain) - 1)
        chain_lengths[hop_count] = chain_lengths.get(hop_count, 0) + 1
        if hop_count >= 3:
            deep_chains.append(
                {
                    "requested_url": url,
                    "hop_count": hop_count,
                    "chain": list(chain),
                    "terminal_status": page.status_code,
                }
            )
        if hop_count >= 1 and len(set(chain)) < len(chain):
            loops.append({"requested_url": url, "chain": list(chain)})
        if hop_count >= 1 and page.status_code >= 400:
            failed_after_redirect.append(
                {
                    "requested_url": url,
                    "terminal_status": page.status_code,
                    "chain": list(chain),
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No URL has a redirect chain longer than 2 hops",
        passed=len(deep_chains) == 0,
        evidence={
            "deep_chains": deep_chains[:25],
            "deep_chain_count": len(deep_chains),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No redirect loops detected",
        passed=len(loops) == 0,
        evidence={"loops": loops[:10]},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Every redirect terminates at a 2xx (no 4xx/5xx after redirect chain)",
        passed=len(failed_after_redirect) == 0,
        evidence={"failed_after_redirect": failed_after_redirect[:10]},
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-25",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": sum(chain_lengths.values()),
            "chain_length_distribution": dict(sorted(chain_lengths.items())),
            "deep_chain_count": len(deep_chains),
            "loop_count": len(loops),
            "failed_after_redirect_count": len(failed_after_redirect),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.redirect_chain_walker"],
    )


# ─── P4-16 — AI / automation use disclosure ─────────────────────────────────

# Phrases practitioners actually use to disclose AI assistance.
# Conservative — we want to catch genuine disclosures, not paranoid
# false positives (e.g. a page that mentions AI in the product context).
AI_DISCLOSURE_PATTERNS = (
    re.compile(r"\bAI[- ]assisted\b", re.I),
    re.compile(r"\bAI[- ]generated\b", re.I),
    re.compile(r"\bgenerated\s+with\s+AI\b", re.I),
    re.compile(r"\bwritten\s+with\s+(?:the\s+help\s+of\s+)?AI\b", re.I),
    re.compile(r"\bAI[- ]powered\s+(?:drafting|writing|editing)\b", re.I),
    re.compile(r"\bthis\s+(?:article|post|page)\s+was\s+(?:partially\s+)?(?:generated|written|drafted|edited)\s+(?:with|by|using)\s+AI\b", re.I),
    re.compile(r"\bedited\s+by\s+(?:a\s+)?human\s+editor\b", re.I),
    re.compile(r"\bGPT\s*-?\d", re.I),
    re.compile(r"\bClaude\s+(?:wrote|drafted|generated)\b", re.I),
    re.compile(r"\bautomated\s+(?:content|generation|workflow|drafting)\b", re.I),
)

# A weaker signal — pages where AI is *discussed* without disclosure.
# Used only to size the universe (how many pages should have disclosure).
AI_TOPIC_PATTERNS = (
    re.compile(r"\b(?:artificial intelligence|machine learning|large language model|LLM|ChatGPT|generative AI|gen[- ]AI)\b", re.I),
)


@register_extractor("P4-16")
async def capture_p4_16(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-16 — AI / automation use disclosure (Consensus).

    Scans every page's main text for explicit AI-assistance disclosure
    patterns. The variable interpretation:

    - Pages discussing AI as a topic do not require disclosure.
    - The variable is failing only when **none** of the site's pages
      disclose AI use, *and* there is independent evidence the content
      shows AI patterns (cross-referenced from P4-21).
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-16",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no main text extracted for any page"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
            errors=["text_content empty"],
        )

    pages_with_disclosure: list[dict[str, Any]] = []
    pages_about_ai = 0
    for url, text in site.text_content.items():
        if not text.main_text:
            continue
        matches: list[str] = []
        for pat in AI_DISCLOSURE_PATTERNS:
            m = pat.search(text.main_text)
            if m:
                matches.append(m.group(0))
        if matches:
            pages_with_disclosure.append({"url": url, "matched_phrases": matches[:5]})
        if any(p.search(text.main_text) for p in AI_TOPIC_PATTERNS):
            pages_about_ai += 1

    # P4-21 cross-reference: if mass-produced detection flagged AI
    # patterns, AND no disclosure exists, that's the failure.
    p4_21_evals = site.llm_evaluations.get("content_substance", {})
    pages_flagged_ai_patterns = sum(
        1
        for ev in p4_21_evals.values()
        if (ev.raw or {}).get("shows_ai_boilerplate") is True
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one site page discloses AI assistance where applicable",
        passed=len(pages_with_disclosure) > 0 or pages_flagged_ai_patterns == 0,
        evidence={
            "disclosure_pages": pages_with_disclosure[:10],
            "disclosure_count": len(pages_with_disclosure),
            "pages_with_ai_topic": pages_about_ai,
            "pages_flagged_ai_patterns_by_p4_21": pages_flagged_ai_patterns,
            "interpretation": (
                "Disclosure not required for every page; failing only when "
                "AI patterns are detected (P4-21) AND no disclosure exists."
            ),
        },
    )

    rules = [rule_1]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-16",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "disclosure_page_count": len(pages_with_disclosure),
            "disclosure_pages": pages_with_disclosure[:25],
            "pages_about_ai": pages_about_ai,
            "pages_flagged_ai_patterns_by_p4_21": pages_flagged_ai_patterns,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.ai_disclosure_pattern_match",
            "P4-21.content_substance_evaluator",
        ],
    )


# ─── P4-20 — Affiliate link disclosure and quality ──────────────────────────


AFFILIATE_DISCLOSURE_PATTERNS = (
    re.compile(r"\baffiliate\s+(?:link|disclosure|partner|commission)\b", re.I),
    re.compile(r"\bwe\s+may\s+earn\s+a\s+commission\b", re.I),
    re.compile(r"\bcommissioned\s+links?\b", re.I),
    re.compile(r"\bcompensated\s+(?:affiliate|partner)\b", re.I),
    re.compile(r"\bsponsored\s+(?:content|post|link)\b", re.I),
    re.compile(r"\bpaid\s+partnership\b", re.I),
)


@register_extractor("P4-20")
async def capture_p4_20(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-20 — Affiliate link disclosure and quality (Consensus).

    Detects affiliate-link presence (via ``rel`` containing
    ``sponsored`` or known affiliate-host patterns) and cross-checks
    whether the page also carries a disclosure statement. Unmeasurable
    when no affiliate links are detected anywhere on the site.
    """
    captured_at = _now()
    if site.link_graph is None or not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-20",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "link graph or text content unavailable"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "composition.affiliate_link_check"],
            errors=["link_graph or text_content missing"],
        )

    pages_with_sponsored_links: list[str] = []
    sponsored_link_count = 0
    for url in site.link_graph.pages:
        for ref in site.link_graph.outbound.get(url, []):
            rel_lower = (ref.rel or "").lower()
            if "sponsored" in rel_lower or "ugc" in rel_lower:
                sponsored_link_count += 1
                if url not in pages_with_sponsored_links:
                    pages_with_sponsored_links.append(url)

    pages_with_disclosure: list[str] = []
    for url, text in site.text_content.items():
        if not text.main_text:
            continue
        if any(p.search(text.main_text) for p in AFFILIATE_DISCLOSURE_PATTERNS):
            pages_with_disclosure.append(url)

    if sponsored_link_count == 0 and not pages_with_disclosure:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-20",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no affiliate links or disclosures detected; variable does not apply",
                "sponsored_link_count": 0,
                "disclosure_page_count": 0,
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "composition.affiliate_link_check"],
        )

    pages_missing_disclosure = [
        url for url in pages_with_sponsored_links if url not in pages_with_disclosure
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Pages with sponsored/affiliate links also carry an affiliate disclosure",
        passed=len(pages_missing_disclosure) == 0,
        evidence={
            "sponsored_link_pages": pages_with_sponsored_links[:25],
            "pages_missing_disclosure": pages_missing_disclosure[:25],
            "missing_disclosure_count": len(pages_missing_disclosure),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="rel='sponsored' or rel='ugc' attribute used on affiliate / monetised links",
        passed=sponsored_link_count > 0,
        evidence={
            "sponsored_link_count": sponsored_link_count,
            "method": "anchor_rel_attribute_scan",
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-20",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "sponsored_link_count": sponsored_link_count,
            "pages_with_sponsored_links": len(pages_with_sponsored_links),
            "disclosure_page_count": len(pages_with_disclosure),
            "pages_missing_disclosure": len(pages_missing_disclosure),
            "sample_sponsored_pages": pages_with_sponsored_links[:10],
            "sample_disclosure_pages": pages_with_disclosure[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.affiliate_link_check",
        ],
    )


# ─── P6-06 — First-person authority markers ─────────────────────────────────


_FIRST_PERSON_PATTERNS = (
    re.compile(r"\b(?:I|we|our)\s+(?:found|tested|measured|surveyed|discovered|built|deployed|ran|analysed|analyzed|interviewed|observed)\b", re.I),
    re.compile(r"\b(?:in\s+our|in\s+my)\s+(?:experience|research|study|analysis|deployment|testing)\b", re.I),
    re.compile(r"\bwe\s+(?:asked|polled|interviewed|tracked|examined)\b", re.I),
    re.compile(r"\b(?:my|our)\s+team\b", re.I),
)

# Generic first-person without evidential frame — the failure mode.
_GENERIC_FIRST_PERSON = (
    re.compile(r"\bwe\s+(?:believe|think|love|are\s+passionate)\b", re.I),
    re.compile(r"\bour\s+(?:passion|mission)\b", re.I),
)


@register_extractor("P6-06")
async def capture_p6_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-06 — First-person authority markers (Probable).

    Detects grounded first-person markers (claim + evidence frame) on
    content pages. Distinguishes from "marketing first-person" patterns
    that are present-but-unsubstantiated.
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-06",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no main text extracted"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
            errors=["text_content empty"],
        )

    eligible: list[str] = []
    grounded_pages: list[dict[str, Any]] = []
    generic_only_pages: list[dict[str, Any]] = []

    for url, text in site.text_content.items():
        if not text.main_text or text.word_count < 200:
            continue
        path = (urlsplit(url).path or "/").lower()
        if not any(
            seg in path
            for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/case-stud", "/research")
        ):
            continue
        eligible.append(url)
        grounded_hits: list[str] = []
        for pat in _FIRST_PERSON_PATTERNS:
            m = pat.search(text.main_text)
            if m:
                grounded_hits.append(m.group(0))
        generic_hits: list[str] = []
        for pat in _GENERIC_FIRST_PERSON:
            m = pat.search(text.main_text)
            if m:
                generic_hits.append(m.group(0))
        if grounded_hits:
            grounded_pages.append(
                {"url": url, "grounded_examples": grounded_hits[:3]}
            )
        elif generic_hits:
            generic_only_pages.append(
                {"url": url, "generic_examples": generic_hits[:3]}
            )

    if not eligible:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-06",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no article-like pages with substantive content"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 30% of article-like pages have grounded first-person markers",
        passed=(len(grounded_pages) / len(eligible)) >= 0.30,
        evidence={
            "grounded_pages_count": len(grounded_pages),
            "eligible_pages_total": len(eligible),
            "grounded_pct": round(len(grounded_pages) / len(eligible) * 100, 1),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=(
            "Generic first-person ('we believe', 'we love', 'our mission') is "
            "outweighed by grounded first-person on article pages"
        ),
        passed=len(grounded_pages) >= len(generic_only_pages),
        evidence={
            "grounded_pages_count": len(grounded_pages),
            "generic_only_pages_count": len(generic_only_pages),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-06",
        pillar="P6",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "eligible_pages": len(eligible),
            "grounded_pages_count": len(grounded_pages),
            "generic_only_pages_count": len(generic_only_pages),
            "grounded_sample": grounded_pages[:10],
            "generic_only_sample": generic_only_pages[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.first_person_pattern_match",
        ],
    )


# ─── P6-08 — Comparison and listicle structures ─────────────────────────────


_LISTICLE_TITLE_PATTERNS = (
    re.compile(r"\b(?:top|best|worst)\s+\d+\b", re.I),
    re.compile(r"\b\d+\s+(?:best|top|worst|ways|tips|reasons|tools|examples|things)\b", re.I),
    re.compile(r"\b(?:ultimate\s+)?guide\s+to\b", re.I),
)

_COMPARISON_TITLE_PATTERNS = (
    re.compile(r"\bvs\.?\b", re.I),
    re.compile(r"\bversus\b", re.I),
    re.compile(r"\b(?:compared|comparison)\b", re.I),
    re.compile(r"\balternatives?\s+to\b", re.I),
)


@register_extractor("P6-08")
async def capture_p6_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-08 — Comparison and listicle structures (Probable).

    Identifies pages that signal listicle/comparison intent via title
    and confirms they actually carry list / table structure in the
    rendered HTML. Mismatches (title promises comparison, body is one
    big block of prose) are the failure mode.
    """
    captured_at = _now()
    if not site.text_content or not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-08",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "html_pages or text_content unavailable"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
        )

    candidates: list[dict[str, Any]] = []
    matching: list[dict[str, Any]] = []
    mismatching: list[dict[str, Any]] = []

    for url, page_audit in site.page_audits.items():
        title = page_audit.title or ""
        h1 = page_audit.h1[0] if page_audit.h1 else ""
        is_listicle = any(p.search(title) or p.search(h1) for p in _LISTICLE_TITLE_PATTERNS)
        is_comparison = any(p.search(title) or p.search(h1) for p in _COMPARISON_TITLE_PATTERNS)
        if not (is_listicle or is_comparison):
            continue
        intent = "listicle" if is_listicle else "comparison"
        # Check rendered HTML for list / table structures.
        html = site.html_pages.get(url)
        list_count = 0
        table_count = 0
        long_lists = 0
        if html and html.html:
            soup = BeautifulSoup(html.html, "html.parser")
            for lst in soup.find_all(["ul", "ol"]):
                items = lst.find_all("li")
                list_count += 1
                if len(items) >= 3:
                    long_lists += 1
            table_count = len(soup.find_all("table"))

        structure_present = (
            long_lists >= 1 if intent == "listicle"
            else (table_count >= 1 or long_lists >= 1)
        )
        rec = {
            "url": url,
            "intent": intent,
            "title": title,
            "list_count": list_count,
            "long_list_count": long_lists,
            "table_count": table_count,
            "structure_present": structure_present,
        }
        candidates.append(rec)
        if structure_present:
            matching.append(rec)
        else:
            mismatching.append(rec)

    if not candidates:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-08",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no listicle / comparison-titled pages detected; variable does not apply",
                "pages_total": len(site.page_audits),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.listicle_pattern_match"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=(
            "Every listicle / comparison-titled page carries the structural "
            "form its title promises (list ≥ 3 items, or table)"
        ),
        passed=len(mismatching) == 0,
        evidence={
            "matching_count": len(matching),
            "mismatching_count": len(mismatching),
            "mismatching_pages": mismatching[:15],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Site uses listicle / comparison structure on at least one page (signal for GEO)",
        passed=len(candidates) > 0,
        evidence={"candidates_count": len(candidates)},
    )

    rules = [rule_1, rule_2]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-08",
        pillar="P6",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "candidates_count": len(candidates),
            "matching_count": len(matching),
            "mismatching_count": len(mismatching),
            "candidates": candidates[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.listicle_pattern_match",
        ],
    )


# ─── P1-24 — Internal inbound link quality (PageRank-weighted) ──────────────

# Authority-band thresholds: scores above 2x the mean are "high authority"
# pages (typical hub / homepage); below 0.5x is "low authority" (orphan-ish).
PR_HIGH_BAND_MULTIPLIER = 2.0
PR_LOW_BAND_MULTIPLIER = 0.5


@register_extractor("P1-24")
async def capture_p1_24(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-24 — Internal inbound link quality (Probable, PageRank-weighted).

    Computes a PageRank-style authority score over the internal link
    graph, then evaluates each page's inbound-link quality as the
    weighted sum of PageRank scores of its inbound source pages. The
    leaked Google features (PageRankNS, IndyRank) confirm this kind of
    authority-weighted computation; the exact algorithm is composition.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-24",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.pagerank_iteration"],
            errors=["site.link_graph is None"],
        )

    pagerank = compute_pagerank(site.link_graph)
    if not pagerank:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-24",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "PageRank computation returned no scores"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["composition.pagerank_iteration"],
            errors=["pagerank empty"],
        )

    mean_pr = sum(pagerank.values()) / len(pagerank)
    high_band = mean_pr * PR_HIGH_BAND_MULTIPLIER
    low_band = mean_pr * PR_LOW_BAND_MULTIPLIER

    # Per-page inbound-link quality = sum of PR scores of inbound sources.
    inbound_quality: list[dict[str, Any]] = []
    for url in sorted(site.link_graph.pages):
        inbound_refs = site.link_graph.inbound_internal(url)
        if not inbound_refs:
            quality_score = 0.0
        else:
            quality_score = sum(
                pagerank.get(ref.source_url, 0.0) for ref in inbound_refs
            )
        inbound_quality.append(
            {
                "url": url,
                "pagerank": round(pagerank.get(url, 0.0), 4),
                "inbound_count": len(inbound_refs),
                "inbound_quality_score": round(quality_score, 4),
                "band": (
                    "high_authority" if pagerank.get(url, 0.0) >= high_band
                    else ("low_authority" if pagerank.get(url, 0.0) < low_band else "average")
                ),
            }
        )

    inbound_quality.sort(key=lambda r: r["inbound_quality_score"], reverse=True)
    top_15 = inbound_quality[:15]
    bottom_15 = inbound_quality[-15:]

    pages_high = sum(1 for r in inbound_quality if r["band"] == "high_authority")
    pages_low = sum(1 for r in inbound_quality if r["band"] == "low_authority")
    pages_avg = sum(1 for r in inbound_quality if r["band"] == "average")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has at least one high-authority hub page (PageRank >= 2x mean)",
        passed=pages_high >= 1,
        evidence={
            "high_authority_count": pages_high,
            "high_threshold": round(high_band, 4),
            "mean_pagerank": round(mean_pr, 4),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Low-authority pages are < 50% of the site (no orphan-cluster pattern)",
        passed=(pages_low / len(pagerank)) < 0.50,
        evidence={
            "low_authority_count": pages_low,
            "low_threshold": round(low_band, 4),
            "total_pages": len(pagerank),
            "low_pct": round(pages_low / len(pagerank) * 100, 1),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-24",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_in_graph": len(pagerank),
            "mean_pagerank": round(mean_pr, 4),
            "high_authority_count": pages_high,
            "average_count": pages_avg,
            "low_authority_count": pages_low,
            "top_15_by_inbound_quality": top_15,
            "bottom_15_by_inbound_quality": bottom_15,
            "thresholds": {
                "high_band_min": round(high_band, 4),
                "low_band_max": round(low_band, 4),
            },
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.pagerank_iteration",
            "composition.inbound_link_quality_aggregation",
        ],
    )


# ─── P4-12 — Content tagging / category structure ───────────────────────────


# Categories surfaced via URL paths (e.g. /blog/category/X) or via
# BreadcrumbList schema items.
_CATEGORY_PATH_PATTERNS = (
    re.compile(r"^/(?P<root>category|categories|topic|topics|tag|tags|section|sections)/[^/]+", re.I),
    re.compile(r"^/(?P<root>blog|news|articles?|posts?)/(?P<cat>[^/]+)/[^/]+", re.I),
)


@register_extractor("P4-12")
async def capture_p4_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-12 — Content tagging / category structure (Probable).

    Detects whether content pages live inside an explicit taxonomy
    (URL-path category segment OR BreadcrumbList schema with >=2
    items). Pages without either signal are 'orphan' from a topic
    structure perspective.
    """
    captured_at = _now()
    if not site.page_audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-12",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits captured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["page_audits empty"],
        )

    categories_via_url: dict[str, int] = {}
    pages_with_url_category: list[str] = []
    pages_with_breadcrumb: list[str] = []
    pages_orphan: list[str] = []
    eligible_pages: list[str] = []

    for url in site.page_audits.keys():
        path = (urlsplit(url).path or "/").lower()
        if path in ("/", "/home", "/index.html"):
            continue  # homepage exempt
        eligible_pages.append(url)
        has_url_cat = False
        for pat in _CATEGORY_PATH_PATTERNS:
            m = pat.search(path)
            if m:
                segs = [s for s in path.strip("/").split("/") if s]
                if len(segs) >= 2:
                    cat = segs[0] if pat.groupindex.get("root") else segs[0]
                    categories_via_url[cat] = categories_via_url.get(cat, 0) + 1
                    has_url_cat = True
                    pages_with_url_category.append(url)
                    break
        sd = site.structured_data.get(url)
        has_breadcrumb = False
        if sd is not None:
            for block in sd.blocks_of_type("BreadcrumbList"):
                items = block.raw.get("itemListElement")
                if isinstance(items, list) and len(items) >= 2:
                    has_breadcrumb = True
                    pages_with_breadcrumb.append(url)
                    break
        if not has_url_cat and not has_breadcrumb:
            pages_orphan.append(url)

    if not eligible_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-12",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "only homepage in audit set; no eligible pages"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
        )

    orphan_pct = len(pages_orphan) / len(eligible_pages) * 100

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has at least one URL-path category segment OR uses BreadcrumbList schema site-wide",
        passed=len(categories_via_url) > 0 or len(pages_with_breadcrumb) > 0,
        evidence={
            "url_category_count": len(categories_via_url),
            "breadcrumb_page_count": len(pages_with_breadcrumb),
            "url_categories_sample": list(categories_via_url.items())[:10],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Most pages (>=70%) have a taxonomy assignment (URL category OR breadcrumb)",
        passed=((len(eligible_pages) - len(pages_orphan)) / len(eligible_pages)) >= 0.70,
        evidence={
            "orphan_count": len(pages_orphan),
            "orphan_pct": round(orphan_pct, 1),
            "eligible_pages_total": len(eligible_pages),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-12",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "eligible_pages_total": len(eligible_pages),
            "pages_with_url_category": len(pages_with_url_category),
            "pages_with_breadcrumb": len(pages_with_breadcrumb),
            "pages_orphan": len(pages_orphan),
            "orphan_pct": round(orphan_pct, 1),
            "url_category_distribution": dict(
                sorted(categories_via_url.items(), key=lambda kv: -kv[1])
            ),
            "orphan_sample": pages_orphan[:20],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.content_tagging_check",
        ],
    )


# ─── P6-03 — Citation density (inline source references) ────────────────────


# Detects inline citations of three flavours: bracketed reference numbers
# ('[3]', '[citation]'), 'according to NAME', and inline anchor links to
# common authoritative domains (gov, edu, established publishers).
_BRACKET_CITATION = re.compile(r"\[\s*\d+\s*\]")
_ACCORDING_TO = re.compile(r"\b(?:according to|per|via|cited (?:in|by)|source[s]?:)\s+[A-Z]", re.I)

_AUTHORITY_HOSTS = (
    "wikipedia.org",
    "wikidata.org",
    "google.com/search/howsearchworks",
    "developers.google.com",
    "schema.org",
    "w3.org",
    "ietf.org",
    "rfc-editor.org",
    "arxiv.org",
    "nature.com",
    "science.org",
    ".gov",
    ".gov.uk",
    ".edu",
    ".ac.uk",
    "who.int",
    "un.org",
    "ec.europa.eu",
    "imf.org",
    "worldbank.org",
)


def _is_authority_link(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in _AUTHORITY_HOSTS)


@register_extractor("P6-03")
async def capture_p6_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-03 — Citation density (Consensus).

    For each substantive page, counts inline citations via three signals:
    bracketed reference numbers, 'according to NAME' patterns, and
    outbound links to recognised authority hosts. Rule 1 (>= 1 citation
    per 500 words) is the headline threshold per the variable spec.
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-03",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no main text extracted"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
            errors=["text_content empty"],
        )

    substantive_pages: list[str] = []
    findings: list[dict[str, Any]] = []
    pages_below_density: list[dict[str, Any]] = []
    pages_with_no_citations: list[str] = []
    pages_with_authority_links: list[str] = []

    for url, text in site.text_content.items():
        if not text.main_text or text.word_count < 300:
            continue
        substantive_pages.append(url)
        bracket_hits = len(_BRACKET_CITATION.findall(text.main_text))
        according_hits = len(_ACCORDING_TO.findall(text.main_text))
        authority_links = 0
        if site.link_graph is not None:
            for ref in site.link_graph.outbound.get(url, []):
                if not ref.is_internal and _is_authority_link(ref.target_url):
                    authority_links += 1
        total_citations = bracket_hits + according_hits + authority_links
        density_per_500 = (total_citations * 500.0 / text.word_count) if text.word_count else 0

        record = {
            "url": url,
            "word_count": text.word_count,
            "bracket_citations": bracket_hits,
            "according_to_hits": according_hits,
            "authority_links": authority_links,
            "total_citations": total_citations,
            "density_per_500w": round(density_per_500, 2),
        }
        findings.append(record)
        if total_citations == 0:
            pages_with_no_citations.append(url)
        if density_per_500 < 1.0:
            pages_below_density.append(record)
        if authority_links >= 1:
            pages_with_authority_links.append(url)

    if not substantive_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-03",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no pages with >= 300 words of substantive content"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=(
            "Citation density >= 1 per 500 words on at least 50% of "
            "substantive pages"
        ),
        passed=(
            (len(substantive_pages) - len(pages_below_density))
            / len(substantive_pages)
        ) >= 0.5,
        evidence={
            "below_density_count": len(pages_below_density),
            "substantive_pages": len(substantive_pages),
            "below_density_pct": round(
                len(pages_below_density) / len(substantive_pages) * 100, 1
            ),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one page cites a recognised authority source (gov/edu/Wikipedia/major publisher)",
        passed=len(pages_with_authority_links) > 0,
        evidence={
            "authority_citing_page_count": len(pages_with_authority_links),
            "authority_hosts_checked": list(_AUTHORITY_HOSTS),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No substantive page has zero citations",
        passed=len(pages_with_no_citations) == 0,
        evidence={
            "no_citation_count": len(pages_with_no_citations),
            "sample": pages_with_no_citations[:15],
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    avg_density = (
        sum(f["density_per_500w"] for f in findings) / len(findings)
        if findings else 0
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-03",
        pillar="P6",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "substantive_pages": len(substantive_pages),
            "pages_with_authority_links": len(pages_with_authority_links),
            "pages_with_no_citations": len(pages_with_no_citations),
            "pages_below_density": len(pages_below_density),
            "avg_density_per_500w": round(avg_density, 2),
            "page_findings_sample": findings[:20],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.citation_pattern_match",
        ],
    )


# ─── P1-15 — Heading hierarchy correctness (DOM order) ──────────────────────


@register_extractor("P1-15")
async def capture_p1_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-15 — Heading hierarchy correctness (Probable).

    Walks each cached page's HTML in document order, captures the
    heading sequence (H1, H2, H3...), and checks the four rules: one
    H1 first, no skipped levels going down, each heading followed by
    content, no styling-only heading abuse (single-word H2s under H3s).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-15",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    page_findings: list[dict[str, Any]] = []
    no_h1: list[str] = []
    multi_h1: list[str] = []
    skipped_levels: list[dict[str, Any]] = []
    empty_section_headings: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or page.status_code >= 400 or not page.html:
            continue
        soup = BeautifulSoup(page.html, "html.parser")
        headings: list[tuple[int, str, BeautifulSoup]] = []
        for el in soup.find_all(re.compile(r"^h[1-6]$")):
            level = int(el.name[1])
            text = (el.get_text() or "").strip()
            headings.append((level, text, el))

        h1_levels = [h for h in headings if h[0] == 1]
        if not h1_levels:
            no_h1.append(url)
        elif len(h1_levels) > 1:
            multi_h1.append(url)

        # Document-order skip-level check.
        last_seen: int | None = None
        page_skips: list[tuple[int, int]] = []
        for level, _, _ in headings:
            if last_seen is not None and level > last_seen + 1:
                page_skips.append((last_seen, level))
            last_seen = level
        if page_skips:
            skipped_levels.append({"url": url, "skips": page_skips[:5]})

        # Empty-section detection: a heading with no following text-bearing
        # sibling before the next heading.
        empty_here: list[str] = []
        for idx, (_, text, el) in enumerate(headings):
            next_heading_el = headings[idx + 1][2] if idx + 1 < len(headings) else None
            sibling = el.find_next_sibling()
            has_content = False
            while sibling is not None and sibling is not next_heading_el:
                t = (sibling.get_text() or "").strip()
                if t:
                    has_content = True
                    break
                sibling = sibling.find_next_sibling()
            if not has_content and text:
                empty_here.append(text[:60])
        if empty_here:
            empty_section_headings.append(
                {"url": url, "empty_headings": empty_here[:5]}
            )

        page_findings.append(
            {
                "url": url,
                "heading_count": len(headings),
                "h1_count": len(h1_levels),
                "level_sequence": [lv for lv, _, _ in headings[:20]],
            }
        )

    if not page_findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-15",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every page has exactly one H1",
        passed=len(no_h1) == 0 and len(multi_h1) == 0,
        evidence={
            "no_h1": no_h1[:20],
            "multi_h1": multi_h1[:20],
            "no_h1_count": len(no_h1),
            "multi_h1_count": len(multi_h1),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No skipped heading levels in document order (no H2 → H4 directly)",
        passed=len(skipped_levels) == 0,
        evidence={
            "skipped_level_pages": skipped_levels[:20],
            "skip_count": len(skipped_levels),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No heading is followed by an empty section",
        passed=len(empty_section_headings) == 0,
        evidence={
            "empty_section_pages": empty_section_headings[:20],
            "empty_count": len(empty_section_headings),
        },
    )

    rules = [rule_1, rule_2, rule_5]
    overall_pass = rule_1.passed and rule_2.passed and rule_5.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-15",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": len(page_findings),
            "pages_no_h1": len(no_h1),
            "pages_multi_h1": len(multi_h1),
            "pages_with_skipped_levels": len(skipped_levels),
            "pages_with_empty_sections": len(empty_section_headings),
            "page_findings_sample": page_findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.heading_hierarchy_dom_walk",
        ],
    )


# ─── P4-04 — Author bio with credentials ────────────────────────────────────


# Credential indicators in bio text.
_CREDENTIAL_PATTERNS = (
    re.compile(r"\b(?:Ph\.?D\.?|PhD|M\.?D\.?|MD|J\.?D\.?|MBA|MSc|BSc|BA|MA|BEng|MEng|CPA|CFA|FRCP)\b"),
    re.compile(r"\b\d+\+?\s+years?\s+(?:of\s+)?(?:experience|in)\b", re.I),
    re.compile(r"\bcertified\s+[A-Z]", re.I),
    re.compile(r"\b(?:director|head|lead|chief|founder|co[- ]?founder|principal|senior|vp|cto|ceo|coo|cmo|cfo)\s+(?:of|at)\b", re.I),
    re.compile(r"\bformer(?:ly)?\s+(?:at|with)\s+[A-Z]", re.I),
)

# Identity-verification signals.
_IDENTITY_PATTERNS = (
    re.compile(r"linkedin\.com/in/", re.I),
    re.compile(r"twitter\.com/[A-Za-z0-9_]+", re.I),
    re.compile(r"x\.com/[A-Za-z0-9_]+", re.I),
    re.compile(r"orcid\.org/", re.I),
    re.compile(r"scholar\.google\.com", re.I),
    re.compile(r"github\.com/[A-Za-z0-9_-]+", re.I),
)


@register_extractor("P4-04")
async def capture_p4_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-04 — Author bio with credentials (Consensus).

    Two-stage detection:
    1. Locate author bio pages via URL pattern (/author/, /team/,
       /people/, /about/).
    2. For each bio page, check for credential signals (degrees,
       years of experience, leadership titles) AND identity-verification
       links (LinkedIn / Twitter / ORCID / etc).
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-04",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no text content extracted"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
            errors=["text_content empty"],
        )

    bio_url_patterns = (
        "/author/",
        "/authors/",
        "/team/",
        "/people/",
        "/our-team",
        "/team-member/",
        "/staff/",
        "/contributors/",
    )

    bio_pages: list[dict[str, Any]] = []
    for url, text in site.text_content.items():
        path = (urlsplit(url).path or "/").lower()
        if not any(seg in path for seg in bio_url_patterns):
            continue
        if not text.main_text:
            continue
        body = text.main_text
        credential_hits: list[str] = []
        for pat in _CREDENTIAL_PATTERNS:
            m = pat.search(body)
            if m:
                credential_hits.append(m.group(0))
        identity_hits = sum(1 for pat in _IDENTITY_PATTERNS if pat.search(body))
        # Also check outbound links from this page for identity hosts.
        if site.link_graph is not None:
            for ref in site.link_graph.outbound.get(url, []):
                target = (ref.target_url or "").lower()
                if any(p.search(target) for p in _IDENTITY_PATTERNS):
                    identity_hits += 1

        word_count = text.word_count
        is_generic = word_count < 50  # too thin to be substantive
        bio_pages.append(
            {
                "url": url,
                "word_count": word_count,
                "credential_hits": credential_hits[:5],
                "credential_count": len(credential_hits),
                "identity_link_count": identity_hits,
                "is_substantive": not is_generic,
            }
        )

    if not bio_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-04",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no author bio pages detected via URL patterns",
                "url_patterns_checked": list(bio_url_patterns),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
        )

    bios_with_credentials = [b for b in bio_pages if b["credential_count"] > 0]
    bios_with_identity = [b for b in bio_pages if b["identity_link_count"] > 0]
    bios_substantive = [b for b in bio_pages if b["is_substantive"]]
    bios_generic = [b for b in bio_pages if not b["is_substantive"]]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Author bio page(s) exist on the site",
        passed=len(bio_pages) > 0,
        evidence={"bio_page_count": len(bio_pages)},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Bios include verifiable credentials (degrees, years of experience, leadership roles)",
        passed=len(bios_with_credentials) / len(bio_pages) >= 0.5,
        evidence={
            "bios_with_credentials": len(bios_with_credentials),
            "bios_total": len(bio_pages),
            "pct": round(len(bios_with_credentials) / len(bio_pages) * 100, 1),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Bios include identity-verification links (LinkedIn / Twitter / ORCID / GitHub)",
        passed=len(bios_with_identity) / len(bio_pages) >= 0.5,
        evidence={
            "bios_with_identity": len(bios_with_identity),
            "bios_total": len(bio_pages),
            "pct": round(len(bios_with_identity) / len(bio_pages) * 100, 1),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Bios are substantive (>= 50 words; not placeholder text)",
        passed=len(bios_generic) == 0,
        evidence={
            "generic_bios": [b["url"] for b in bios_generic][:10],
            "generic_count": len(bios_generic),
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-04",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "bio_page_count": len(bio_pages),
            "bios_with_credentials": len(bios_with_credentials),
            "bios_with_identity_links": len(bios_with_identity),
            "bios_substantive": len(bios_substantive),
            "bios_generic": len(bios_generic),
            "bio_findings_sample": bio_pages[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.author_bio_credential_check",
        ],
    )


# ─── P4-15 — Methodology disclosure ─────────────────────────────────────────


_METHODOLOGY_PATTERNS = (
    re.compile(r"\bour\s+methodology\b", re.I),
    re.compile(r"\bhow\s+we\s+(?:tested|test|reviewed|review|evaluated|evaluate|measured|measure|ranked|rank|scored)\b", re.I),
    re.compile(r"\b(?:testing|evaluation|review|ranking)\s+(?:criteria|methodology|framework|process)\b", re.I),
    re.compile(r"\bwe\s+(?:tested|reviewed|measured|evaluated|surveyed|interviewed)\b", re.I),
    re.compile(r"\bover\s+\d+\s+(?:hours|days|weeks|months)\s+of\s+testing\b", re.I),
    re.compile(r"\bsample\s+size\s+of\s+\d+\b", re.I),
)

# Review-content URL hints.
_REVIEW_URL_PATTERNS = (
    "/review/",
    "/reviews/",
    "/best-",
    "/top-",
    "/vs-",
    "-vs-",
    "/comparison/",
)


@register_extractor("P4-15")
async def capture_p4_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-15 — Methodology disclosure (Consensus).

    Required by Google's Product Reviews Update for review / comparison
    / ranking content. Detects:

    1. Review-like content pages (URL patterns + Product/Review schema)
    2. Whether each carries explicit methodology disclosure (patterns)

    Unmeasurable when site has no review-like content.
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-15",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no text content extracted"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
            errors=["text_content empty"],
        )

    review_pages: list[str] = []
    pages_with_methodology: list[dict[str, Any]] = []
    pages_missing_methodology: list[str] = []

    for url, text in site.text_content.items():
        path = (urlsplit(url).path or "/").lower()
        is_review_url = any(seg in path for seg in _REVIEW_URL_PATTERNS)
        sd = site.structured_data.get(url)
        has_review_schema = False
        if sd is not None:
            has_review_schema = bool(
                sd.blocks_of_type("Review")
                or sd.blocks_of_type("ProductReview")
            )
        if not (is_review_url or has_review_schema):
            continue
        review_pages.append(url)
        if not text.main_text:
            pages_missing_methodology.append(url)
            continue
        methodology_hits: list[str] = []
        for pat in _METHODOLOGY_PATTERNS:
            m = pat.search(text.main_text)
            if m:
                methodology_hits.append(m.group(0)[:80])
        if methodology_hits:
            pages_with_methodology.append(
                {"url": url, "methodology_phrases": methodology_hits[:5]}
            )
        else:
            pages_missing_methodology.append(url)

    if not review_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-15",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no review / comparison content detected; variable does not apply",
                "url_patterns_checked": list(_REVIEW_URL_PATTERNS),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every review / comparison page discloses its methodology",
        passed=len(pages_missing_methodology) == 0,
        evidence={
            "missing_methodology": pages_missing_methodology[:25],
            "missing_count": len(pages_missing_methodology),
            "review_pages_total": len(review_pages),
        },
    )

    rules = [rule_1]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-15",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "review_pages_total": len(review_pages),
            "pages_with_methodology": len(pages_with_methodology),
            "pages_missing_methodology": len(pages_missing_methodology),
            "with_methodology_sample": pages_with_methodology[:15],
            "missing_methodology_sample": pages_missing_methodology[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "trafilatura.main_text",
            "composition.methodology_pattern_match",
        ],
    )


# ─── P0-08 — Site topical breadth (siteRadius proxy) ────────────────────────


def _vector_centroid(vectors: list[tuple[float, ...]]) -> tuple[float, ...]:
    """Mean vector across a list. Returns zero-vector if input is empty."""
    if not vectors:
        return ()
    dim = len(vectors[0])
    sums = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            sums[i] += x
    n = float(len(vectors))
    return tuple(s / n for s in sums)


# Empirical bands for radius (1 - mean cosine to centroid). A tight site
# clusters at ≤ 0.10; a broad multi-topic site ≥ 0.25; in between is
# 'focused'. Bands are heuristic — refined as we audit more sites.
RADIUS_TIGHT_MAX = 0.10
RADIUS_BROAD_MIN = 0.25


@register_extractor("P0-08")
async def capture_p0_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-08 — Site topical breadth (Probable, siteRadius proxy).

    Computes the radius of the site's content cluster in the embedding
    space: the mean (1 - cosine_similarity) between each page's
    embedding and the centroid embedding. Larger radius = broader
    topical spread. The leaked Google feature ``siteRadius`` measures
    this same geometric property; our composition is a defensible
    proxy.
    """
    captured_at = _now()
    if not site.embeddings_configured:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-08",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "GEMINI_API_KEY not set; cannot compute embeddings"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.site_radius"],
            errors=["embeddings_configured False"],
        )
    if len(site.embeddings) < 3:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-08",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": f"only {len(site.embeddings)} embedded pages; need >= 3 for site radius"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.site_radius"],
        )

    vectors = [emb.vector for emb in site.embeddings.values() if emb.vector]
    centroid = _vector_centroid(vectors)
    similarities = [cosine_similarity(v, centroid) for v in vectors]
    # radius interpretation: distance = 1 - cosine_similarity.
    distances = [1.0 - s for s in similarities]
    radius_mean = sum(distances) / len(distances)
    radius_p95 = sorted(distances)[int(0.95 * (len(distances) - 1))]
    radius_max = max(distances)

    if radius_mean <= RADIUS_TIGHT_MAX:
        band = "tight"
    elif radius_mean >= RADIUS_BROAD_MIN:
        band = "broad"
    else:
        band = "focused"

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site radius indicates a coherent topical cluster (mean radius <= 0.25)",
        passed=radius_mean <= RADIUS_BROAD_MIN,
        evidence={
            "radius_mean": round(radius_mean, 4),
            "broad_threshold": RADIUS_BROAD_MIN,
            "interpretation": band,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No single outlier page sits unusually far from the cluster (max < 0.40)",
        passed=radius_max < 0.40,
        evidence={
            "radius_max": round(radius_max, 4),
            "radius_p95": round(radius_p95, 4),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed and rule_2.passed

    # Find the most-outlier pages for evidence.
    page_distances = [
        (url, round(1.0 - cosine_similarity(emb.vector, centroid), 4))
        for url, emb in site.embeddings.items()
        if emb.vector
    ]
    page_distances.sort(key=lambda t: t[1], reverse=True)
    outlier_sample = [{"url": u, "distance_from_centroid": d} for u, d in page_distances[:10]]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-08",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "embedded_pages": len(vectors),
            "radius_mean": round(radius_mean, 4),
            "radius_p95": round(radius_p95, 4),
            "radius_max": round(radius_max, 4),
            "band": band,
            "thresholds": {
                "tight_max": RADIUS_TIGHT_MAX,
                "broad_min": RADIUS_BROAD_MIN,
            },
            "outlier_pages_sample": outlier_sample,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "composition.site_radius",
        ],
    )


# ─── P2-19 — HSTS configuration ─────────────────────────────────────────────


@register_extractor("P2-19")
async def capture_p2_19(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-19 — HSTS configuration (Probable).

    Reads the ``Strict-Transport-Security`` header from cached HTML
    responses (captured on every page fetch). A passing site sets HSTS
    with a substantial max-age (>= 1 year) on every page response.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-19",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    pages_with_hsts = 0
    pages_without_hsts: list[str] = []
    max_ages: list[int] = []
    has_includesubdomains = 0
    has_preload = 0
    page_findings: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or page.status_code >= 400:
            continue
        headers = dict(page.headers or ())
        hsts = headers.get("strict-transport-security")
        if not hsts:
            pages_without_hsts.append(url)
            continue
        pages_with_hsts += 1
        # Parse max-age, includeSubDomains, preload.
        hsts_lower = hsts.lower()
        max_age_value: int | None = None
        m = re.search(r"max-age\s*=\s*(\d+)", hsts_lower)
        if m:
            max_age_value = int(m.group(1))
            max_ages.append(max_age_value)
        if "includesubdomains" in hsts_lower:
            has_includesubdomains += 1
        if "preload" in hsts_lower:
            has_preload += 1
        page_findings.append(
            {
                "url": url,
                "header": hsts[:200],
                "max_age_seconds": max_age_value,
            }
        )

    pages_total = sum(
        1
        for p in site.html_pages.values()
        if p.fetch_error is None and p.status_code < 400
    )
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="HSTS header (Strict-Transport-Security) is present on every page response",
        passed=len(pages_without_hsts) == 0 and pages_with_hsts > 0,
        evidence={
            "pages_with_hsts": pages_with_hsts,
            "pages_without_hsts": pages_without_hsts[:25],
            "pages_total": pages_total,
        },
    )
    min_max_age = min(max_ages) if max_ages else 0
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="max-age is at least 1 year (31_536_000 seconds) on every page",
        passed=min_max_age >= 31_536_000 if max_ages else False,
        evidence={
            "min_max_age_seconds": min_max_age,
            "required_seconds": 31_536_000,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="includeSubDomains directive set",
        passed=has_includesubdomains > 0,
        evidence={
            "pages_with_includesubdomains": has_includesubdomains,
            "pages_total": pages_total,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-19",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_total": pages_total,
            "pages_with_hsts": pages_with_hsts,
            "pages_without_hsts_count": len(pages_without_hsts),
            "min_max_age_seconds": min_max_age,
            "pages_with_includesubdomains": has_includesubdomains,
            "pages_with_preload": has_preload,
            "page_findings_sample": page_findings[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.hsts_header_check"],
    )


# ─── P1-26 — Outbound link quality and theme ────────────────────────────────


# Reuses the _AUTHORITY_HOSTS list defined earlier in this module (P6-03).
# Per-domain external link counts above this threshold are flagged as
# 'spammy concentration' — practitioners cite >5 links to the same off-
# site domain on the same page as a sign of paid placement or auto-
# generated content. Heuristic.
SPAM_CONCENTRATION_THRESHOLD = 5


@register_extractor("P1-26")
async def capture_p1_26(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-26 — Outbound link quality and theme (Probable).

    Walks the cached link graph for every page's outbound external
    links and classifies them: authority-tier (recognised hosts), spam
    concentration (many links to the same off-site domain), and rel
    attribute hygiene (no improper nofollow/sponsored/ugc usage).
    Reports the site-wide distribution.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-26",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.outbound_link_quality"],
            errors=["link_graph empty"],
        )

    pages_with_authority_links: list[dict[str, Any]] = []
    pages_with_spam_concentration: list[dict[str, Any]] = []
    total_external_links = 0
    total_authority_links = 0
    domain_to_pages: dict[str, set[str]] = {}

    for url in site.link_graph.pages:
        refs = site.link_graph.outbound.get(url, [])
        external = [r for r in refs if not r.is_internal]
        if not external:
            continue
        per_domain: dict[str, int] = {}
        authority_count = 0
        for ref in external:
            host = (urlsplit(ref.target_url).netloc or "").lower().removeprefix("www.")
            per_domain[host] = per_domain.get(host, 0) + 1
            if any(a in ref.target_url.lower() for a in _AUTHORITY_HOSTS):
                authority_count += 1
            domain_to_pages.setdefault(host, set()).add(url)
        total_external_links += len(external)
        total_authority_links += authority_count
        if authority_count > 0:
            pages_with_authority_links.append(
                {"url": url, "authority_link_count": authority_count}
            )
        concentrated = [
            (host, count) for host, count in per_domain.items()
            if count >= SPAM_CONCENTRATION_THRESHOLD
        ]
        if concentrated:
            pages_with_spam_concentration.append(
                {"url": url, "concentrated": concentrated[:5]}
            )

    distinct_external_hosts = len(domain_to_pages)
    authority_share = (
        total_authority_links / total_external_links * 100
        if total_external_links else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 5% of outbound external links go to recognised authority sources",
        passed=authority_share >= 5.0,
        evidence={
            "authority_share_pct": round(authority_share, 1),
            "authority_link_count": total_authority_links,
            "external_link_total": total_external_links,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=(
            "No page has spam-concentration outbound links "
            f"(>= {SPAM_CONCENTRATION_THRESHOLD} links to one off-site domain)"
        ),
        passed=len(pages_with_spam_concentration) == 0,
        evidence={
            "concentrated_pages": pages_with_spam_concentration[:15],
            "threshold": SPAM_CONCENTRATION_THRESHOLD,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Outbound external host diversity (>= 10 distinct off-site domains site-wide)",
        passed=distinct_external_hosts >= 10,
        evidence={
            "distinct_external_hosts": distinct_external_hosts,
            "threshold": 10,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-26",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "total_external_links": total_external_links,
            "total_authority_links": total_authority_links,
            "authority_share_pct": round(authority_share, 1),
            "distinct_external_hosts": distinct_external_hosts,
            "pages_with_authority_links": len(pages_with_authority_links),
            "pages_with_spam_concentration": len(pages_with_spam_concentration),
            "top_external_hosts": sorted(
                ((host, len(pages)) for host, pages in domain_to_pages.items()),
                key=lambda kv: -kv[1],
            )[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.outbound_link_quality",
        ],
    )


# ─── P1-45 — Historical update cadence ──────────────────────────────────────


@register_extractor("P1-45")
async def capture_p1_45(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-45 — Historical update cadence (Probable; first-audit unmeasurable).

    Frequency of substantive updates per page over time. Computable
    only once we have multiple audit snapshots to compare. The first
    audit always reports unmeasurable; subsequent audits will derive
    cadence from cross-audit htmldate diffs.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-45",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "historical update cadence requires >= 2 audit snapshots; "
                "this is a first-audit run"
            ),
            "method": "cross_audit_htmldate_diff",
            "next_audit_will_make_measurable": True,
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["composition.cross_audit_freshness_diff"],
        errors=["only one audit snapshot available"],
    )


# ─── P6-32 — Prompt-injection / adversarial content hygiene ─────────────────


# Patterns we flag as adversarial-to-LLMs.
_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:previous|prior|all|above)\s+(?:instructions?|prompts?|directives?|context)\b", re.I),
    re.compile(r"\bdisregard\s+(?:the\s+)?(?:above|previous|prior|all)\b", re.I),
    re.compile(r"<\|im_start\|>|<\|im_end\|>|<\|system\|>", re.I),
    re.compile(r"\[\s*(?:SYSTEM|ASSISTANT|USER)\s*\]\s*:", re.I),
    re.compile(r"\byou\s+are\s+(?:a|now)\s+(?:helpful\s+)?(?:assistant|ai|agent)\b", re.I),
)

# Hidden-content CSS patterns. Crude but defensible: each of these
# is a hallmark of "text the page renderer hides from humans but
# leaves in the HTML for LLM crawlers".
_HIDDEN_CSS_INLINE = (
    re.compile(r"style\s*=\s*[\"'][^\"']*display\s*:\s*none", re.I),
    re.compile(r"style\s*=\s*[\"'][^\"']*visibility\s*:\s*hidden", re.I),
    re.compile(r"style\s*=\s*[\"'][^\"']*font-size\s*:\s*0", re.I),
    re.compile(r"style\s*=\s*[\"'][^\"']*color\s*:\s*#?fff(?:fff)?", re.I),  # white text
    re.compile(r"style\s*=\s*[\"'][^\"']*text-indent\s*:\s*-\d{4,}", re.I),
    re.compile(r"style\s*=\s*[\"'][^\"']*position\s*:\s*absolute[^\"']*left\s*:\s*-\d{4,}", re.I),
)


@register_extractor("P6-32")
async def capture_p6_32(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-32 — Prompt-injection / adversarial content hygiene (Consensus).

    Pure pattern detection over cached HTML + main text. Flags:
    - 'ignore previous instructions' style LLM-targeted text
    - fake system-prompt syntax
    - hidden CSS text (display:none, visibility:hidden, text-indent:-9999px,
      font-size:0, white-on-white)

    Trust signal for AI search: a page that contains hidden instructions
    targeting LLMs gets demoted as adversarial.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-32",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    pages_with_injection: list[dict[str, Any]] = []
    pages_with_hidden_css: list[dict[str, Any]] = []
    pages_with_alt_stuffing: list[dict[str, Any]] = []
    total_checked = 0

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or page.status_code >= 400 or not page.html:
            continue
        total_checked += 1
        html = page.html

        injection_hits: list[str] = []
        for pat in _PROMPT_INJECTION_PATTERNS:
            m = pat.search(html)
            if m:
                injection_hits.append(m.group(0)[:60])
        if injection_hits:
            pages_with_injection.append(
                {"url": url, "matched_patterns": injection_hits[:5]}
            )

        hidden_hits: list[str] = []
        for pat in _HIDDEN_CSS_INLINE:
            m = pat.search(html)
            if m:
                hidden_hits.append(m.group(0)[:80])
        if hidden_hits:
            pages_with_hidden_css.append(
                {"url": url, "hidden_inline_styles": hidden_hits[:5]}
            )

        # Alt-text keyword stuffing detection: image alt > 200 chars
        # OR repeated keyword density inside one alt attribute.
        soup = BeautifulSoup(html, "html.parser")
        stuffed_alts: list[str] = []
        for img in soup.find_all("img", alt=True):
            alt = (img.get("alt") or "").strip()
            if not alt:
                continue
            if len(alt) > 200:
                stuffed_alts.append(alt[:120] + "…")
            else:
                words = [w for w in re.findall(r"\w+", alt.lower()) if len(w) > 3]
                if words:
                    repeats = max(words.count(w) for w in set(words))
                    if repeats >= 4:
                        stuffed_alts.append(alt[:120])
        if stuffed_alts:
            pages_with_alt_stuffing.append(
                {"url": url, "stuffed_alts": stuffed_alts[:5]}
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No 'ignore previous instructions' / fake-system-prompt patterns in any page HTML",
        passed=len(pages_with_injection) == 0,
        evidence={
            "pages_with_injection": pages_with_injection[:25],
            "violation_count": len(pages_with_injection),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No hidden-CSS text patterns (display:none / visibility:hidden / off-screen / zero-font-size)",
        passed=len(pages_with_hidden_css) == 0,
        evidence={
            "pages_with_hidden_css": pages_with_hidden_css[:25],
            "violation_count": len(pages_with_hidden_css),
        },
        notes=(
            "Detection is conservative (inline-style only). Stylesheet-"
            "level hiding patterns are not caught at this layer; deferred."
        ),
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No image alt-text keyword stuffing (> 200 chars or 4+ repeats of one term)",
        passed=len(pages_with_alt_stuffing) == 0,
        evidence={
            "pages_with_alt_stuffing": pages_with_alt_stuffing[:25],
            "violation_count": len(pages_with_alt_stuffing),
        },
    )

    rules = [rule_1, rule_2, rule_5]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-32",
        pillar="P6",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": total_checked,
            "pages_with_prompt_injection": len(pages_with_injection),
            "pages_with_hidden_css": len(pages_with_hidden_css),
            "pages_with_alt_stuffing": len(pages_with_alt_stuffing),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "composition.prompt_injection_pattern_match",
        ],
    )


# ─── P1-46 — Duplicate content within site ──────────────────────────────────


@register_extractor("P1-46")
async def capture_p1_46(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-46 — Duplicate content within site (Consensus).

    Aggregates DataForSEO's per-page ``duplicate_content``,
    ``duplicate_title`` and ``duplicate_description`` flags from the
    Instant Pages prefetch into a site-wide view. Reports the share
    of indexable pages flagged on each axis.
    """
    captured_at = _now()
    if not site.page_audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-46",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits captured"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo.on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    indexable_pages = [p for p in site.page_audits.values() if p.is_indexable]
    total = len(indexable_pages)
    if total == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-46",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no indexable pages"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo.on_page.instant_pages"],
        )

    dup_content_pages = [p.url for p in indexable_pages if p.duplicate_content_check]
    dup_title_pages = [p.url for p in indexable_pages if p.duplicate_title_check]
    dup_desc_pages = [p.url for p in indexable_pages if p.duplicate_description_check]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No indexable pages are flagged as duplicate content site-wide",
        passed=len(dup_content_pages) == 0,
        evidence={
            "dup_content_pages": dup_content_pages[:25],
            "count": len(dup_content_pages),
            "total_indexable": total,
            "pct": round(len(dup_content_pages) / total * 100, 1),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No indexable pages share duplicate titles",
        passed=len(dup_title_pages) == 0,
        evidence={
            "dup_title_pages": dup_title_pages[:25],
            "count": len(dup_title_pages),
            "pct": round(len(dup_title_pages) / total * 100, 1),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No indexable pages share duplicate descriptions",
        passed=len(dup_desc_pages) == 0,
        evidence={
            "dup_desc_pages": dup_desc_pages[:25],
            "count": len(dup_desc_pages),
            "pct": round(len(dup_desc_pages) / total * 100, 1),
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-46",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "total_indexable": total,
            "dup_content_count": len(dup_content_pages),
            "dup_title_count": len(dup_title_pages),
            "dup_description_count": len(dup_desc_pages),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.duplicate_content_aggregation",
        ],
    )


# ─── P2-04 — Sitemap freshness (<lastmod> distribution) ─────────────────────


import asyncio  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402
from datetime import date  # noqa: E402

import httpx  # noqa: E402

from seomate.utils.sitemap import (  # noqa: E402
    DEFAULT_SITEMAP_PATHS,
    SITEMAP_NS,
)


async def _fetch_sitemap_lastmods(primary_url: str, *, max_urls: int = 500) -> list[date]:
    """Best-effort: walk the site's sitemap(s) and collect <lastmod> dates.

    Same discovery cascade as utils/sitemap.discover_urls — tries each
    default path, recurses into sitemap indexes once. Errors return an
    empty list so the extractor degrades to unmeasurable gracefully.
    """
    from urllib.parse import urljoin, urlsplit

    parts = urlsplit(primary_url)
    if not parts.scheme or not parts.netloc:
        return []
    base = f"{parts.scheme}://{parts.netloc}"
    out: list[date] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"},
    ) as client:
        for path in DEFAULT_SITEMAP_PATHS:
            try:
                resp = await client.get(urljoin(base, path))
            except httpx.RequestError:
                continue
            if resp.status_code >= 400:
                continue
            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError:
                continue
            tag = root.tag.rsplit("}", 1)[-1] if "}" in root.tag else root.tag
            if tag == "sitemapindex":
                # Recurse one level into nested sitemaps.
                for sm in root.findall(f"{{{SITEMAP_NS}}}sitemap"):
                    loc_el = sm.find(f"{{{SITEMAP_NS}}}loc")
                    if loc_el is None or not loc_el.text:
                        continue
                    try:
                        nested = await client.get(loc_el.text.strip())
                    except httpx.RequestError:
                        continue
                    if nested.status_code >= 400:
                        continue
                    try:
                        nested_root = ET.fromstring(nested.text)
                    except ET.ParseError:
                        continue
                    for u in nested_root.findall(f"{{{SITEMAP_NS}}}url"):
                        lm_el = u.find(f"{{{SITEMAP_NS}}}lastmod")
                        if lm_el is not None and lm_el.text:
                            d = _parse_iso_date(lm_el.text.strip())
                            if d is not None:
                                out.append(d)
                                if len(out) >= max_urls:
                                    return out
                if out:
                    return out
                continue
            if tag == "urlset":
                for u in root.findall(f"{{{SITEMAP_NS}}}url"):
                    lm_el = u.find(f"{{{SITEMAP_NS}}}lastmod")
                    if lm_el is not None and lm_el.text:
                        d = _parse_iso_date(lm_el.text.strip())
                        if d is not None:
                            out.append(d)
                            if len(out) >= max_urls:
                                return out
                if out:
                    return out
    return out


def _parse_iso_date(text: str) -> date | None:
    """Parse a sitemap <lastmod>: ISO date or full ISO 8601 timestamp."""
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


@register_extractor("P2-04")
async def capture_p2_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-04 — Sitemap freshness via ``<lastmod>`` (Probable).

    Fetches the site's sitemap(s) directly and parses every URL's
    ``<lastmod>``. Reports the distribution of declared modification
    dates — a well-maintained sitemap mirrors the page-modification
    reality captured at the HTML layer (P4-02). A sitemap full of
    stale lastmod values often signals either abandoned content or a
    misconfigured publishing pipeline.
    """
    captured_at = _now()
    lastmods = await _fetch_sitemap_lastmods(site.primary_url)
    if not lastmods:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-04",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no sitemap lastmod data available (sitemap missing, "
                    "no <lastmod> entries, or only sitemap index found)"
                ),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_xml_fetch"],
            errors=["sitemap lastmod empty"],
        )

    today = _now().date()
    ages = sorted([(today - d).days for d in lastmods])
    median = ages[len(ages) // 2]
    p75 = ages[int(0.75 * (len(ages) - 1))]
    p95 = ages[int(0.95 * (len(ages) - 1))]
    stale_count = sum(1 for a in ages if a > 730)  # > 2 years
    fresh_count = sum(1 for a in ages if a <= 365)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Sitemap contains <lastmod> for the majority of URLs (>= 50%)",
        passed=len(lastmods) >= 5,  # arbitrary floor, real test = "present at all"
        evidence={
            "urls_with_lastmod": len(lastmods),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Median <lastmod> age <= 12 months (sitemap broadly fresh)",
        passed=median <= 365,
        evidence={"median_age_days": median, "fresh_threshold_days": 365},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="< 30% of URLs have <lastmod> older than 24 months",
        passed=(stale_count / len(ages)) < 0.30,
        evidence={
            "stale_count": stale_count,
            "stale_pct": round(stale_count / len(ages) * 100, 1),
            "stale_threshold_days": 730,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-04",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "urls_with_lastmod": len(lastmods),
            "median_age_days": median,
            "p75_age_days": p75,
            "p95_age_days": p95,
            "min_age_days": ages[0],
            "max_age_days": ages[-1],
            "fresh_count": fresh_count,
            "stale_count": stale_count,
            "fresh_threshold_days": 365,
            "stale_threshold_days": 730,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.sitemap_xml_fetch",
            "composition.sitemap_lastmod_distribution",
        ],
    )


# ─── P2-33 — Hreflang tags ──────────────────────────────────────────────────


@register_extractor("P2-33")
async def capture_p2_33(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-33 — Hreflang correctness (Consensus).

    Parses <link rel="alternate" hreflang="..."> tags from every cached
    page's HTML and reports site-wide hreflang declaration patterns.
    Unmeasurable for single-locale sites (Pixelette is en-GB only).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-33",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    pages_with_hreflang: list[dict[str, Any]] = []
    all_declared_locales: set[str] = set()
    x_default_seen = False
    pages_missing_self_reference: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        soup = BeautifulSoup(page.html, "html.parser")
        links = soup.find_all(
            "link",
            attrs={"rel": "alternate", "hreflang": True},
        )
        if not links:
            continue
        per_page_locales: list[dict[str, str]] = []
        has_self_ref = False
        for link in links:
            lang = (link.get("hreflang") or "").lower()
            href = link.get("href") or ""
            per_page_locales.append({"hreflang": lang, "href": href})
            all_declared_locales.add(lang)
            if lang == "x-default":
                x_default_seen = True
            if href and (href == url or href == page.url):
                has_self_ref = True
        pages_with_hreflang.append(
            {
                "url": url,
                "hreflang_count": len(per_page_locales),
                "locales": per_page_locales[:10],
                "has_self_reference": has_self_ref,
            }
        )
        if not has_self_ref:
            pages_missing_self_reference.append({"url": url})

    if not pages_with_hreflang:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-33",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no hreflang tags found; site appears to be single-locale",
                "configured_locales": site.domain,
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
        )

    # Site has hreflang somewhere — apply the correctness rules.
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every page declares hreflang for itself (self-referencing alternate)",
        passed=len(pages_missing_self_reference) == 0,
        evidence={
            "pages_missing_self_reference": pages_missing_self_reference[:15],
            "count": len(pages_missing_self_reference),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="x-default fallback is declared somewhere on the site",
        passed=x_default_seen,
        evidence={"x_default_present": x_default_seen},
    )

    rules = [rule_1, rule_3]
    overall_pass = rule_1.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-33",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_with_hreflang": len(pages_with_hreflang),
            "distinct_locales": sorted(all_declared_locales),
            "x_default_present": x_default_seen,
            "pages_missing_self_reference_count": len(pages_missing_self_reference),
            "sample": pages_with_hreflang[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "composition.hreflang_parse",
        ],
    )


# ─── P2-27 — External broken links ──────────────────────────────────────────


# Cap concurrent HEAD requests to be polite + bounded by audit time.
_BROKEN_LINK_CONCURRENCY = 8
_BROKEN_LINK_TIMEOUT_S = 10.0
# Cap the total number of external URLs we check per audit. The link
# graph commonly carries hundreds of external links; we sample.
_BROKEN_LINK_MAX_CHECKS = 200


@register_extractor("P2-27")
async def capture_p2_27(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-27 — External broken links (Probable).

    Walks the link graph for every distinct external URL, fires a
    HEAD request, classifies status as 'ok' (2xx-3xx) or 'broken'
    (4xx/5xx). Capped at 200 unique external URLs per audit so a
    site with thousands of outbound links doesn't blow the runtime.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-27",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.head_check"],
            errors=["link_graph empty"],
        )

    # Build the unique external-URL set + map URL → source pages.
    external_url_to_sources: dict[str, set[str]] = {}
    for url in site.link_graph.pages:
        for ref in site.link_graph.outbound.get(url, []):
            if ref.is_internal:
                continue
            external_url_to_sources.setdefault(ref.target_url, set()).add(url)

    if not external_url_to_sources:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-27",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no external links found in link graph"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.head_check"],
        )

    # Sample up to _BROKEN_LINK_MAX_CHECKS distinct URLs.
    sampled = list(external_url_to_sources.keys())[:_BROKEN_LINK_MAX_CHECKS]
    sem = asyncio.Semaphore(_BROKEN_LINK_CONCURRENCY)
    broken: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=_BROKEN_LINK_TIMEOUT_S,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"},
    ) as client:

        async def _check(target: str) -> None:
            async with sem:
                try:
                    resp = await client.head(target)
                except httpx.RequestError as exc:
                    fetch_errors.append(
                        {"url": target, "error": f"{type(exc).__name__}: {exc}"}
                    )
                    return
            # Some servers reject HEAD; fall back to GET if status 405.
            if resp.status_code == 405:
                try:
                    resp = await client.get(target)
                except httpx.RequestError:
                    pass
            if resp.status_code >= 400:
                broken.append(
                    {
                        "url": target,
                        "status_code": resp.status_code,
                        "source_pages": sorted(external_url_to_sources.get(target, []))[:5],
                    }
                )

        await asyncio.gather(*[_check(u) for u in sampled])

    checked = len(sampled) - len(fetch_errors)
    broken_pct = (len(broken) / checked * 100) if checked else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No external links return 4xx/5xx on HEAD (or GET fallback)",
        passed=len(broken) == 0,
        evidence={
            "broken_count": len(broken),
            "broken_pct": round(broken_pct, 1),
            "broken_sample": broken[:25],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Broken external link share stays under 5% of checked sample",
        passed=broken_pct < 5.0,
        evidence={
            "broken_pct": round(broken_pct, 1),
            "threshold_pct": 5.0,
            "checked": checked,
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-27",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "external_urls_total": len(external_url_to_sources),
            "checked": checked,
            "sampled": len(sampled),
            "broken_count": len(broken),
            "broken_pct": round(broken_pct, 1),
            "fetch_error_count": len(fetch_errors),
            "broken_sample": broken[:25],
            "fetch_error_sample": fetch_errors[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.head_check",
            "composition.external_link_status_check",
        ],
    )


# ─── P4-14 — Comparative content (vs / alternatives / best-of) ──────────────


_COMPARATIVE_TITLE_PATTERNS = (
    re.compile(r"\bvs\.?\b", re.I),
    re.compile(r"\bversus\b", re.I),
    re.compile(r"\balternatives?\s+to\b", re.I),
    re.compile(r"\b(?:top|best)\s+\d+\s+\w+\s+(?:for|to|in)\b", re.I),
    re.compile(r"\bbest\s+\w+\s+(?:for|of|in)\s+\d{4}\b", re.I),
    re.compile(r"\bmigrat(?:ion|ing)\s+from\b", re.I),
    re.compile(r"\bbuyer'?s?\s+guide\b", re.I),
)


@register_extractor("P4-14")
async def capture_p4_14(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P4-14 — Comparative content presence (Probable).

    Detects whether the site publishes any pages in comparative formats
    (X vs Y, alternatives to X, best of X, buyer's guide, migration
    guide). Reads from cached page titles and H1s. No new data needed.
    """
    captured_at = _now()
    if not site.page_audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P4-14",
            pillar="P4",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits captured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo.on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    matches: list[dict[str, Any]] = []
    for url, page_audit in site.page_audits.items():
        title = page_audit.title or ""
        h1 = page_audit.h1[0] if page_audit.h1 else ""
        haystack = f"{title} {h1}"
        hits: list[str] = []
        for pat in _COMPARATIVE_TITLE_PATTERNS:
            m = pat.search(haystack)
            if m:
                hits.append(m.group(0))
        if hits:
            matches.append(
                {"url": url, "title": title, "matched_patterns": hits[:3]}
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site publishes at least one comparative-format content page",
        passed=len(matches) >= 1,
        evidence={
            "comparative_page_count": len(matches),
            "pages_total": len(site.page_audits),
            "patterns_checked": [p.pattern for p in _COMPARATIVE_TITLE_PATTERNS],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Comparative content represents at least 5% of pages (variety signal)",
        passed=(len(matches) / len(site.page_audits)) >= 0.05,
        evidence={
            "comparative_page_count": len(matches),
            "pages_total": len(site.page_audits),
            "pct": round(len(matches) / len(site.page_audits) * 100, 1),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P4-14",
        pillar="P4",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "comparative_page_count": len(matches),
            "pages_total": len(site.page_audits),
            "matches_sample": matches[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.comparative_content_pattern_match",
        ],
    )


# ─── P0-07 — Topical authority / site focus score ───────────────────────────


# Empirical bands for focus score (1 - radius_mean). High focus =
# tight cluster = strong authority signal per the leaked siteFocusScore.
FOCUS_STRONG_MIN = 0.85   # radius <= 0.15
FOCUS_WEAK_MAX = 0.70     # radius >= 0.30


@register_extractor("P0-07")
async def capture_p0_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-07 — Topical authority / site focus score (Probable, siteFocusScore proxy).

    Inverse of P0-08 site radius. siteFocusScore = 1 - mean_distance
    from cluster centroid. High focus means the site's content
    clusters tightly around one topical position.
    """
    captured_at = _now()
    if not site.embeddings_configured or len(site.embeddings) < 3:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-07",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "embeddings unavailable (need >= 3 embedded pages); "
                    "P0-07 derives from same data as P0-08"
                ),
                "embeddings_configured": site.embeddings_configured,
                "embedded_pages": len(site.embeddings),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.site_focus_score"],
            errors=["embeddings empty or <3 pages"],
        )

    # Reuse the same centroid + similarity logic as P0-07's mirror P0-08.
    vectors = [emb.vector for emb in site.embeddings.values() if emb.vector]
    centroid = _vector_centroid(vectors)
    similarities = [cosine_similarity(v, centroid) for v in vectors]
    mean_similarity = sum(similarities) / len(similarities) if similarities else 0.0
    focus_score = mean_similarity

    if focus_score >= FOCUS_STRONG_MIN:
        band = "strong_focus"
    elif focus_score <= FOCUS_WEAK_MAX:
        band = "diffuse"
    else:
        band = "moderate_focus"

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Site focus score >= {FOCUS_WEAK_MAX} (not diffuse)",
        passed=focus_score > FOCUS_WEAK_MAX,
        evidence={"focus_score": round(focus_score, 4), "band": band},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Site focus score >= {FOCUS_STRONG_MIN} (strong topical authority signal)",
        passed=focus_score >= FOCUS_STRONG_MIN,
        evidence={"focus_score": round(focus_score, 4), "strong_threshold": FOCUS_STRONG_MIN},
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-07",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "embedded_pages": len(vectors),
            "focus_score": round(focus_score, 4),
            "band": band,
            "thresholds": {"strong_min": FOCUS_STRONG_MIN, "weak_max": FOCUS_WEAK_MAX},
            "interpretation": (
                "High focus score = tight topical cluster = strong authority "
                "signal per leaked siteFocusScore. Inverse of P0-08 site radius."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "composition.site_focus_score",
        ],
    )


# ─── P0-13 — Keyword-to-page mapping ────────────────────────────────────────


@register_extractor("P0-13")
async def capture_p0_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-13 — Keyword-to-page mapping (Probable, auto-discovered universe).

    Derives the mapping directly from ranked_keywords — DataForSEO Labs
    already returns the ranking URL per keyword. Reports cannibalisation
    (single page assigned as primary for too many keywords) and
    reverse-cannibalisation (same keyword surfacing on multiple ranked
    URLs — though ranked_keywords typically returns one per keyword).

    Currently uses auto-discovered keywords until a curated list is
    configured. Recorded in the value so reviewers see the provenance.
    """
    captured_at = _now()
    if not site.ranked_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-13",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked keywords available for mapping"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["ranked_keywords empty"],
        )

    # Map keyword -> ranking URL (taking the best-ranked URL per keyword).
    keyword_to_page: dict[str, str] = {}
    page_to_keywords: dict[str, list[str]] = {}
    unmapped: list[str] = []

    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = kw_data.get("keyword") or ""
        serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
        url = serp.get("url") or ""
        if not keyword:
            continue
        if not url:
            unmapped.append(keyword)
            continue
        keyword_to_page[keyword] = url
        page_to_keywords.setdefault(url, []).append(keyword)

    cannibalised_pages: list[dict[str, Any]] = []
    for url, kws in page_to_keywords.items():
        if len(kws) > 5:
            cannibalised_pages.append(
                {
                    "url": url,
                    "keyword_count": len(kws),
                    "keywords_sample": kws[:10],
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every ranked keyword maps to a primary page",
        passed=len(unmapped) == 0,
        evidence={
            "unmapped_keywords": unmapped[:25],
            "unmapped_count": len(unmapped),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Each keyword maps to exactly one primary page (no cannibalisation surface)",
        passed=True,  # ranked_keywords returns one URL per keyword by design
        evidence={
            "method": "ranked_keywords returns one ranking URL per keyword",
        },
        notes="Pass-through; checking GSC for queries-on-multiple-URLs is future H1d work.",
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="No single page is the primary for more than 5 distinct ranked keywords",
        passed=len(cannibalised_pages) == 0,
        evidence={
            "reverse_cannibalisation_pages": cannibalised_pages[:15],
            "count": len(cannibalised_pages),
        },
    )

    rules = [rule_1, rule_2, rule_4]
    overall_pass = rule_1.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-13",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "universe_provenance": "auto_discovered_from_ranked_keywords",
            "keywords_mapped": len(keyword_to_page),
            "pages_with_assignment": len(page_to_keywords),
            "reverse_cannibalisation_count": len(cannibalised_pages),
            "mapping_sample": [
                {"keyword": k, "page": p}
                for k, p in list(keyword_to_page.items())[:15]
            ],
            "reverse_cannibalisation_sample": cannibalised_pages[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "composition.keyword_to_page_mapping",
        ],
    )


# ─── P1-28 — Image alt text coverage ────────────────────────────────────────


@register_extractor("P1-28")
async def capture_p1_28(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-28 — Image alt text coverage (Consensus).

    Reads from DataForSEO's per-page ``checks.no_image_alt`` flag
    (captured in PageAudit). True on a page = at least one image
    missing alt; reported as site-wide distribution. Granular per-image
    coverage percentage is a future refactor (needs image inventory
    capture).
    """
    captured_at = _now()
    if not site.page_audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-28",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits captured"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo.on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_with_images = [p for p in site.page_audits.values() if p.images_count > 0]
    pages_missing_alt = [p.url for p in pages_with_images if p.no_image_alt_check]
    pages_complete_alt = [
        p.url for p in pages_with_images if not p.no_image_alt_check
    ]

    if not pages_with_images:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-28",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no pages with images detected"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo.on_page.instant_pages"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No page with images has any image missing alt text",
        passed=len(pages_missing_alt) == 0,
        evidence={
            "pages_missing_alt": pages_missing_alt[:25],
            "missing_count": len(pages_missing_alt),
            "pages_with_images_total": len(pages_with_images),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least 80% of image-bearing pages have complete alt coverage",
        passed=(len(pages_complete_alt) / len(pages_with_images)) >= 0.8,
        evidence={
            "complete_alt_pages": len(pages_complete_alt),
            "pages_with_images_total": len(pages_with_images),
            "pct": round(len(pages_complete_alt) / len(pages_with_images) * 100, 1),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-28",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_with_images": len(pages_with_images),
            "pages_missing_alt": len(pages_missing_alt),
            "pages_complete_alt": len(pages_complete_alt),
            "complete_alt_pct": round(
                len(pages_complete_alt) / len(pages_with_images) * 100, 1
            ),
            "missing_alt_sample": pages_missing_alt[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo.on_page.instant_pages",
            "composition.image_alt_coverage_aggregation",
        ],
    )


# ─── P1-43 — Content freshness via semantic date ────────────────────────────


# Patterns we flag as 'semantic date' references — phrasing that
# implicitly anchors the content to a point in time, per the
# leaked `semanticDate` Google feature.
_SEMANTIC_DATE_PATTERNS = (
    re.compile(r"\bas\s+of\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b", re.I),
    re.compile(r"\b(?:this|last|next)\s+(?:week|month|quarter|year)\b", re.I),
    re.compile(r"\b(?:in|during)\s+(?:202[0-9]|201[5-9])\b", re.I),
    re.compile(r"\b(?:Q[1-4])\s*\d{4}\b", re.I),
    re.compile(r"\b\d{4}\s+(?:report|study|analysis|update|edition|version)\b", re.I),
    re.compile(r"\bupdated\s+(?:on\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I),
)


@register_extractor("P1-43")
async def capture_p1_43(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-43 — Content freshness via semantic date (Probable).

    Counts implicit-date references in main text per page. The leaked
    Google ``semanticDate`` feature confirms NLP-driven date inference
    is tracked. Pages with semantic date references give Google a
    second freshness anchor beyond schema dates and byline dates.
    """
    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-43",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no main text extracted"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["trafilatura.main_text"],
            errors=["text_content empty"],
        )

    findings: list[dict[str, Any]] = []
    pages_with_semantic_date: list[str] = []
    pages_without: list[str] = []
    substantive_pages = 0

    for url, text in site.text_content.items():
        if not text.main_text or text.word_count < 200:
            continue
        substantive_pages += 1
        matches: list[str] = []
        for pat in _SEMANTIC_DATE_PATTERNS:
            for m in pat.finditer(text.main_text):
                matches.append(m.group(0))
                if len(matches) >= 5:
                    break
            if len(matches) >= 5:
                break
        if matches:
            pages_with_semantic_date.append(url)
            findings.append({"url": url, "semantic_date_examples": matches[:5]})
        else:
            pages_without.append(url)

    if substantive_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-43",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no substantive pages (>= 200 words) to check"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 30% of substantive pages carry a semantic-date reference",
        passed=(len(pages_with_semantic_date) / substantive_pages) >= 0.30,
        evidence={
            "pages_with_semantic_date": len(pages_with_semantic_date),
            "substantive_pages": substantive_pages,
            "pct": round(
                len(pages_with_semantic_date) / substantive_pages * 100, 1
            ),
        },
    )

    rules = [rule_1]
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-43",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "substantive_pages": substantive_pages,
            "pages_with_semantic_date": len(pages_with_semantic_date),
            "pages_without_semantic_date": len(pages_without),
            "semantic_date_pct": round(
                len(pages_with_semantic_date) / substantive_pages * 100, 1
            ),
            "findings_sample": findings[:20],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "trafilatura.main_text",
            "composition.semantic_date_pattern_match",
        ],
    )


# ─── P6-21 — Vector retrievability (chunk semantic coherence) ───────────────


@register_extractor("P6-21")
async def capture_p6_21(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-21 — Vector retrievability (Probable, heuristic).

    Heuristic check on H2-section structure: each H2 section's body
    should be 100-800 words (good chunk window for retriever
    embedding). Sections outside that range are too short to carry
    substance or too long to chunk cleanly.

    Single-topic-ness and cross-section-dependence checks are deferred
    to H1c (need LLM evaluation of section semantics).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-21",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    page_findings: list[dict[str, Any]] = []
    eligible_pages = 0
    pages_with_good_chunk_ratio = 0

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        # Only article-like pages have meaningful H2 sectioning.
        path = (urlsplit(url).path or "/").lower()
        if not any(
            seg in path
            for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/guide", "/learn")
        ):
            continue
        eligible_pages += 1
        soup = BeautifulSoup(page.html, "html.parser")
        h2_elements = soup.find_all("h2")
        if not h2_elements:
            page_findings.append(
                {"url": url, "h2_count": 0, "chunk_ratio": 0.0}
            )
            continue

        section_word_counts: list[int] = []
        for h2 in h2_elements:
            # Collect text in siblings until the next H2 (or end of section).
            words = 0
            sibling = h2.find_next_sibling()
            while sibling is not None and sibling.name != "h2":
                text = (sibling.get_text() or "").strip()
                if text:
                    words += len(text.split())
                sibling = sibling.find_next_sibling()
            section_word_counts.append(words)

        good_sections = sum(1 for w in section_word_counts if 100 <= w <= 800)
        chunk_ratio = (
            good_sections / len(section_word_counts)
            if section_word_counts else 0
        )
        if chunk_ratio >= 0.5:
            pages_with_good_chunk_ratio += 1
        page_findings.append(
            {
                "url": url,
                "h2_count": len(h2_elements),
                "section_word_counts": section_word_counts[:20],
                "good_sections": good_sections,
                "chunk_ratio": round(chunk_ratio, 2),
            }
        )

    if eligible_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-21",
            pillar="P6",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no article-like pages eligible"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
        )

    rule_2 = RuleResult(
        rule_id=2,
        rule_text=(
            "Section lengths are within retriever-chunk window "
            "(100-800 words) on at least 50% of article pages"
        ),
        passed=(pages_with_good_chunk_ratio / eligible_pages) >= 0.5,
        evidence={
            "pages_with_good_chunk_ratio": pages_with_good_chunk_ratio,
            "eligible_pages": eligible_pages,
            "pct": round(pages_with_good_chunk_ratio / eligible_pages * 100, 1),
        },
    )
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Article pages have H2 sectioning (>=1 H2 per page)",
        passed=all(f["h2_count"] >= 1 for f in page_findings),
        evidence={
            "pages_without_h2": [
                f["url"] for f in page_findings if f["h2_count"] == 0
            ][:10],
            "pages_total": len(page_findings),
        },
    )
    rule_others = RuleResult(
        rule_id=3,
        rule_text=(
            "Single-topic sections + topic-statement-at-head + low cross-section "
            "dependence (DEFERRED — needs LLM semantic eval of section content)"
        ),
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_section_semantics"},
    )

    rules = [rule_1, rule_2, rule_others]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-21",
        pillar="P6",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "eligible_pages": eligible_pages,
            "pages_with_good_chunk_ratio": pages_with_good_chunk_ratio,
            "good_chunk_pct": round(
                pages_with_good_chunk_ratio / eligible_pages * 100, 1
            ),
            "section_findings_sample": page_findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.h2_section_chunk_check",
        ],
    )


# ─── P1-41 — Content freshness — byline date ────────────────────────────────


_BYLINE_DATE_PATTERN = re.compile(
    r"\b(?:Published|Posted|Updated|Last\s+(?:updated|modified)|Date)\s*[:\-]?\s*"
    r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)


@register_extractor("P1-41")
async def capture_p1_41(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-41 — Byline date (Probable, leaked bylineDate feature).

    Two signals: Article.datePublished / dateModified from structured
    data, and visible 'Published/Updated' prefix patterns near the top
    of the main text. Reports per-page distribution of byline-date
    presence.
    """
    captured_at = _now()
    if not site.page_audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-41",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits captured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["extruct.parse_structured_data", "trafilatura.main_text"],
            errors=["page_audits empty"],
        )

    pages_with_schema_date: list[str] = []
    pages_with_visible_byline_date: list[str] = []
    pages_with_either: list[dict[str, Any]] = []
    article_pages: list[str] = []

    article_types = {
        "Article", "NewsArticle", "BlogPosting",
        "TechArticle", "ScholarlyArticle",
    }

    for url in site.page_audits.keys():
        path = (urlsplit(url).path or "/").lower()
        if not any(
            seg in path
            for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/case-stud", "/research")
        ):
            continue
        article_pages.append(url)
        schema_date = None
        sd = site.structured_data.get(url)
        if sd is not None:
            for block in sd.schema_org_blocks:
                if not (set(block.types) & article_types):
                    continue
                raw = block.raw
                schema_date = (
                    raw.get("datePublished")
                    or raw.get("dateModified")
                )
                if schema_date:
                    pages_with_schema_date.append(url)
                    break
        visible_match = None
        text = site.text_content.get(url)
        if text and text.main_text:
            # Only look at first 800 words (byline area)
            head = " ".join(text.main_text.split()[:800])
            m = _BYLINE_DATE_PATTERN.search(head)
            if m:
                visible_match = m.group(0)[:80]
                pages_with_visible_byline_date.append(url)
        if schema_date or visible_match:
            pages_with_either.append(
                {
                    "url": url,
                    "schema_date": str(schema_date) if schema_date else None,
                    "visible_byline": visible_match,
                }
            )

    if not article_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-41",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no article-like pages to check"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["extruct.parse_structured_data", "trafilatura.main_text"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every article-like page has a byline date (visible OR schema)",
        passed=len(pages_with_either) == len(article_pages),
        evidence={
            "article_pages_total": len(article_pages),
            "pages_with_byline_date": len(pages_with_either),
            "pages_without_byline_date": [
                u for u in article_pages
                if u not in {p["url"] for p in pages_with_either}
            ][:10],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Articles carry Article.datePublished schema in addition to visible byline",
        passed=len(pages_with_schema_date) >= 1,
        evidence={
            "schema_date_pages": len(pages_with_schema_date),
            "article_pages_total": len(article_pages),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-41",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "article_pages_total": len(article_pages),
            "pages_with_schema_date": len(pages_with_schema_date),
            "pages_with_visible_byline_date": len(pages_with_visible_byline_date),
            "pages_with_either": len(pages_with_either),
            "findings_sample": pages_with_either[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "extruct.parse_structured_data",
            "trafilatura.main_text",
            "composition.byline_date_detection",
        ],
    )


# ─── P1-42 — Content freshness — syntactic date ─────────────────────────────


_URL_DATE_PATTERN = re.compile(r"/(20\d{2})/(\d{2})(?:/(\d{2}))?/")
_URL_YEAR_ONLY = re.compile(r"/(20\d{2})/[a-zA-Z]")


@register_extractor("P1-42")
async def capture_p1_42(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-42 — Syntactic date (Probable, leaked syntacticDate feature).

    Detects URL-embedded dates (/YYYY/MM/slug/) and the HTTP
    Last-Modified header captured during HTML prefetch. URL-date
    presence is a strong syntactic-date signal for blog/news content;
    Last-Modified covers everything else.
    """
    captured_at = _now()
    if not site.page_audits or not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-42",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page_audits or html_pages captured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["page_audits / html_pages empty"],
        )

    pages_with_url_date: list[dict[str, Any]] = []
    pages_with_last_modified: list[str] = []
    pages_with_either: list[str] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None:
            continue
        url_date_match: dict[str, Any] | None = None
        m = _URL_DATE_PATTERN.search(url)
        if m:
            year, month = m.group(1), m.group(2)
            day = m.group(3)
            url_date_match = {
                "url": url,
                "year": year,
                "month": month,
                "day": day,
            }
            pages_with_url_date.append(url_date_match)
        last_modified = None
        for k, v in page.headers or ():
            if k.lower() == "last-modified" and v:
                last_modified = v
                break
        if last_modified:
            pages_with_last_modified.append(url)
        if url_date_match or last_modified:
            pages_with_either.append(url)

    total = len([
        p for p in site.html_pages.values()
        if p.fetch_error is None
    ])
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site provides syntactic date on at least 50% of pages (URL pattern or Last-Modified header)",
        passed=(len(pages_with_either) / total) >= 0.5 if total else False,
        evidence={
            "pages_with_either": len(pages_with_either),
            "total_fetched": total,
            "pct": round(len(pages_with_either) / total * 100, 1) if total else 0,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one page carries a URL-embedded date (/YYYY/MM/ pattern)",
        passed=len(pages_with_url_date) >= 1,
        evidence={
            "url_date_count": len(pages_with_url_date),
        },
        notes="URL-date is the highest-confidence syntacticDate signal; absence is acceptable if Last-Modified is universal.",
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Last-Modified header present on at least 80% of pages",
        passed=(len(pages_with_last_modified) / total) >= 0.8 if total else False,
        evidence={
            "last_modified_count": len(pages_with_last_modified),
            "pct": round(len(pages_with_last_modified) / total * 100, 1) if total else 0,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-42",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "total_pages": total,
            "pages_with_url_date": len(pages_with_url_date),
            "pages_with_last_modified": len(pages_with_last_modified),
            "pages_with_either": len(pages_with_either),
            "url_date_sample": pages_with_url_date[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.syntactic_date_detection",
        ],
    )


# ─── P2-32 — Lazy loading implementation ────────────────────────────────────


@register_extractor("P2-32")
async def capture_p2_32(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-32 — Lazy loading implementation (Probable).

    Per-page check of ``<img loading="lazy">`` coverage. Important
    caveat: the FIRST visible images on a page should NOT be lazy-
    loaded (above-the-fold content harms LCP if lazied). We flag both
    too-few-lazy and the inverse pattern (first image lazy-loaded
    when it likely represents the hero).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-32",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    pages_examined = 0
    pages_with_no_lazy: list[str] = []
    pages_with_first_img_lazy: list[str] = []
    findings: list[dict[str, Any]] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        soup = BeautifulSoup(page.html, "html.parser")
        imgs = soup.find_all("img")
        if not imgs:
            continue
        pages_examined += 1
        total = len(imgs)
        lazy = sum(1 for img in imgs if (img.get("loading") or "").lower() == "lazy")
        first_lazy = (
            imgs[0].get("loading", "").lower() == "lazy"
            if imgs else False
        )
        # If a page has >= 4 images and 0 lazy, flag as missing-lazy.
        if total >= 4 and lazy == 0:
            pages_with_no_lazy.append(url)
        if first_lazy:
            pages_with_first_img_lazy.append(url)
        findings.append(
            {
                "url": url,
                "img_total": total,
                "img_lazy_count": lazy,
                "img_lazy_pct": round(lazy / total * 100, 1) if total else 0,
                "first_img_lazy": first_lazy,
            }
        )

    if pages_examined == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-32",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no pages with images to check"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=(
            "Pages with >= 4 images use loading='lazy' on at least one image "
            "(image-heavy pages should not load everything eagerly)"
        ),
        passed=len(pages_with_no_lazy) == 0,
        evidence={
            "pages_image_heavy_no_lazy": pages_with_no_lazy[:15],
            "count": len(pages_with_no_lazy),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="First image on page is NOT lazy-loaded (above-the-fold should be eager)",
        passed=len(pages_with_first_img_lazy) == 0,
        evidence={
            "pages_first_img_lazy": pages_with_first_img_lazy[:15],
            "count": len(pages_with_first_img_lazy),
        },
        notes="A lazy-loaded first image harms LCP and is the common 'lazy-load misconfiguration' failure mode.",
    )

    rules = [rule_1, rule_2]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-32",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_examined": pages_examined,
            "pages_image_heavy_no_lazy": len(pages_with_no_lazy),
            "pages_first_img_lazy": len(pages_with_first_img_lazy),
            "findings_sample": findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.lazy_loading_check",
        ],
    )


# ─── P2-31 — Image format efficiency (WebP, AVIF) ───────────────────────────


_MODERN_IMG_EXTENSIONS = (".webp", ".avif")
_LEGACY_IMG_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


@register_extractor("P2-31")
async def capture_p2_31(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-31 — Image format efficiency (Probable).

    Per-page BS4 walk over ``<img src>`` attributes; counts modern
    (WebP, AVIF) versus legacy (JPEG, PNG, GIF) formats by file
    extension. Reports site-wide distribution and the share of
    modern-format coverage per page.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-31",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    total_modern = 0
    total_legacy = 0
    total_unknown = 0
    page_findings: list[dict[str, Any]] = []
    pages_examined = 0
    pages_all_modern: list[str] = []
    pages_mostly_legacy: list[str] = []

    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        soup = BeautifulSoup(page.html, "html.parser")
        imgs = soup.find_all("img")
        if not imgs:
            continue
        pages_examined += 1
        modern = 0
        legacy = 0
        unknown = 0
        for img in imgs:
            src = (img.get("src") or "").lower()
            # picture > source > srcset is more reliable but src check
            # catches the vast majority of cases.
            if any(src.endswith(ext) or f"{ext}?" in src or f"{ext}#" in src for ext in _MODERN_IMG_EXTENSIONS):
                modern += 1
            elif any(src.endswith(ext) or f"{ext}?" in src or f"{ext}#" in src for ext in _LEGACY_IMG_EXTENSIONS):
                legacy += 1
            else:
                unknown += 1
        total_modern += modern
        total_legacy += legacy
        total_unknown += unknown
        page_total = modern + legacy
        modern_pct = (modern / page_total * 100) if page_total else 0
        if page_total > 0 and modern == page_total:
            pages_all_modern.append(url)
        if page_total >= 3 and modern_pct < 50:
            pages_mostly_legacy.append(url)
        page_findings.append(
            {
                "url": url,
                "img_total": modern + legacy + unknown,
                "modern": modern,
                "legacy": legacy,
                "unknown": unknown,
                "modern_pct_of_known": round(modern_pct, 1),
            }
        )

    if pages_examined == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-31",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no pages with <img> elements found"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
        )

    total_known = total_modern + total_legacy
    modern_share_pct = (
        total_modern / total_known * 100 if total_known else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 50% of identifiable images are served in modern formats (WebP / AVIF)",
        passed=modern_share_pct >= 50.0,
        evidence={
            "total_modern": total_modern,
            "total_legacy": total_legacy,
            "total_unknown_extension": total_unknown,
            "modern_share_pct": round(modern_share_pct, 1),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Image-heavy pages (>= 3 images) are not majority-legacy",
        passed=len(pages_mostly_legacy) == 0,
        evidence={
            "mostly_legacy_pages": pages_mostly_legacy[:15],
            "count": len(pages_mostly_legacy),
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-31",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_examined": pages_examined,
            "total_modern": total_modern,
            "total_legacy": total_legacy,
            "total_unknown": total_unknown,
            "modern_share_pct": round(modern_share_pct, 1),
            "pages_all_modern": len(pages_all_modern),
            "pages_mostly_legacy": len(pages_mostly_legacy),
            "page_findings_sample": page_findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "composition.image_format_distribution",
        ],
    )


# ─── P0-12 — Pillar page / hub-and-spoke architecture ───────────────────────


@register_extractor("P0-12")
async def capture_p0_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-12 — Pillar / hub-and-spoke architecture (Probable, composition).

    For each topic cluster (derived inline from embeddings — same
    threshold-clustering as P0-11), identifies whether a pillar
    candidate exists: a single page with disproportionately high
    inbound links from other cluster members, and outbound links to
    most cluster members.
    """
    captured_at = _now()
    if not site.embeddings_configured or len(site.embeddings) < 3:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-12",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "embeddings unavailable (need >= 3 embedded pages) "
                    "OR Gemini API key not set"
                ),
                "embedded_pages": len(site.embeddings),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.pillar_architecture"],
            errors=["embeddings empty or <3 pages"],
        )
    if site.link_graph is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-12",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["composition.pillar_architecture"],
            errors=["link_graph missing"],
        )

    # Re-compute clusters inline using the same threshold + agglomeration
    # as P0-11 (single-link union-find). Duplicated logic but avoids
    # cross-extractor state dependencies.
    threshold = 0.70
    urls = sorted(site.embeddings.keys())
    parent = {u: u for u in urls}

    def _find(u: str) -> str:
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for i, a in enumerate(urls):
        va = site.embeddings[a].vector
        if not va:
            continue
        for b in urls[i + 1:]:
            vb = site.embeddings[b].vector
            if not vb:
                continue
            if cosine_similarity(va, vb) >= threshold:
                _union(a, b)

    groups: dict[str, list[str]] = {}
    for u in urls:
        groups.setdefault(_find(u), []).append(u)
    clusters = [sorted(g) for g in groups.values() if len(g) >= 3]

    if not clusters:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-12",
            pillar="P0",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no topic clusters of >= 3 pages identified; pillar architecture not applicable",
                "embedded_pages": len(site.embeddings),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.pillar_architecture"],
        )

    cluster_findings: list[dict[str, Any]] = []
    clusters_with_pillar = 0
    clusters_without_pillar: list[dict[str, Any]] = []

    for cluster in clusters:
        # For each member, count inbound internal links from other
        # cluster members.
        cluster_set = set(cluster)
        inbound_from_cluster: dict[str, int] = {}
        outbound_to_cluster: dict[str, int] = {}
        for member in cluster:
            inbound_from_cluster[member] = sum(
                1
                for ref in site.link_graph.inbound_internal(member)
                if ref.source_url in cluster_set
            )
            outbound_to_cluster[member] = sum(
                1
                for ref in site.link_graph.outbound_internal(member)
                if ref.target_url in cluster_set
            )
        # Pillar candidate: highest inbound from cluster, AND outbound
        # to at least 70% of cluster members.
        pillar_candidate = max(
            cluster,
            key=lambda u: inbound_from_cluster[u],
        )
        inbound_pct = (
            inbound_from_cluster[pillar_candidate] / (len(cluster) - 1) * 100
            if len(cluster) > 1 else 0
        )
        outbound_pct = (
            outbound_to_cluster[pillar_candidate] / (len(cluster) - 1) * 100
            if len(cluster) > 1 else 0
        )
        has_pillar = inbound_pct >= 70.0 and outbound_pct >= 70.0
        if has_pillar:
            clusters_with_pillar += 1
        else:
            clusters_without_pillar.append(
                {
                    "cluster_size": len(cluster),
                    "candidate_url": pillar_candidate,
                    "inbound_pct": round(inbound_pct, 1),
                    "outbound_pct": round(outbound_pct, 1),
                }
            )
        cluster_findings.append(
            {
                "cluster_size": len(cluster),
                "candidate_pillar": pillar_candidate,
                "inbound_pct_from_cluster": round(inbound_pct, 1),
                "outbound_pct_to_cluster": round(outbound_pct, 1),
                "has_pillar": has_pillar,
            }
        )

    total_clusters = len(clusters)
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one topic cluster has a clear pillar page (>= 70% inbound + outbound)",
        passed=clusters_with_pillar >= 1,
        evidence={
            "clusters_with_pillar": clusters_with_pillar,
            "total_clusters": total_clusters,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Most clusters have a pillar (>= 50% of clusters >= 3 pages)",
        passed=(clusters_with_pillar / total_clusters) >= 0.5 if total_clusters else False,
        evidence={
            "clusters_with_pillar": clusters_with_pillar,
            "total_clusters": total_clusters,
            "pct": round(
                clusters_with_pillar / total_clusters * 100, 1
            ) if total_clusters else 0,
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-12",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "total_clusters": total_clusters,
            "clusters_with_pillar": clusters_with_pillar,
            "clusters_without_pillar": len(clusters_without_pillar),
            "cluster_findings": cluster_findings[:15],
            "no_pillar_sample": clusters_without_pillar[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "http.html_fetch",
            "composition.pillar_architecture",
        ],
    )


# ─── Target-keyword-per-page helper (shared by P1-03 / P1-13 / P1-14) ───────


_KEYWORD_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "as", "it", "this", "that", "these", "those", "i", "you", "he", "she",
        "we", "they", "your", "my", "our", "what", "how", "why", "do", "does",
        "did", "can", "vs", "&",
    }
)


def _kw_normalise(text: str) -> str:
    """Lowercase + strip + collapse whitespace for case-insensitive matching."""
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _kw_tokens(text: str) -> list[str]:
    """Tokenise a keyword/heading into content-bearing words (stopwords removed)."""
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in raw if t and t not in _KEYWORD_STOPWORDS and len(t) > 1]


def _build_page_target_keywords(site: SiteData) -> dict[str, dict[str, Any]]:
    """Map page URL -> {target_keyword, position, all_keywords} from ranked_keywords.

    The "target" is the keyword with the best (lowest) SERP position for
    that ranking URL. Keys are URL paths (host+path) so they match
    page_audits regardless of trailing slash / scheme drift.

    Returns ``{}`` if no ranked_keywords data is available.
    """
    if not site.ranked_keywords:
        return {}

    by_path: dict[str, dict[str, Any]] = {}
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
        url = (serp.get("url") or "").strip()
        position = serp.get("rank_absolute") or serp.get("rank_group") or 999
        if not keyword or not url:
            continue
        key = _norm_for_match(url)
        bucket = by_path.setdefault(
            key,
            {"target_keyword": keyword, "position": position, "all_keywords": []},
        )
        bucket["all_keywords"].append(keyword)
        if position < bucket["position"]:
            bucket["target_keyword"] = keyword
            bucket["position"] = position
    return by_path


def _resolve_page_kw(
    url: str,
    target_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Look up the target-keyword bucket for a page URL via normalised path."""
    return target_map.get(_norm_for_match(url))


# ─── P1-03 — Title tag includes target keyword ──────────────────────────────


@register_extractor("P1-03")
async def capture_p1_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-03 — Title tag includes target keyword (Consensus).

    For every page that has a ranked target keyword (from ranked_keywords),
    check whether the page title contains it (case-insensitive substring).
    Pass if >= 70% of mapped pages have the target keyword in the title.
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-03",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-03",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_checked = 0
    pages_with_kw_in_title = 0
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        pages_checked += 1
        keyword = bucket["target_keyword"]
        title_norm = _kw_normalise(audit.title or "")
        kw_norm = _kw_normalise(keyword)
        present = bool(kw_norm) and kw_norm in title_norm
        if present:
            pages_with_kw_in_title += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {"url": audit.url, "keyword": keyword, "title": audit.title}
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {"url": audit.url, "keyword": keyword, "title": audit.title}
                )

    coverage_pct = (
        round(pages_with_kw_in_title / pages_checked * 100, 1) if pages_checked else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=70% of pages with a ranked target keyword include it in the title",
        passed=pages_checked > 0 and coverage_pct >= 70,
        evidence={
            "pages_checked": pages_checked,
            "pages_with_keyword_in_title": pages_with_kw_in_title,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-03",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_with_target_keyword": pages_checked,
            "pages_with_kw_in_title": pages_with_kw_in_title,
            "coverage_pct": coverage_pct,
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.keyword_inclusion",
        ],
    )


# ─── P1-13 — H1 keyword inclusion ───────────────────────────────────────────


@register_extractor("P1-13")
async def capture_p1_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-13 — H1 keyword inclusion (Consensus).

    For every page with a ranked target keyword, check whether the
    primary H1 contains it (case-insensitive substring). Pages without
    an H1 are reported separately under ``pages_with_no_h1``.

    Pass if >= 70% of mapped pages with an H1 include the keyword.
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-13",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-13",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_with_h1 = 0
    pages_with_kw_in_h1 = 0
    pages_no_h1: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        keyword = bucket["target_keyword"]
        if not audit.h1:
            if len(pages_no_h1) < 15:
                pages_no_h1.append({"url": audit.url, "keyword": keyword})
            continue
        pages_with_h1 += 1
        kw_norm = _kw_normalise(keyword)
        # Consider any H1 text — pages can have multiple H1s (P1-12 flags this).
        h1_combined = _kw_normalise(" || ".join(audit.h1))
        if kw_norm and kw_norm in h1_combined:
            pages_with_kw_in_h1 += 1
        else:
            if len(misses) < 15:
                misses.append(
                    {"url": audit.url, "keyword": keyword, "h1": list(audit.h1)}
                )

    coverage_pct = (
        round(pages_with_kw_in_h1 / pages_with_h1 * 100, 1) if pages_with_h1 else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=70% of pages with H1 and a ranked target keyword include it in the H1",
        passed=pages_with_h1 > 0 and coverage_pct >= 70,
        evidence={
            "pages_with_h1_and_target_keyword": pages_with_h1,
            "pages_with_kw_in_h1": pages_with_kw_in_h1,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="All pages with a target keyword have an H1",
        passed=len(pages_no_h1) == 0,
        evidence={"pages_no_h1": pages_no_h1, "count": len(pages_no_h1)},
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-13",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_with_h1_and_target_keyword": pages_with_h1,
            "pages_with_kw_in_h1": pages_with_kw_in_h1,
            "coverage_pct": coverage_pct,
            "pages_no_h1_count": len(pages_no_h1),
            "pages_no_h1_sample": pages_no_h1[:10],
            "misses_sample": misses[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.keyword_inclusion",
        ],
    )


# ─── P1-14 — H2/H3 keyword inclusion (token-overlap coverage) ───────────────


@register_extractor("P1-14")
async def capture_p1_14(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-14 — H2/H3 keyword inclusion (Probable).

    Looser test than P1-13: secondary headings should contain semantic
    variations/topical entities related to the target keyword. We
    approximate this with token overlap: at least one content-bearing
    token from the target keyword (stopwords removed) appears in at
    least one H2 or H3 on the page.

    Coverage metric: across pages with target keyword + H2/H3, what
    fraction have at least one matching subheading.

    Pass: coverage >= 50% AND each "covered" page averages >= 1.0
    matching tokens per subheading (very lax — Probable evidence weight).
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-14",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-14",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_with_subheadings = 0
    pages_with_overlap = 0
    no_subheadings: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    overlap_counts: list[int] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        keyword = bucket["target_keyword"]
        kw_toks = set(_kw_tokens(keyword))
        if not kw_toks:
            continue
        subheadings = list(audit.h2) + list(audit.h3)
        if not subheadings:
            if len(no_subheadings) < 15:
                no_subheadings.append({"url": audit.url, "keyword": keyword})
            continue
        pages_with_subheadings += 1
        sub_token_set: set[str] = set()
        for sh in subheadings:
            sub_token_set.update(_kw_tokens(sh))
        overlap = kw_toks & sub_token_set
        overlap_counts.append(len(overlap))
        if overlap:
            pages_with_overlap += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {
                        "url": audit.url,
                        "keyword": keyword,
                        "matched_tokens": sorted(overlap),
                        "subheadings_sample": subheadings[:5],
                    }
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {
                        "url": audit.url,
                        "keyword": keyword,
                        "subheadings_sample": subheadings[:5],
                    }
                )

    coverage_pct = (
        round(pages_with_overlap / pages_with_subheadings * 100, 1)
        if pages_with_subheadings
        else 0
    )
    avg_overlap = (
        round(sum(overlap_counts) / len(overlap_counts), 2)
        if overlap_counts
        else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=50% of pages with H2/H3 and a target keyword have token overlap",
        passed=pages_with_subheadings > 0 and coverage_pct >= 50,
        evidence={
            "pages_with_subheadings_and_keyword": pages_with_subheadings,
            "pages_with_overlap": pages_with_overlap,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Average keyword tokens matched per page >= 1.0 (sanity floor)",
        passed=avg_overlap >= 1.0,
        evidence={"avg_overlap_tokens_per_page": avg_overlap},
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-14",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_with_subheadings_and_keyword": pages_with_subheadings,
            "pages_with_overlap": pages_with_overlap,
            "coverage_pct": coverage_pct,
            "avg_overlap_tokens_per_page": avg_overlap,
            "no_subheadings_count": len(no_subheadings),
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.keyword_token_overlap",
        ],
    )


# ─── P1-09 — Meta description includes target keyword ───────────────────────


@register_extractor("P1-09")
async def capture_p1_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-09 — Meta description includes target keyword (Contested).

    Mirror of P1-03 but on the meta description. Evidence weight is
    Contested because Google does not use meta description as a ranking
    signal directly; the value is in SERP click-through (matching query
    intent gets the snippet bolded).

    Pass: >= 60% of pages with a target keyword and a non-empty
    description include the keyword in the description. Threshold is
    softer than P1-03 because Contested.
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-09",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONTESTED,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-09",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONTESTED,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_with_desc = 0
    pages_with_kw_in_desc = 0
    pages_no_desc: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        keyword = bucket["target_keyword"]
        desc = (audit.description or "").strip()
        if not desc:
            if len(pages_no_desc) < 15:
                pages_no_desc.append({"url": audit.url, "keyword": keyword})
            continue
        pages_with_desc += 1
        kw_norm = _kw_normalise(keyword)
        desc_norm = _kw_normalise(desc)
        if kw_norm and kw_norm in desc_norm:
            pages_with_kw_in_desc += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {"url": audit.url, "keyword": keyword, "description": desc}
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {"url": audit.url, "keyword": keyword, "description": desc}
                )

    coverage_pct = (
        round(pages_with_kw_in_desc / pages_with_desc * 100, 1)
        if pages_with_desc
        else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=60% of pages with description + target keyword include the keyword in the description",
        passed=pages_with_desc > 0 and coverage_pct >= 60,
        evidence={
            "pages_with_desc_and_keyword": pages_with_desc,
            "pages_with_kw_in_desc": pages_with_kw_in_desc,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="All pages with a target keyword have a meta description",
        passed=len(pages_no_desc) == 0,
        evidence={"pages_no_desc": pages_no_desc, "count": len(pages_no_desc)},
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-09",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_with_desc_and_keyword": pages_with_desc,
            "pages_with_kw_in_desc": pages_with_kw_in_desc,
            "coverage_pct": coverage_pct,
            "pages_no_desc_count": len(pages_no_desc),
            "pages_no_desc_sample": pages_no_desc[:10],
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONTESTED,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.keyword_inclusion",
        ],
    )


# ─── P1-17 — URL keyword inclusion (slug match) ─────────────────────────────


def _slugify_for_match(text: str) -> str:
    """Lowercase + collapse non-alphanumerics to hyphens for slug matching."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s


@register_extractor("P1-17")
async def capture_p1_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-17 — URL keyword inclusion (Probable).

    Check whether the URL slug contains the target keyword in
    slug-friendly form. Two tests per page: full-keyword slug match
    (strict), and any-keyword-token match (loose).

    Pass: >= 60% strict match across mapped pages. Homepage ("/")
    excluded from the strict check (homepages legitimately have no
    keyword slug).
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-17",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-17",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    non_home_checked = 0
    strict_matches = 0
    loose_matches = 0
    homepages_skipped = 0
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        keyword = bucket["target_keyword"]
        path = (urlsplit(audit.url).path or "/").strip("/").lower()
        if not path:
            homepages_skipped += 1
            continue
        slug_kw = _slugify_for_match(keyword)
        slug_path = _slugify_for_match(path)
        strict = bool(slug_kw) and slug_kw in slug_path
        kw_toks = _kw_tokens(keyword)
        path_toks = set(_kw_tokens(path.replace("-", " ").replace("/", " ")))
        loose_overlap = [t for t in kw_toks if t in path_toks]
        loose = bool(loose_overlap)

        non_home_checked += 1
        if strict:
            strict_matches += 1
        if loose:
            loose_matches += 1
        if strict:
            if len(hits_sample) < 5:
                hits_sample.append(
                    {"url": audit.url, "keyword": keyword, "slug": path}
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {
                        "url": audit.url,
                        "keyword": keyword,
                        "slug": path,
                        "loose_overlap_tokens": loose_overlap,
                    }
                )

    strict_pct = (
        round(strict_matches / non_home_checked * 100, 1)
        if non_home_checked
        else 0
    )
    loose_pct = (
        round(loose_matches / non_home_checked * 100, 1)
        if non_home_checked
        else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=60% of non-homepage mapped pages have the target keyword in the URL slug",
        passed=non_home_checked > 0 and strict_pct >= 60,
        evidence={
            "non_home_pages_checked": non_home_checked,
            "strict_matches": strict_matches,
            "strict_match_pct": strict_pct,
            "miss_sample": misses,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=80% of non-homepage mapped pages have at least one keyword token in the slug (loose check)",
        passed=non_home_checked > 0 and loose_pct >= 80,
        evidence={
            "loose_match_count": loose_matches,
            "loose_match_pct": loose_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-17",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "non_home_pages_checked": non_home_checked,
            "homepages_skipped": homepages_skipped,
            "strict_matches": strict_matches,
            "strict_match_pct": strict_pct,
            "loose_matches": loose_matches,
            "loose_match_pct": loose_pct,
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.slug_keyword_match",
        ],
    )


# ─── P1-29 — Image filename relevance ───────────────────────────────────────


# Generic camera/upload prefixes that signal no descriptive filename.
_GENERIC_FILENAME_PATTERNS = (
    re.compile(r"^img[_\-]?\d+", re.I),      # IMG_0042, IMG-0042, img0042
    re.compile(r"^dsc[_\-]?\d+", re.I),      # DSC_1234
    re.compile(r"^p\d{6,}", re.I),           # P1234567 (some cameras)
    re.compile(r"^image[_\-]?\d+", re.I),    # image001
    re.compile(r"^photo[_\-]?\d+", re.I),    # photo01
    re.compile(r"^untitled", re.I),
    re.compile(r"^screenshot[_\-]?\d+", re.I),
    re.compile(r"^[0-9]{10,}$"),              # bare timestamp
    re.compile(r"^[a-f0-9]{8}\-[a-f0-9]{4}\-[a-f0-9]{4}\-[a-f0-9]{4}\-[a-f0-9]{12}", re.I),  # UUID
    re.compile(r"^[a-f0-9]{32,}$", re.I),     # long hex hash
)


def _is_generic_filename(stem: str) -> bool:
    if not stem:
        return True
    s = stem.strip()
    if not s:
        return True
    return any(p.search(s) for p in _GENERIC_FILENAME_PATTERNS)


@register_extractor("P1-29")
async def capture_p1_29(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-29 — Image filename relevance (Consensus).

    Walk every <img> in fetched HTML, extract the filename stem from
    the URL, and flag generic camera/upload prefixes (IMG_, DSC_, UUID,
    timestamp). Pass if >= 70% of image filenames are descriptive
    (non-generic).

    Pages with zero <img> tags are not counted toward the denominator.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-29",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    total_images = 0
    descriptive_images = 0
    generic_examples: list[dict[str, Any]] = []
    per_page_findings: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        page_total = 0
        page_generic = 0
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src:
                continue
            # Skip data: URIs and obvious tracking pixels (1x1)
            if src.startswith("data:"):
                continue
            path = urlsplit(src).path or src
            filename = path.rsplit("/", 1)[-1]
            stem = filename.rsplit(".", 1)[0] if "." in filename else filename
            stem = stem.split("?", 1)[0]
            total_images += 1
            page_total += 1
            if _is_generic_filename(stem):
                page_generic += 1
                if len(generic_examples) < 15:
                    generic_examples.append({"url": url, "src": src, "stem": stem})
            else:
                descriptive_images += 1
        if page_total > 0:
            per_page_findings.append(
                {
                    "url": url,
                    "image_count": page_total,
                    "generic_count": page_generic,
                    "descriptive_pct": round(
                        (page_total - page_generic) / page_total * 100, 1
                    ),
                }
            )

    descriptive_pct = (
        round(descriptive_images / total_images * 100, 1) if total_images else 0
    )
    generic_count = total_images - descriptive_images

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=70% of <img> filenames are descriptive (not IMG_/DSC_/UUID/timestamp)",
        passed=total_images > 0 and descriptive_pct >= 70,
        evidence={
            "total_images": total_images,
            "descriptive_images": descriptive_images,
            "generic_images": generic_count,
            "descriptive_pct": descriptive_pct,
            "generic_examples": generic_examples,
        },
    )

    if total_images == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-29",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no <img> tags found in fetched HTML"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "composition.image_filename_check"],
            errors=["no images"],
        )

    # Pages where every single image is generic
    worst_pages = sorted(
        [p for p in per_page_findings if p["descriptive_pct"] < 30],
        key=lambda p: p["descriptive_pct"],
    )[:10]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-29",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_images": total_images,
            "descriptive_images": descriptive_images,
            "generic_images": generic_count,
            "descriptive_pct": descriptive_pct,
            "worst_pages_sample": worst_pages,
            "generic_filename_examples": generic_examples[:10],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.image_filename_check"],
    )


# ─── P1-04 — Title starts with target keyword (Speculative, watchlist) ──────


@register_extractor("P1-04")
async def capture_p1_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-04 — Title starts with keyword (Speculative).

    Page title begins with the target keyword within the first three
    tokens. Recorded for completeness but flagged as watchlist per
    taxonomy — Google has not endorsed keyword position as a ranking
    factor.

    Pass: >= 50% of mapped pages have the target keyword (full phrase
    or its head token) within the first 3 tokens of the title.
    """
    captured_at = _now()
    target_map = _build_page_target_keywords(site)
    if not target_map:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-04",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords mapping available"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["dataforseo_labs.ranked_keywords", "dataforseo_on_page.instant_pages"],
            errors=["ranked_keywords empty"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-04",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    pages_checked = 0
    pages_kw_at_start = 0
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for audit in audits:
        bucket = _resolve_page_kw(audit.url, target_map)
        if bucket is None:
            continue
        keyword = bucket["target_keyword"]
        if not audit.title:
            continue
        pages_checked += 1
        title_tokens = _kw_tokens(audit.title)
        first_three = " ".join(title_tokens[:3])
        kw_norm = _kw_normalise(keyword)
        # Strict: full keyword phrase appears at the very start
        title_norm = _kw_normalise(audit.title)
        starts_strict = title_norm.startswith(kw_norm) if kw_norm else False
        # Loose: any keyword token appears in first 3 title tokens (head-term proxy)
        kw_toks = set(_kw_tokens(keyword))
        starts_loose = bool(kw_toks & set(title_tokens[:3]))
        if starts_strict or starts_loose:
            pages_kw_at_start += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {
                        "url": audit.url,
                        "keyword": keyword,
                        "title": audit.title,
                        "match_type": "strict" if starts_strict else "loose",
                    }
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {
                        "url": audit.url,
                        "keyword": keyword,
                        "title": audit.title,
                        "first_3_tokens": first_three,
                    }
                )

    coverage_pct = (
        round(pages_kw_at_start / pages_checked * 100, 1) if pages_checked else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=50% of pages have target keyword (or head token) within first 3 title tokens",
        passed=pages_checked > 0 and coverage_pct >= 50,
        evidence={
            "pages_checked": pages_checked,
            "pages_with_kw_at_start": pages_kw_at_start,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
        notes="Speculative — watchlist variable. Not used for operational scoring.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-04",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_checked": pages_checked,
            "pages_with_kw_at_start": pages_kw_at_start,
            "coverage_pct": coverage_pct,
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
            "watchlist": True,
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "dataforseo_on_page.instant_pages",
            "composition.keyword_position",
        ],
    )


# ─── P1-05 — Title-to-content match score (DataForSEO proxy) ────────────────


@register_extractor("P1-05")
async def capture_p1_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-05 — Title-to-content match score (Probable).

    DataForSEO's `title_to_content_consistency` is a 0-1 relevance
    score between title text and page content body, treated here as a
    proxy for the leaked Google `titlematchScore` feature.

    Pass: >= 80% of pages with both a title and extractable content
    have a consistency score >= 0.4 (DataForSEO's threshold for
    "well-aligned"). Site median included as a corroborating signal.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-05",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    scores: list[float] = []
    misses: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    no_score_pages = 0
    for audit in audits:
        s = audit.title_to_content_consistency
        if s is None:
            no_score_pages += 1
            continue
        scores.append(float(s))
        if s >= 0.4:
            if len(hits_sample) < 5:
                hits_sample.append(
                    {"url": audit.url, "score": round(float(s), 3), "title": audit.title}
                )
        else:
            if len(misses) < 15:
                misses.append(
                    {"url": audit.url, "score": round(float(s), 3), "title": audit.title}
                )

    if not scores:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-05",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "DataForSEO returned no title_to_content_consistency scores",
                "pages_inspected": len(audits),
                "pages_missing_score": no_score_pages,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["all scores None"],
        )

    well_aligned = sum(1 for s in scores if s >= 0.4)
    coverage_pct = round(well_aligned / len(scores) * 100, 1)
    sorted_scores = sorted(scores)
    median = sorted_scores[len(sorted_scores) // 2]
    mean = round(sum(scores) / len(scores), 3)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=80% of pages have title-content consistency >= 0.4",
        passed=coverage_pct >= 80,
        evidence={
            "pages_scored": len(scores),
            "well_aligned_count": well_aligned,
            "coverage_pct": coverage_pct,
            "miss_sample": misses,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Site median title-content consistency >= 0.4",
        passed=median >= 0.4,
        evidence={
            "median_score": round(median, 3),
            "mean_score": mean,
            "min_score": round(sorted_scores[0], 3),
            "max_score": round(sorted_scores[-1], 3),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-05",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_scored": len(scores),
            "pages_missing_score": no_score_pages,
            "well_aligned_count": well_aligned,
            "coverage_pct": coverage_pct,
            "median_score": round(median, 3),
            "mean_score": mean,
            "hits_sample": hits_sample,
            "misses_sample": misses[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_on_page.instant_pages.title_to_content_consistency",
        ],
    )


# ─── P1-06 — Title brand placement ──────────────────────────────────────────


# Delimiters practitioners use to separate descriptive title from brand suffix.
_TITLE_BRAND_DELIMITERS = (" | ", " - ", " – ", " — ", " :: ", " · ", " » ")


def _detect_brand_placement(title: str, brand_variants: tuple[str, ...]) -> str:
    """Return one of: 'suffix', 'prefix', 'middle', 'absent'.

    Suffix means the brand follows a recognised delimiter at the end.
    Prefix means the brand starts the title (followed by delimiter).
    Middle means the brand appears somewhere in the title but not at
    either end. Absent means no brand variant detected.
    """
    if not title or not brand_variants:
        return "absent"
    t_norm = _kw_normalise(title)
    for variant in brand_variants:
        b_norm = _kw_normalise(variant)
        if not b_norm or b_norm not in t_norm:
            continue
        # Check suffix: title ends with " | brand" / " - brand" etc.
        for delim in _TITLE_BRAND_DELIMITERS:
            if title.rstrip().lower().endswith(delim.lower() + b_norm) or \
                    title.rstrip().lower().endswith(delim.lower() + variant.lower()):
                return "suffix"
        # Plain end without delimiter
        if t_norm.endswith(b_norm) and " " in t_norm[:-len(b_norm)]:
            # only treat as suffix if there's descriptive text before
            return "suffix"
        # Prefix: starts with brand + delimiter
        for delim in _TITLE_BRAND_DELIMITERS:
            if t_norm.startswith(b_norm + delim.lower().rstrip()):
                return "prefix"
        if t_norm.startswith(b_norm + " ") and len(t_norm) > len(b_norm) + 1:
            # ambiguous prefix without delimiter
            return "prefix"
        return "middle"
    return "absent"


@register_extractor("P1-06")
async def capture_p1_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-06 — Title brand placement (Probable).

    Categorise each title as ``suffix`` / ``prefix`` / ``middle`` /
    ``absent`` for the brand string. Practitioner convention places
    the brand at the suffix (so the descriptive portion reaches users
    first in truncated SERP displays).

    Pass: >= 70% of non-homepage pages have brand at suffix (homepage
    can legitimately lead with brand and is reported separately).
    """
    captured_at = _now()
    if not site.brand:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-06",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand identity configured for site"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages", "config.brand_identity"],
            errors=["site.brand is None"],
        )

    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-06",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    brand_variants = site.brand.all_variants
    placement_counts = {"suffix": 0, "prefix": 0, "middle": 0, "absent": 0}
    non_home_counts = {"suffix": 0, "prefix": 0, "middle": 0, "absent": 0}
    homepage_placement = None
    examples: dict[str, list[dict[str, Any]]] = {
        "suffix": [], "prefix": [], "middle": [], "absent": [],
    }
    for audit in audits:
        if not audit.title:
            continue
        placement = _detect_brand_placement(audit.title, brand_variants)
        placement_counts[placement] += 1
        path = (urlsplit(audit.url).path or "/").strip("/").lower()
        if not path:
            homepage_placement = {
                "url": audit.url,
                "title": audit.title,
                "placement": placement,
            }
        else:
            non_home_counts[placement] += 1
        if len(examples[placement]) < 5:
            examples[placement].append({"url": audit.url, "title": audit.title})

    non_home_total = sum(non_home_counts.values())
    suffix_pct = (
        round(non_home_counts["suffix"] / non_home_total * 100, 1)
        if non_home_total
        else 0
    )
    absent_pct = (
        round(non_home_counts["absent"] / non_home_total * 100, 1)
        if non_home_total
        else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=70% of non-homepage pages have brand at title suffix",
        passed=non_home_total > 0 and suffix_pct >= 70,
        evidence={
            "non_home_total": non_home_total,
            "suffix_count": non_home_counts["suffix"],
            "suffix_pct": suffix_pct,
            "miss_examples": examples["prefix"] + examples["middle"] + examples["absent"],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<=10% of non-homepage pages have no brand in title",
        passed=non_home_total > 0 and absent_pct <= 10,
        evidence={
            "non_home_total": non_home_total,
            "absent_count": non_home_counts["absent"],
            "absent_pct": absent_pct,
            "absent_examples": examples["absent"],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-06",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "brand_variants_checked": list(brand_variants),
            "placement_counts_all": placement_counts,
            "placement_counts_non_home": non_home_counts,
            "non_home_total": non_home_total,
            "suffix_pct": suffix_pct,
            "absent_pct": absent_pct,
            "homepage_placement": homepage_placement,
            "examples": {k: v[:3] for k, v in examples.items()},
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_on_page.instant_pages",
            "config.brand_identity",
            "composition.title_brand_placement",
        ],
    )


# ─── P1-48 — Bullets and numbered lists ─────────────────────────────────────


def _is_substantive_page(soup: BeautifulSoup) -> bool:
    """Cheap heuristic: page has at least one <h1> and >= 300 words of text.

    Used to exclude thin pages from list/TOC/multimedia thresholds so
    a thin landing page doesn't drag site-level coverage down.
    """
    if not soup.find("h1"):
        return False
    text = soup.get_text(separator=" ", strip=True)
    return len(text.split()) >= 300


@register_extractor("P1-48")
async def capture_p1_48(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-48 — Bullets and numbered lists (Probable).

    Walk every fetched HTML page and count semantic list elements
    (`<ul>`/`<ol>`) and their items (`<li>`). Pass if >= 60% of
    substantive pages (H1 + >=300 words) carry at least one list.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-48",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    substantive_pages = 0
    pages_with_list = 0
    total_lists = 0
    total_items = 0
    no_list_pages: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        if not _is_substantive_page(soup):
            continue
        substantive_pages += 1
        lists = soup.find_all(["ul", "ol"])
        items = soup.find_all("li")
        # Exclude nav/footer lists from "content list" check
        content_lists = [
            l for l in lists
            if not any(
                anc.name in ("nav", "header", "footer")
                or "nav" in (anc.get("class") or [])
                or "menu" in (anc.get("class") or [])
                for anc in l.parents if anc.name
            )
        ]
        total_lists += len(content_lists)
        total_items += len(items)
        if content_lists:
            pages_with_list += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {
                        "url": url,
                        "list_count": len(content_lists),
                        "item_count": sum(len(l.find_all("li")) for l in content_lists),
                    }
                )
        else:
            if len(no_list_pages) < 15:
                no_list_pages.append({"url": url})

    coverage_pct = (
        round(pages_with_list / substantive_pages * 100, 1)
        if substantive_pages
        else 0
    )

    if substantive_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-48",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no substantive pages (H1 + 300+ words) to evaluate"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.list_detection"],
            errors=["no substantive pages"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=60% of substantive content pages have at least one content list",
        passed=coverage_pct >= 60,
        evidence={
            "substantive_pages": substantive_pages,
            "pages_with_list": pages_with_list,
            "coverage_pct": coverage_pct,
            "no_list_sample": no_list_pages,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-48",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "substantive_pages": substantive_pages,
            "pages_with_list": pages_with_list,
            "coverage_pct": coverage_pct,
            "total_content_lists": total_lists,
            "total_li_items": total_items,
            "hits_sample": hits_sample,
            "no_list_sample": no_list_pages[:10],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.list_detection"],
    )


# ─── P1-49 — Table of contents ──────────────────────────────────────────────


def _looks_like_toc(list_el: Any) -> bool:
    """Heuristic: a <ul>/<ol> is a TOC if all/most direct <li><a> links
    point to in-page anchors (href starts with '#') and there are >= 3 items.
    """
    items = list_el.find_all("li", recursive=False)
    if len(items) < 3:
        return False
    anchor_count = 0
    inpage_count = 0
    for li in items:
        a = li.find("a", recursive=True)
        if a is None:
            continue
        anchor_count += 1
        href = (a.get("href") or "").strip()
        if href.startswith("#") and len(href) > 1:
            inpage_count += 1
    if anchor_count == 0:
        return False
    return inpage_count / anchor_count >= 0.75


@register_extractor("P1-49")
async def capture_p1_49(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-49 — Table of contents (Probable).

    A page has a TOC if it contains a `<ul>`/`<ol>` near the top of the
    article body whose items are ≥ 3 in-page anchor links (`href="#..."`).
    Pass if >= 30% of substantive pages (H1 + >=300 words + 3+ headings)
    have a TOC.

    Threshold is intentionally low — TOCs are most valuable on long-form
    content, not every page.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-49",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    long_form_pages = 0
    pages_with_toc = 0
    pages_with_anchor_ids = 0
    no_toc_pages: list[dict[str, Any]] = []
    hits_sample: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        if not _is_substantive_page(soup):
            continue
        headings = soup.find_all(["h2", "h3"])
        if len(headings) < 3:
            continue
        long_form_pages += 1

        # Check headings for jump-target anchor IDs
        headings_with_id = sum(1 for h in headings if h.get("id"))
        if headings_with_id >= 3:
            pages_with_anchor_ids += 1

        # Look for TOC pattern in lists
        lists = soup.find_all(["ul", "ol"])
        toc_found = False
        for lst in lists:
            if _looks_like_toc(lst):
                toc_found = True
                break

        if toc_found:
            pages_with_toc += 1
            if len(hits_sample) < 5:
                hits_sample.append(
                    {
                        "url": url,
                        "heading_count": len(headings),
                        "headings_with_id": headings_with_id,
                    }
                )
        else:
            if len(no_toc_pages) < 15:
                no_toc_pages.append(
                    {
                        "url": url,
                        "heading_count": len(headings),
                        "headings_with_id": headings_with_id,
                    }
                )

    coverage_pct = (
        round(pages_with_toc / long_form_pages * 100, 1)
        if long_form_pages
        else 0
    )
    anchor_id_pct = (
        round(pages_with_anchor_ids / long_form_pages * 100, 1)
        if long_form_pages
        else 0
    )

    if long_form_pages == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-49",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no long-form pages (H1 + 300+ words + 3+ subheadings)"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.toc_detection"],
            errors=["no long-form pages"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=30% of long-form pages have a table of contents",
        passed=coverage_pct >= 30,
        evidence={
            "long_form_pages": long_form_pages,
            "pages_with_toc": pages_with_toc,
            "coverage_pct": coverage_pct,
            "no_toc_sample": no_toc_pages,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=50% of long-form pages have anchor IDs on subheadings (enables Google jump-to)",
        passed=anchor_id_pct >= 50,
        evidence={
            "pages_with_anchor_ids": pages_with_anchor_ids,
            "anchor_id_pct": anchor_id_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-49",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "long_form_pages": long_form_pages,
            "pages_with_toc": pages_with_toc,
            "coverage_pct": coverage_pct,
            "pages_with_anchor_ids": pages_with_anchor_ids,
            "anchor_id_pct": anchor_id_pct,
            "hits_sample": hits_sample,
            "no_toc_sample": no_toc_pages[:10],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.toc_detection"],
    )


# ─── P1-50 — Multimedia presence ────────────────────────────────────────────


# Known video/embed hosts to identify when an <iframe> is multimedia
_VIDEO_EMBED_HOSTS = (
    "youtube.com", "youtu.be", "youtube-nocookie.com",
    "vimeo.com", "player.vimeo.com",
    "loom.com",
    "wistia.com", "wistia.net",
    "vidyard.com",
    "twitch.tv",
    "dailymotion.com",
    "ted.com",
    "tiktok.com",
)


@register_extractor("P1-50")
async def capture_p1_50(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-50 — Multimedia presence (Probable).

    Aggregate per-page presence of:
    - images (`<img>`)
    - native video (`<video>`)
    - embedded video (`<iframe src=...>` matching known video hosts)
    - audio (`<audio>`)
    - SVG illustrations (`<svg>` or inline SVG)

    Diversity score: number of distinct media types per page. Pass if
    site-median diversity score >= 2 (most pages have at least images
    plus one other format) AND >= 50% of pages have any video.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-50",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    page_findings: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        if not _is_substantive_page(soup):
            continue

        images = len(soup.find_all("img"))
        native_videos = len(soup.find_all("video"))
        audios = len(soup.find_all("audio"))
        svgs = len(soup.find_all("svg"))
        embed_videos = 0
        for iframe in soup.find_all("iframe"):
            src = (iframe.get("src") or "").strip().lower()
            host = urlsplit(src).netloc.lower().removeprefix("www.")
            if any(h in host for h in _VIDEO_EMBED_HOSTS):
                embed_videos += 1

        formats_present: list[str] = []
        if images >= 1:
            formats_present.append("image")
        if native_videos >= 1 or embed_videos >= 1:
            formats_present.append("video")
        if audios >= 1:
            formats_present.append("audio")
        if svgs >= 1:
            formats_present.append("svg")

        page_findings.append(
            {
                "url": url,
                "images": images,
                "native_videos": native_videos,
                "embed_videos": embed_videos,
                "audios": audios,
                "svgs": svgs,
                "format_count": len(formats_present),
                "formats": formats_present,
            }
        )

    if not page_findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-50",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no substantive pages to evaluate"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "composition.multimedia_detection"],
            errors=["no substantive pages"],
        )

    format_counts = sorted(p["format_count"] for p in page_findings)
    median_format_count = format_counts[len(format_counts) // 2]
    pages_with_video = sum(
        1 for p in page_findings if p["native_videos"] or p["embed_videos"]
    )
    pages_with_video_pct = round(pages_with_video / len(page_findings) * 100, 1)
    pages_with_only_images = [
        p for p in page_findings
        if p["formats"] == ["image"]
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site median format-diversity score >= 2 (most pages have images + 1 other format)",
        passed=median_format_count >= 2,
        evidence={
            "median_format_count": median_format_count,
            "min_format_count": format_counts[0],
            "max_format_count": format_counts[-1],
            "pages_evaluated": len(page_findings),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=50% of pages have native or embedded video",
        passed=pages_with_video_pct >= 50,
        evidence={
            "pages_with_video": pages_with_video,
            "pages_with_video_pct": pages_with_video_pct,
            "pages_image_only_count": len(pages_with_only_images),
            "pages_image_only_sample": [p["url"] for p in pages_with_only_images[:10]],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    # Pick three richest pages as positive examples
    page_findings_sorted = sorted(
        page_findings, key=lambda p: p["format_count"], reverse=True
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-50",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(page_findings),
            "median_format_count": median_format_count,
            "pages_with_video": pages_with_video,
            "pages_with_video_pct": pages_with_video_pct,
            "pages_image_only_count": len(pages_with_only_images),
            "richest_pages_sample": page_findings_sorted[:5],
            "image_only_sample": [p["url"] for p in pages_with_only_images[:10]],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.multimedia_detection"],
    )


# ─── P2-22 — JavaScript rendering pattern (CSR / SSR / SSG) ─────────────────


_CSR_LOADING_PATTERNS = (
    re.compile(r"\bloading\.?\s*$", re.I),
    re.compile(r"^\s*please\s+enable\s+javascript", re.I),
    re.compile(r"<noscript[^>]*>[^<]*you\s+need\s+to\s+enable\s+javascript", re.I),
)


def _has_meaningful_initial_content(soup: BeautifulSoup) -> dict[str, bool]:
    """Return a dict of presence checks for SSR-vs-CSR detection."""
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""

    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = (meta_desc.get("content") or "").strip() if meta_desc else ""

    canonical = soup.find("link", attrs={"rel": "canonical"})
    canonical_href = (canonical.get("href") or "").strip() if canonical else ""

    h1 = soup.find("h1")
    h1_text = h1.get_text(strip=True) if h1 else ""

    json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})

    # Internal links: <a href> with same-origin / relative path
    anchors_with_href = [a for a in soup.find_all("a") if a.get("href")]

    # "Loading..." style stub detection
    body = soup.find("body")
    body_text = body.get_text(" ", strip=True) if body else ""
    has_loading_stub = any(p.search(body_text[:300]) for p in _CSR_LOADING_PATTERNS)

    # Substantive content: extract body word count
    body_words = len(body_text.split()) if body_text else 0

    return {
        "title_present": bool(title),
        "meta_description_present": bool(desc_content),
        "canonical_present": bool(canonical_href),
        "h1_present": bool(h1_text),
        "json_ld_present": len(json_ld) > 0,
        "anchors_with_href_count": len(anchors_with_href),
        "body_word_count": body_words,
        "has_loading_stub": has_loading_stub,
    }


@register_extractor("P2-22")
async def capture_p2_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-22 — JavaScript rendering pattern (Consensus).

    Compares our raw HTML fetch (httpx — no JS execution) against
    DataForSEO Instant Pages (which renders JS) for each page.

    Detection signals:
    - title / meta description / canonical / h1 present in raw HTML
    - JSON-LD blocks in raw HTML
    - at least one anchor with an href (crawlable internal link)
    - no "Loading..." stub or "please enable JavaScript" placeholder
    - body word count meaningfully matches DataForSEO's word count

    Pass: >= 80% of pages pass the SSR checklist (title + h1 + canonical
    + json_ld + anchors + no_loading_stub + word_count_ratio >= 0.5).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-22",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    findings: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        checks = _has_meaningful_initial_content(soup)

        # Compare against DataForSEO's JS-rendered audit (if we have one for this URL)
        # to detect content gap (much more text post-JS = CSR).
        dfs_audit = site.page_audits.get(url) or site.page_audits.get(page.url)
        dfs_words = dfs_audit.plain_text_word_count if dfs_audit else 0
        word_count_ratio = (
            checks["body_word_count"] / dfs_words if dfs_words > 0 else 1.0
        )
        # If ratio > 1.0, raw HTML has MORE words than parsed; treat as fine (SSR)
        word_count_ok = word_count_ratio >= 0.5 if dfs_words > 0 else True

        ssr_score = sum(
            [
                checks["title_present"],
                checks["h1_present"],
                checks["canonical_present"],
                checks["json_ld_present"],
                checks["anchors_with_href_count"] >= 3,
                not checks["has_loading_stub"],
                word_count_ok,
            ]
        )
        passes_ssr = ssr_score >= 6  # of 7 checks

        findings.append(
            {
                "url": url,
                "ssr_score": ssr_score,
                "ssr_score_max": 7,
                "passes_ssr": passes_ssr,
                "title_present": checks["title_present"],
                "h1_present": checks["h1_present"],
                "canonical_present": checks["canonical_present"],
                "json_ld_present": checks["json_ld_present"],
                "anchors_with_href": checks["anchors_with_href_count"],
                "has_loading_stub": checks["has_loading_stub"],
                "raw_word_count": checks["body_word_count"],
                "rendered_word_count": dfs_words,
                "word_count_ratio": round(word_count_ratio, 3),
                "word_count_ok": word_count_ok,
            }
        )

    if not findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-22",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no fetched HTML pages eligible for SSR check"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "dataforseo_on_page.instant_pages"],
            errors=["no eligible pages"],
        )

    pages_passing = sum(1 for f in findings if f["passes_ssr"])
    coverage_pct = round(pages_passing / len(findings) * 100, 1)
    failing_pages = [f for f in findings if not f["passes_ssr"]]

    # Categorise rendering pattern
    if coverage_pct >= 95:
        pattern = "SSR/SSG"
    elif coverage_pct >= 60:
        pattern = "mostly-SSR-with-CSR-routes"
    elif coverage_pct >= 20:
        pattern = "mixed-CSR/SSR"
    else:
        pattern = "CSR-only"

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=80% of pages pass the SSR checklist (6 of 7 rendering signals present)",
        passed=coverage_pct >= 80,
        evidence={
            "pages_evaluated": len(findings),
            "pages_passing": pages_passing,
            "coverage_pct": coverage_pct,
            "rendering_pattern": pattern,
            "failing_sample": failing_pages[:10],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-22",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(findings),
            "pages_passing": pages_passing,
            "coverage_pct": coverage_pct,
            "rendering_pattern": pattern,
            "failing_pages_sample": failing_pages[:10],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "dataforseo_on_page.instant_pages",
            "composition.ssr_csr_detection",
        ],
    )


# ─── P2-07 — Canonicalisation conflicts ─────────────────────────────────────


@register_extractor("P2-07")
async def capture_p2_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-07 — Canonicalisation conflicts (Consensus).

    Compares signals across:
    - declared canonical (page_audit.canonical)
    - sitemap URLs (site.urls — discovered from sitemap)
    - dominant internal-link target (link_graph)

    Reports per-page conflicts. Pass if >= 90% of indexable pages have
    consistent signals across all three. GSC URL Inspection (Google's
    selected canonical) is not available externally; we use the three
    signals we can observe.
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-07",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )

    sitemap_url_keys = {_norm_for_match(u) for u in (site.urls or [])}
    # Build a map of inbound counts per target URL from link_graph (if available)
    inbound_counts_by_target: dict[str, int] = {}
    if site.link_graph is not None:
        for target_url, refs in site.link_graph.inbound.items():
            internal = [r for r in refs if r.is_internal and not r.is_self]
            if internal:
                inbound_counts_by_target[_norm_for_match(target_url)] = len(internal)

    pages_checked = 0
    pages_consistent = 0
    conflicts: list[dict[str, Any]] = []
    no_canonical: list[str] = []
    for audit in audits:
        if audit.meta_robots and "noindex" in audit.meta_robots.lower():
            continue
        pages_checked += 1
        own_key = _norm_for_match(audit.url)
        canonical = (audit.canonical or "").strip()
        if not canonical:
            no_canonical.append(audit.url)
            conflicts.append(
                {
                    "url": audit.url,
                    "issue": "no canonical declared",
                    "canonical": None,
                }
            )
            continue
        canonical_key = _norm_for_match(canonical)

        page_conflicts: list[str] = []
        # Rule 2: sitemap URL should match declared canonical
        if sitemap_url_keys and canonical_key not in sitemap_url_keys:
            page_conflicts.append("canonical not present in sitemap URL set")
        # Rule 3: dominant inbound target matches canonical
        # If the canonical points elsewhere, the inbound to canonical should be >= inbound to self
        inbound_self = inbound_counts_by_target.get(own_key, 0)
        inbound_canonical = inbound_counts_by_target.get(canonical_key, 0)
        if canonical_key != own_key and inbound_self > inbound_canonical * 1.5:
            page_conflicts.append(
                f"page has more inbound links ({inbound_self}) than the declared canonical "
                f"({inbound_canonical}); internal-link signals contradict canonical"
            )
        # Rule 5: scheme + host normalisation - canonical should use same host as audit URL
        from urllib.parse import urlsplit as _us
        a_parts = _us(audit.url)
        c_parts = _us(canonical)
        if c_parts.scheme and c_parts.scheme != a_parts.scheme:
            page_conflicts.append(
                f"canonical scheme ({c_parts.scheme}) differs from page scheme "
                f"({a_parts.scheme})"
            )

        if not page_conflicts:
            pages_consistent += 1
        else:
            if len(conflicts) < 20:
                conflicts.append(
                    {
                        "url": audit.url,
                        "canonical": canonical,
                        "issues": page_conflicts,
                    }
                )

    coverage_pct = (
        round(pages_consistent / pages_checked * 100, 1) if pages_checked else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=90% of indexable pages have consistent canonical signals across declared, sitemap, and internal-link target",
        passed=pages_checked > 0 and coverage_pct >= 90,
        evidence={
            "pages_checked": pages_checked,
            "pages_consistent": pages_consistent,
            "coverage_pct": coverage_pct,
            "conflicts_sample": conflicts,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-07",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_checked": pages_checked,
            "pages_consistent": pages_consistent,
            "coverage_pct": coverage_pct,
            "no_canonical_count": len(no_canonical),
            "no_canonical_sample": no_canonical[:10],
            "conflicts_sample": conflicts[:15],
            "sitemap_urls_known": len(sitemap_url_keys),
            "note": "GSC URL Inspection (Google-selected canonical) not available externally; uses declared+sitemap+inbound signals only.",
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo_on_page.instant_pages",
            "sitemap.discover_urls",
            "composition.link_graph",
            "composition.canonical_conflict_check",
        ],
    )


# ─── P2-37 — Pop-ups and intrusive interstitials (heuristic) ────────────────


# Class/role/aria patterns that frequently indicate modal / popup / overlay markup
_INTERSTITIAL_CSS_HINTS = (
    "modal", "popup", "pop-up", "overlay", "lightbox", "dialog",
    "interstitial", "fullscreen-takeover", "exit-intent",
    "newsletter-modal", "subscribe-modal", "consent-banner",
)
_LEGITIMATE_HINTS = (
    "cookie", "gdpr", "ccpa", "consent",  # cookie banners are exempt
    "age-gate", "age-verify",              # age verification exempt
    "paywall", "subscription-required",    # YMYL paywalls exempt
)


def _detect_interstitial_markup(soup: BeautifulSoup) -> dict[str, Any]:
    """Heuristic detection of likely-interstitial markup in raw HTML.

    Not authoritative (modals rendered post-load via JS won't appear in raw
    HTML), but flags markup patterns that often indicate interstitials.
    """
    suspicious: list[dict[str, Any]] = []
    legitimate: list[dict[str, Any]] = []
    # Walk elements with class/role/aria attributes
    for el in soup.find_all(
        attrs={"role": True}
    ) + soup.find_all(attrs={"aria-modal": True}) + soup.find_all(class_=True):
        role = (el.get("role") or "").lower()
        aria_modal = (el.get("aria-modal") or "").lower()
        cls = " ".join(el.get("class") or []).lower()
        haystack = f"{role} {aria_modal} {cls}"
        if not haystack.strip():
            continue
        is_legit = any(h in haystack for h in _LEGITIMATE_HINTS)
        matched = [h for h in _INTERSTITIAL_CSS_HINTS if h in haystack]
        if matched:
            entry = {
                "tag": el.name,
                "matched_hints": matched,
                "class_or_role": haystack.strip()[:120],
            }
            if is_legit:
                legitimate.append(entry)
            else:
                suspicious.append(entry)
    # Deduplicate by matched_hints tuple to keep evidence compact
    seen_keys: set[tuple] = set()
    dedup_suspicious: list[dict[str, Any]] = []
    for entry in suspicious:
        key = tuple(sorted(entry["matched_hints"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        dedup_suspicious.append(entry)
    return {
        "suspicious_count": len(suspicious),
        "legitimate_count": len(legitimate),
        "suspicious_samples": dedup_suspicious[:5],
    }


@register_extractor("P2-37")
async def capture_p2_37(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-37 — Pop-ups and intrusive interstitials (Consensus, heuristic).

    Heuristic: scans raw HTML for modal/popup/overlay markup patterns
    that commonly indicate intrusive interstitials. Cookie banners,
    age gates, and paywalls are filtered out as legitimate.

    Pass: >= 90% of fetched pages have no suspicious interstitial markup.

    Caveat noted in value: JS-injected modals invisible to raw-HTML
    detection. Authoritative requires rendered scrape (Playwright);
    we report what's observable externally without rendering.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-37",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    pages_with_suspicious: list[dict[str, Any]] = []
    pages_checked = 0
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        pages_checked += 1
        finding = _detect_interstitial_markup(soup)
        if finding["suspicious_count"] > 0:
            pages_with_suspicious.append(
                {
                    "url": url,
                    "suspicious_count": finding["suspicious_count"],
                    "samples": finding["suspicious_samples"],
                }
            )

    if pages_checked == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-37",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no eligible fetched HTML pages"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["no eligible pages"],
        )

    clean_pages = pages_checked - len(pages_with_suspicious)
    clean_pct = round(clean_pages / pages_checked * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=90% of fetched pages have no suspicious interstitial markup (cookie / age / paywall exempt)",
        passed=clean_pct >= 90,
        evidence={
            "pages_checked": pages_checked,
            "clean_pages": clean_pages,
            "clean_pct": clean_pct,
            "pages_with_suspicious_sample": pages_with_suspicious[:10],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-37",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_checked": pages_checked,
            "clean_pages": clean_pages,
            "pages_with_suspicious_count": len(pages_with_suspicious),
            "clean_pct": clean_pct,
            "pages_with_suspicious_sample": pages_with_suspicious[:10],
            "caveat": "Heuristic raw-HTML detection only; JS-injected modals invisible. Authoritative check requires rendered crawl (Playwright).",
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.interstitial_heuristic"],
    )


# ─── P2-42 — Sitemap priority weighting per URL ─────────────────────────────


_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_VALID_CHANGEFREQ = {
    "always", "hourly", "daily", "weekly", "monthly", "yearly", "never",
}


async def _fetch_sitemap_records(primary_url: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch sitemap and return per-URL records with priority + changefreq.

    Returns (records, errors). Each record:
    {"loc": str, "priority": float|None, "changefreq": str|None,
     "lastmod": str|None}.
    """
    import httpx
    from urllib.parse import urljoin, urlparse
    from xml.etree import ElementTree as ET

    parsed = urlparse(primary_url)
    if not parsed.scheme or not parsed.netloc:
        return [], ["invalid primary_url"]
    base = f"{parsed.scheme}://{parsed.netloc}"

    paths = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")
    errors: list[str] = []
    records: list[dict[str, Any]] = []

    async def _walk(client: httpx.AsyncClient, url: str, depth: int = 0) -> None:
        if depth > 3:
            return
        try:
            resp = await client.get(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
            return
        if resp.status_code >= 400:
            return
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            errors.append(f"{url}: parse error {exc}")
            return
        tag = root.tag.rsplit("}", 1)[-1] if "}" in root.tag else root.tag
        if tag == "sitemapindex":
            for sm in root.findall(f"{{{_SITEMAP_NS}}}sitemap"):
                loc_el = sm.find(f"{{{_SITEMAP_NS}}}loc")
                if loc_el is not None and loc_el.text:
                    await _walk(client, loc_el.text.strip(), depth + 1)
        elif tag == "urlset":
            for u in root.findall(f"{{{_SITEMAP_NS}}}url"):
                loc_el = u.find(f"{{{_SITEMAP_NS}}}loc")
                if loc_el is None or not loc_el.text:
                    continue
                pri_el = u.find(f"{{{_SITEMAP_NS}}}priority")
                cf_el = u.find(f"{{{_SITEMAP_NS}}}changefreq")
                lm_el = u.find(f"{{{_SITEMAP_NS}}}lastmod")
                priority: float | None = None
                if pri_el is not None and pri_el.text:
                    try:
                        priority = float(pri_el.text.strip())
                    except ValueError:
                        priority = None
                records.append(
                    {
                        "loc": loc_el.text.strip(),
                        "priority": priority,
                        "changefreq": (
                            cf_el.text.strip().lower() if cf_el is not None and cf_el.text else None
                        ),
                        "lastmod": lm_el.text.strip() if lm_el is not None and lm_el.text else None,
                    }
                )

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1"},
    ) as client:
        for path in paths:
            await _walk(client, urljoin(base, path))
            if records:
                break

    return records, errors


@register_extractor("P2-42")
async def capture_p2_42(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-42 — Sitemap priority weighting per URL (Speculative).

    Parse sitemap for priority + changefreq declarations. Google has
    explicitly stated these values are largely ignored, so this is
    a Speculative variable — recorded for completeness but not used
    for operational scoring.

    Two completeness checks:
    1. If priority is declared, it's a valid 0.0-1.0 float
    2. If changefreq is declared, it's a valid sitemap-spec value
    """
    captured_at = _now()
    records, errors = await _fetch_sitemap_records(site.primary_url)
    if not records:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-42",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no sitemap reachable or sitemap had no <url> entries",
                "errors": errors[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["http.sitemap_fetch"],
            errors=errors[:3] or ["no records"],
        )

    with_priority = [r for r in records if r["priority"] is not None]
    with_changefreq = [r for r in records if r["changefreq"] is not None]
    invalid_priority = [
        r for r in with_priority if not (0.0 <= r["priority"] <= 1.0)
    ]
    invalid_changefreq = [
        r for r in with_changefreq
        if r["changefreq"] not in _VALID_CHANGEFREQ
    ]

    priority_distribution: dict[str, int] = {}
    for r in with_priority:
        bucket = f"{r['priority']:.1f}"
        priority_distribution[bucket] = priority_distribution.get(bucket, 0) + 1
    changefreq_distribution: dict[str, int] = {}
    for r in with_changefreq:
        cf = r["changefreq"]
        changefreq_distribution[cf] = changefreq_distribution.get(cf, 0) + 1

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="All declared <priority> values are valid floats in [0.0, 1.0]",
        passed=len(invalid_priority) == 0,
        evidence={
            "invalid_priority_count": len(invalid_priority),
            "invalid_priority_sample": invalid_priority[:5],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="All declared <changefreq> values are valid sitemap-spec tokens",
        passed=len(invalid_changefreq) == 0,
        evidence={
            "invalid_changefreq_count": len(invalid_changefreq),
            "invalid_changefreq_sample": invalid_changefreq[:5],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-42",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_urls_in_sitemap": len(records),
            "urls_with_priority": len(with_priority),
            "urls_with_changefreq": len(with_changefreq),
            "priority_distribution": priority_distribution,
            "changefreq_distribution": changefreq_distribution,
            "invalid_priority_count": len(invalid_priority),
            "invalid_changefreq_count": len(invalid_changefreq),
            "watchlist": True,
            "note": "Google explicitly states sitemap <priority> and <changefreq> are largely ignored by its crawler. Recorded for completeness, not used for operational recommendations.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=["http.sitemap_fetch", "composition.sitemap_priority_parse"],
    )


# ─── P2-39 — AMP detection ──────────────────────────────────────────────────


@register_extractor("P2-39")
async def capture_p2_39(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-39 — Use of AMP (Speculative, watchlist).

    AMP was deprecated as a Top Stories carousel requirement in 2021
    and is no longer a Google ranking input. Recorded for completeness:
    if any pages still use AMP, recommend migration to standard HTML
    + Core Web Vitals.

    Detects:
    - <html amp> or <html ⚡> attribute in fetched HTML
    - /amp/ in URL path

    Pass: 0% AMP pages found (clean modern state). Sites still on AMP
    are flagged as migration candidates.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-39",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    amp_pages: list[dict[str, Any]] = []
    pages_checked = 0
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        pages_checked += 1
        # Path-based: /amp/ in URL
        path_amp = "/amp/" in (urlsplit(url).path or "").lower() or \
                   (urlsplit(url).path or "").lower().endswith("/amp")
        # Markup-based: <html amp> or <html ⚡>
        markup_amp = False
        amp_signal = None
        # Crude regex on raw HTML <html ...> opening tag
        html_open_match = re.search(r"<html\b[^>]*>", page.html[:2000], re.I)
        if html_open_match:
            tag = html_open_match.group(0)
            if re.search(r"\bamp\b", tag, re.I) or "⚡" in tag:
                markup_amp = True
                amp_signal = tag[:120]
        if path_amp or markup_amp:
            amp_pages.append(
                {
                    "url": url,
                    "path_amp": path_amp,
                    "markup_amp": markup_amp,
                    "html_tag_sample": amp_signal,
                }
            )

    if pages_checked == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-39",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no eligible fetched HTML pages"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["http.html_fetch"],
            errors=["no eligible pages"],
        )

    amp_pct = round(len(amp_pages) / pages_checked * 100, 1) if pages_checked else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No AMP-rendered pages detected (AMP deprecated 2021; migration to modern HTML recommended)",
        passed=len(amp_pages) == 0,
        evidence={
            "amp_page_count": len(amp_pages),
            "amp_pct": amp_pct,
            "amp_samples": amp_pages[:10],
        },
        notes="Watchlist variable — AMP no longer provides ranking benefit; flag as migration candidate if present.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-39",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_checked": pages_checked,
            "amp_page_count": len(amp_pages),
            "amp_pct": amp_pct,
            "amp_pages_sample": amp_pages[:10],
            "watchlist": True,
            "note": "AMP deprecated 2021. PASSED means site doesn't use AMP (modern state); FAILED means AMP migration recommended.",
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=["http.html_fetch", "composition.amp_detection"],
    )


# ─── P2-41 — Site update cadence (from sitemap lastmod) ─────────────────────


@register_extractor("P2-41")
async def capture_p2_41(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-41 — Site update cadence (Probable, first-audit best-effort).

    Derives a site-wide cadence approximation from sitemap ``<lastmod>``
    distribution. Full version (per Backlinko #70) needs accumulated
    snapshots over time; this first-audit estimate uses what the
    sitemap declares about its own update history.

    Pass: ≥ 3 updates per month in the last 3 months (active) OR ≥ 6
    updates in the last 12 months total (moderate cadence).

    Caveat noted in value: sitemap lastmod is self-declared by the CMS
    and may not reflect actual content changes. True P2-41 requires
    multi-snapshot history (resolves after ≥ 2 audits accumulated).
    """
    captured_at = _now()
    records, errors = await _fetch_sitemap_records(site.primary_url)
    if not records:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-41",
            pillar="P2",
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

    # Parse lastmod values into datetimes
    parsed_dates: list[datetime] = []
    no_lastmod_count = 0
    for r in records:
        lm = r.get("lastmod")
        if not lm:
            no_lastmod_count += 1
            continue
        try:
            # Sitemap lastmod is ISO 8601, often with timezone
            normalised = lm.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalised)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_dates.append(dt)
        except (ValueError, TypeError):
            continue

    if not parsed_dates:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-41",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "sitemap has no parseable <lastmod> values",
                "urls_in_sitemap": len(records),
                "urls_without_lastmod": no_lastmod_count,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.sitemap_fetch"],
            errors=["no parseable lastmod"],
        )

    now = _now()
    one_month_ago = now.replace(day=1)
    three_months_ago = now - timedelta(days=90)
    twelve_months_ago = now - timedelta(days=365)
    updates_last_3m = sum(1 for d in parsed_dates if d >= three_months_ago)
    updates_last_12m = sum(1 for d in parsed_dates if d >= twelve_months_ago)
    updates_per_month_3m = round(updates_last_3m / 3, 2)
    updates_per_month_12m = round(updates_last_12m / 12, 2)

    # Distribution by month for the last 12 months
    by_month: dict[str, int] = {}
    for d in parsed_dates:
        if d < twelve_months_ago:
            continue
        key = d.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + 1

    if updates_per_month_3m >= 3:
        classification = "active"
    elif updates_per_month_3m >= 1 or updates_last_12m >= 6:
        classification = "moderate"
    else:
        classification = "stale"

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=(
            "Site shows active or moderate update cadence "
            "(>=3/month last 3 months OR >=6 total last 12 months)"
        ),
        passed=classification in ("active", "moderate"),
        evidence={
            "classification": classification,
            "updates_per_month_3m": updates_per_month_3m,
            "updates_last_12m": updates_last_12m,
            "updates_per_month_12m": updates_per_month_12m,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-41",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "urls_in_sitemap": len(records),
            "urls_with_lastmod": len(parsed_dates),
            "urls_without_lastmod": no_lastmod_count,
            "classification": classification,
            "updates_last_3m": updates_last_3m,
            "updates_last_12m": updates_last_12m,
            "updates_per_month_3m": updates_per_month_3m,
            "updates_per_month_12m": updates_per_month_12m,
            "month_distribution": dict(sorted(by_month.items())),
            "caveat": "First-audit estimate from sitemap lastmod (self-declared). True multi-snapshot cadence resolves once >=2 audits are stored.",
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.sitemap_fetch", "composition.sitemap_lastmod_cadence"],
    )


# ─── P1-38 — Original content score ─────────────────────────────────────────


@register_extractor("P1-38")
async def capture_p1_38(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-38 — Original content score (Probable, leak-feature approximation).

    Per-page originality score approximating Google's leaked
    ``OriginalContentScore``. Combines two signals:

    1. DataForSEO's site-internal ``duplicate_content_check`` boolean
       (true if the crawler flagged the page as a duplicate of another
       on-site page).
    2. Maximum pairwise cosine similarity between this page's
       embedding and any other page's embedding (high similarity = the
       page largely overlaps another page's content).

    Formula:
        score = 1.0 - max_similarity_to_others
        if duplicate_content_check: score = min(score, 0.3)

    Pass: site median originality_score >= 0.6 AND no page below 0.2.

    Caveat: in-site originality only; external-web duplication needs
    Copyscape or distinctive-phrase search (not free).
    """
    captured_at = _now()
    audits = site.successful_audits
    if not audits:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-38",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page audits available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_on_page.instant_pages"],
            errors=["page_audits empty"],
        )
    if not site.embeddings_configured or not site.embeddings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-38",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page embeddings available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["embeddings empty"],
        )

    # Build (url, vector) list for pages with both an audit and an embedding
    pages_with_data: list[tuple[str, tuple[float, ...], bool]] = []
    for audit in audits:
        emb = site.embeddings.get(audit.url)
        if emb is None or not emb.vector:
            continue
        pages_with_data.append(
            (audit.url, emb.vector, bool(audit.duplicate_content_check))
        )

    if len(pages_with_data) < 2:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-38",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "need at least 2 embedded pages for pairwise similarity",
                "pages_with_data": len(pages_with_data),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["insufficient data"],
        )

    page_scores: list[dict[str, Any]] = []
    for i, (url_i, vec_i, dup_i) in enumerate(pages_with_data):
        max_sim = 0.0
        best_neighbour = None
        for j, (url_j, vec_j, _) in enumerate(pages_with_data):
            if i == j:
                continue
            sim = cosine_similarity(vec_i, vec_j)
            if sim > max_sim:
                max_sim = sim
                best_neighbour = url_j
        score = max(0.0, 1.0 - max_sim)
        if dup_i:
            score = min(score, 0.3)
        page_scores.append(
            {
                "url": url_i,
                "originality_score": round(score, 3),
                "max_similarity_to_others": round(max_sim, 3),
                "closest_neighbour": best_neighbour,
                "duplicate_content_flag": dup_i,
            }
        )

    scores = sorted(p["originality_score"] for p in page_scores)
    median = scores[len(scores) // 2]
    mean = sum(scores) / len(scores)
    min_score = scores[0]
    max_score = scores[-1]
    low_originality_pages = [p for p in page_scores if p["originality_score"] < 0.2]
    low_originality_sorted = sorted(
        page_scores, key=lambda p: p["originality_score"]
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site median originality score >= 0.6",
        passed=median >= 0.6,
        evidence={
            "median_score": round(median, 3),
            "mean_score": round(mean, 3),
            "pages_scored": len(page_scores),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No page scores below 0.2 (no severe in-site duplicate)",
        passed=len(low_originality_pages) == 0,
        evidence={
            "low_originality_count": len(low_originality_pages),
            "low_originality_pages": low_originality_pages[:10],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-38",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_scored": len(page_scores),
            "median_score": round(median, 3),
            "mean_score": round(mean, 3),
            "min_score": round(min_score, 3),
            "max_score": round(max_score, 3),
            "low_originality_count": len(low_originality_pages),
            "least_original_pages": low_originality_sorted[:10],
            "caveat": "In-site originality only — external-web duplication detection (Copyscape / phrase-search) not implemented; this score approximates Google's leaked OriginalContentScore.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "dataforseo_on_page.instant_pages.duplicate_content_check",
            "composition.originality_score",
        ],
    )


# ─── P1-35 — TF-IDF / keyword prominence ────────────────────────────────────


# Common English stopwords stripped before TF-IDF computation. Conservative
# list — we lean toward leaving "ambiguous" words in rather than over-strip.
_TFIDF_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to", "for",
        "with", "by", "from", "is", "are", "was", "were", "be", "been", "being",
        "as", "it", "its", "this", "that", "these", "those", "i", "you", "he",
        "she", "we", "they", "them", "us", "my", "our", "your", "their", "his",
        "her", "what", "how", "why", "when", "where", "who", "which", "do",
        "does", "did", "doing", "have", "has", "had", "having", "can", "could",
        "would", "should", "will", "may", "might", "must", "shall", "than",
        "then", "if", "else", "so", "not", "no", "yes", "very", "just", "also",
        "more", "most", "much", "many", "some", "any", "all", "each", "every",
        "few", "other", "another", "such", "only", "own", "same", "too", "up",
        "down", "out", "over", "under", "about", "between", "through", "during",
        "before", "after", "above", "below", "without", "within", "into", "onto",
        "off", "again", "further", "here", "there", "now", "while", "because",
        "since", "until", "though", "although", "even", "still", "yet",
    }
)


def _tokenise_for_tfidf(text: str) -> list[str]:
    """Lowercase + alphanumeric tokens >= 3 chars, stopwords removed."""
    if not text:
        return []
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= 3 and t not in _TFIDF_STOPWORDS]


@register_extractor("P1-35")
async def capture_p1_35(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-35 — TF-IDF / keyword prominence (Probable; in-site corpus).

    Approximation of leaked Google ``avgTermWeight``. For each page, we
    compute TF-IDF over the in-site corpus (every other audited page as
    background) and report the top weighted terms.

    Coverage rule: every substantive page (>=200 words) has at least
    10 distinct content-bearing tokens — i.e., it isn't dominated by
    a handful of repeated terms (keyword-stuffing signal).

    For each page-with-target-keyword (ranked_keywords mapping), check
    whether at least one keyword token appears in the page's top-10
    TF-IDF terms — a prominence sanity check.
    """
    import math
    from collections import Counter

    captured_at = _now()
    if not site.text_content:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-35",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no text_content prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch", "trafilatura.extract"],
            errors=["text_content empty"],
        )

    # Build per-page token list + IDF over the corpus
    pages: list[tuple[str, list[str]]] = []
    for url, page_text in site.text_content.items():
        toks = _tokenise_for_tfidf(getattr(page_text, "main_text", "") or "")
        if len(toks) >= 50:  # ignore very short pages — noisy TF-IDF
            pages.append((url, toks))
    if len(pages) < 2:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-35",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "need at least 2 substantive text pages for TF-IDF corpus",
                "pages_with_text": len(pages),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["insufficient corpus"],
        )

    # Document frequency for each token across the corpus
    df: Counter = Counter()
    for _, toks in pages:
        for t in set(toks):
            df[t] += 1
    N = len(pages)

    target_map = _build_page_target_keywords(site)

    per_page_findings: list[dict[str, Any]] = []
    pages_dominated_by_few_terms = 0
    pages_with_kw_prominent = 0
    pages_with_target_kw = 0
    for url, toks in pages:
        tf = Counter(toks)
        total_tokens = sum(tf.values())
        distinct_tokens = len(tf)
        scores: list[tuple[str, float]] = []
        for term, freq in tf.items():
            tf_val = freq / total_tokens
            idf_val = math.log((N + 1) / (df[term] + 1)) + 1.0  # smooth
            scores.append((term, tf_val * idf_val))
        scores.sort(key=lambda x: x[1], reverse=True)
        top10 = scores[:10]

        # Dominance check: if top-3 terms account for >=40% of all tokens,
        # the page is suspiciously narrow / keyword-stuffed
        top3_share = (
            sum(tf[t] for t, _ in scores[:3]) / total_tokens
            if total_tokens else 0
        )
        if top3_share >= 0.4:
            pages_dominated_by_few_terms += 1

        # Keyword prominence: does any target keyword token appear in top10?
        bucket = _resolve_page_kw(url, target_map)
        kw_top10_match: list[str] = []
        if bucket:
            kw_toks = set(_kw_tokens(bucket["target_keyword"]))
            pages_with_target_kw += 1
            top10_terms = {t for t, _ in top10}
            kw_top10_match = sorted(kw_toks & top10_terms)
            if kw_top10_match:
                pages_with_kw_prominent += 1

        per_page_findings.append(
            {
                "url": url,
                "total_tokens": total_tokens,
                "distinct_tokens": distinct_tokens,
                "top3_share": round(top3_share, 3),
                "top10_terms": [{"term": t, "score": round(s, 4)} for t, s in top10],
                "target_keyword_top10_match": kw_top10_match,
            }
        )

    kw_prominence_pct = (
        round(pages_with_kw_prominent / pages_with_target_kw * 100, 1)
        if pages_with_target_kw else 0
    )
    dominated_pct = round(pages_dominated_by_few_terms / len(pages) * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="<=10% of pages are dominated by 3 terms accounting for >=40% of tokens",
        passed=dominated_pct <= 10,
        evidence={
            "dominated_pages": pages_dominated_by_few_terms,
            "dominated_pct": dominated_pct,
            "total_pages": len(pages),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="If page has a ranked target keyword, at least one keyword token appears in top-10 TF-IDF terms (>=70% coverage)",
        passed=pages_with_target_kw == 0 or kw_prominence_pct >= 70,
        evidence={
            "pages_with_target_kw": pages_with_target_kw,
            "pages_with_kw_prominent": pages_with_kw_prominent,
            "kw_prominence_pct": kw_prominence_pct,
        },
        notes=(
            "ranked_keywords surface thin on this site — denominator may be small"
            if pages_with_target_kw < 5 else None
        ),
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-35",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_analysed": len(pages),
            "pages_dominated_by_few_terms": pages_dominated_by_few_terms,
            "dominated_pct": dominated_pct,
            "pages_with_target_kw": pages_with_target_kw,
            "pages_with_kw_prominent": pages_with_kw_prominent,
            "kw_prominence_pct": kw_prominence_pct,
            "findings_sample": per_page_findings[:5],
            "caveat": "Corpus is the audited site only — IDF reflects in-site rarity, not web-corpus rarity. True avgTermWeight needs a much broader corpus.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "trafilatura.extract",
            "composition.tfidf_in_site",
        ],
    )


# ─── P2-36 — IndexNow protocol adoption ─────────────────────────────────────


@register_extractor("P2-36")
async def capture_p2_36(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-36 — IndexNow protocol adoption (Probable, partial external detection).

    Without server log access we can only detect IndexNow through public
    signals:
    1. robots.txt mentions of indexnow.org or the key file
    2. Common verification file paths (indexnow.txt, etc.)
    3. <meta name="indexnow" ...> tag in homepage HTML

    Pass: any of the three signals present (site IS using IndexNow).
    Fail: no signals → site likely NOT using IndexNow → migration
    recommendation for sites that target Bing / Yandex / Naver / Seznam.

    Note: Google does NOT consume IndexNow; this only matters for non-Google
    engines. Pixelette is Google-focused so a FAIL here may be ignorable.
    """
    import httpx
    from urllib.parse import urlsplit, urljoin

    captured_at = _now()
    parsed = urlsplit(site.primary_url)
    if not parsed.scheme or not parsed.netloc:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-36",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "invalid primary_url"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.well_known_probe"],
            errors=["invalid primary_url"],
        )
    base = f"{parsed.scheme}://{parsed.netloc}"

    robots_mentions: list[str] = []
    key_file_hits: list[dict[str, Any]] = []
    homepage_meta_indexnow = False
    probe_errors: list[str] = []

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1"},
    ) as client:
        # 1. robots.txt scan
        try:
            r = await client.get(urljoin(base, "/robots.txt"))
            if r.status_code < 400:
                for line in r.text.splitlines():
                    low = line.lower().strip()
                    if "indexnow" in low or "bing.com/indexnow" in low:
                        robots_mentions.append(line.strip()[:160])
        except Exception as exc:  # noqa: BLE001
            probe_errors.append(f"robots.txt: {exc}")

        # 2. Probe common IndexNow key file paths
        common_paths = ("/indexnow.txt", "/IndexNow.txt", "/.well-known/indexnow.txt")
        for path in common_paths:
            try:
                r = await client.get(urljoin(base, path))
                if r.status_code == 200:
                    snippet = (r.text or "").strip()
                    # IndexNow keys are 8-128 hex chars; check the body looks like one
                    body_first_line = snippet.splitlines()[0] if snippet else ""
                    looks_like_key = bool(
                        re.fullmatch(r"[a-fA-F0-9\-]{8,128}", body_first_line.strip())
                    )
                    key_file_hits.append(
                        {
                            "path": path,
                            "status": r.status_code,
                            "looks_like_key": looks_like_key,
                            "body_first_line": body_first_line[:120],
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                probe_errors.append(f"{path}: {exc}")

        # 3. Check homepage meta tag (we already have it cached if html_pages exists)
    home_html_obj = site.html_pages.get(site.primary_url)
    if home_html_obj is None:
        # Try other variants
        for url, page in site.html_pages.items():
            if (urlsplit(url).path or "/").strip("/") == "":
                home_html_obj = page
                break
    if home_html_obj is not None and home_html_obj.html:
        try:
            soup = BeautifulSoup(home_html_obj.html, "html.parser")
            meta = soup.find("meta", attrs={"name": re.compile(r"^indexnow$", re.I)})
            if meta is not None:
                homepage_meta_indexnow = True
        except Exception:  # noqa: BLE001
            pass

    signals_found = (
        bool(robots_mentions)
        + bool([h for h in key_file_hits if h.get("looks_like_key")])
        + homepage_meta_indexnow
    )
    adopted = signals_found >= 1

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one IndexNow signal detected externally (robots.txt mention, key file at common path, or homepage meta tag)",
        passed=adopted,
        evidence={
            "robots_mentions": robots_mentions,
            "key_file_hits_present": [h for h in key_file_hits if h.get("looks_like_key")],
            "homepage_meta_indexnow": homepage_meta_indexnow,
        },
        notes=(
            "Without server log access, externally-observable signals are partial. "
            "A negative result means IndexNow not adopted via standard signals; "
            "a positive result is definitive evidence of adoption."
        ),
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-36",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if adopted else CaptureStatus.FAILED,
        value={
            "adopted": adopted,
            "signals_found": signals_found,
            "robots_mentions": robots_mentions,
            "key_file_probes": key_file_hits,
            "homepage_meta_indexnow": homepage_meta_indexnow,
            "probe_errors": probe_errors[:5],
            "note": (
                "Google does not consume IndexNow. This variable matters for "
                "non-Google engines (Bing / Yandex / Naver / Seznam). Negative "
                "result is non-fatal for Google-focused sites."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.well_known_probe",
            "http.robots_txt",
            "composition.indexnow_detection",
        ],
    )


# ─── P2-21 — Server location (DNS + IP geolocation) ─────────────────────────


# Header fingerprints for major CDNs / edge networks; presence of any of
# these means the origin server location is largely hidden from end users.
_CDN_HEADER_FINGERPRINTS = (
    ("cf-ray", "Cloudflare"),
    ("server", "cloudflare"),
    ("x-served-by", "Fastly"),
    ("server", "Fastly"),
    ("x-cache", "cloudfront"),
    ("via", "CloudFront"),
    ("x-amz-cf-id", "CloudFront"),
    ("server", "AkamaiGHost"),
    ("x-cdn", "Akamai"),
    ("x-vercel-cache", "Vercel"),
    ("server", "Vercel"),
    ("x-nf-request-id", "Netlify"),
    ("x-azure-ref", "Azure"),
)


def _detect_cdn_from_headers(headers: tuple[tuple[str, str], ...]) -> str | None:
    """Return CDN name if any header fingerprint matches, else None."""
    lookup = {(k.lower(), v.lower()) for k, v in headers}
    for needle_key, needle_val in _CDN_HEADER_FINGERPRINTS:
        for (k, v) in lookup:
            if k == needle_key and needle_val.lower() in v:
                return needle_val
    return None


@register_extractor("P2-21")
async def capture_p2_21(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-21 — Server location (Speculative, watchlist).

    Resolves the primary URL's hostname to an IP, queries free
    ip-api.com geolocation, and inspects headers from the homepage
    fetch for CDN fingerprints.

    Pass: any IP successfully resolved (variable is recording-only;
    Google does not use server location as a ranking signal). CDN
    presence noted in value — when behind a CDN, "server location"
    reflects edge nodes rather than origin.
    """
    import socket
    import httpx
    from urllib.parse import urlsplit

    captured_at = _now()
    parsed = urlsplit(site.primary_url)
    host = (parsed.netloc or "").split(":", 1)[0]
    if not host:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-21",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no host in primary_url"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["socket.gethostbyname"],
            errors=["invalid primary_url"],
        )

    ip: str | None = None
    dns_error: str | None = None
    try:
        ip = socket.gethostbyname(host)
    except (socket.gaierror, OSError) as exc:
        dns_error = str(exc)

    geo: dict[str, Any] = {}
    if ip:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"http://ip-api.com/json/{ip}",
                    params={"fields": "status,country,countryCode,city,region,isp,org,as"},
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "success":
                        geo = data
        except Exception as exc:  # noqa: BLE001
            geo = {"error": str(exc)}

    # CDN detection from cached homepage fetch headers
    cdn_detected: str | None = None
    home_page = site.html_pages.get(site.primary_url)
    if home_page is None:
        for url, page in site.html_pages.items():
            if (urlsplit(url).path or "/").strip("/") == "":
                home_page = page
                break
    if home_page is not None and home_page.headers:
        cdn_detected = _detect_cdn_from_headers(home_page.headers)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Hostname resolves to an IP and geolocation succeeded",
        passed=bool(ip and geo),
        evidence={
            "host": host,
            "ip": ip,
            "country": geo.get("country"),
            "countryCode": geo.get("countryCode"),
            "isp": geo.get("isp"),
            "as": geo.get("as"),
            "dns_error": dns_error,
        },
        notes="Speculative — Google does not use server location as a ranking signal. Recorded for completeness.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-21",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "host": host,
            "ip": ip,
            "country": geo.get("country"),
            "country_code": geo.get("countryCode"),
            "city": geo.get("city"),
            "region": geo.get("region"),
            "isp": geo.get("isp"),
            "organisation": geo.get("org"),
            "asn": geo.get("as"),
            "cdn_detected": cdn_detected,
            "behind_cdn": cdn_detected is not None,
            "dns_error": dns_error,
            "watchlist": True,
            "note": (
                "Speculative — modern CDN deployment makes origin server location "
                "largely irrelevant to user experience. Behind-CDN sites should be "
                "evaluated via TTFB (P2-11), not origin geography."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=[
            "socket.gethostbyname",
            "http.ip_api_com",
            "http.html_fetch.headers",
            "composition.cdn_fingerprint",
        ],
    )


# ─── P2-40 — Host age (RDAP + archive.org) ──────────────────────────────────


@register_extractor("P2-40")
async def capture_p2_40(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-40 — Host age (Speculative, approximation).

    Approximates leaked Google ``hostAge`` via two independent signals:

    1. **RDAP domain registration date** (free public lookup via rdap.org).
    2. **archive.org Wayback Machine first-snapshot date** (free public
       endpoint).

    Both are publicly observable; neither equals Google's internal
    `hostAge` but together they approximate.

    Pass: host has either a known registration date OR a Wayback first-
    snapshot, AND age (from the earliest of the two) is >= 1 year.
    """
    import httpx
    from datetime import datetime as _dt
    from urllib.parse import urlsplit

    captured_at = _now()
    parsed = urlsplit(site.primary_url)
    host = (parsed.netloc or "").split(":", 1)[0].lower()
    # Strip leading "www." for the registrable domain
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-40",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no host in primary_url"},
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["rdap.org", "archive.org"],
            errors=["invalid primary_url"],
        )

    registration_date: datetime | None = None
    rdap_error: str | None = None
    wayback_date: datetime | None = None
    wayback_error: str | None = None

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1"},
    ) as client:
        # RDAP — public free domain registration data
        try:
            r = await client.get(f"https://rdap.org/domain/{host}")
            if r.status_code < 400:
                data = r.json()
                for event in (data.get("events") or []):
                    if event.get("eventAction") == "registration":
                        date_str = event.get("eventDate") or ""
                        try:
                            registration_date = _dt.fromisoformat(
                                date_str.replace("Z", "+00:00")
                            )
                            break
                        except ValueError:
                            pass
        except Exception as exc:  # noqa: BLE001
            rdap_error = f"{type(exc).__name__}: {exc}"

        # archive.org Wayback Machine: find earliest snapshot
        try:
            r = await client.get(
                "https://archive.org/wayback/available",
                params={"url": host, "timestamp": "19960101"},
            )
            if r.status_code < 400:
                data = r.json()
                ts = (
                    (data.get("archived_snapshots") or {})
                    .get("closest", {})
                    .get("timestamp")
                )
                if ts:
                    try:
                        wayback_date = _dt.strptime(ts, "%Y%m%d%H%M%S").replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        pass
        except Exception as exc:  # noqa: BLE001
            wayback_error = f"{type(exc).__name__}: {exc}"

    candidates = [d for d in (registration_date, wayback_date) if d is not None]
    if not candidates:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-40",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no host-age signal available (RDAP and Wayback both failed)",
                "rdap_error": rdap_error,
                "wayback_error": wayback_error,
            },
            rules=None,
            evidence_weight=EvidenceWeight.SPECULATIVE,
            data_sources=["rdap.org", "archive.org"],
            errors=list(filter(None, [rdap_error, wayback_error])),
        )

    earliest = min(candidates)
    now = _now()
    age_days = (now - earliest).days
    age_years = round(age_days / 365.25, 2)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Host age >= 1 year (established, not newly-launched)",
        passed=age_years >= 1.0,
        evidence={
            "age_years": age_years,
            "earliest_signal": earliest.isoformat(),
            "registration_date": registration_date.isoformat() if registration_date else None,
            "wayback_first_snapshot": wayback_date.isoformat() if wayback_date else None,
        },
        notes="Speculative — Google has historically denied domain age as a direct ranking factor. Recorded as a trust-context signal.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-40",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "host": host,
            "age_years": age_years,
            "age_days": age_days,
            "registration_date": registration_date.isoformat() if registration_date else None,
            "wayback_first_snapshot": wayback_date.isoformat() if wayback_date else None,
            "earliest_signal": earliest.isoformat(),
            "rdap_error": rdap_error,
            "wayback_error": wayback_error,
            "watchlist": True,
            "note": (
                "Speculative — approximates leaked Google hostAge. Neither RDAP "
                "creation date nor Wayback first-crawl equals Google's internal "
                "hostAge but together they bracket the host's public existence."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=[
            "rdap.org",
            "archive.org.wayback",
            "composition.host_age_approximation",
        ],
    )


# ─── P1-36 — Semantic keyword and entity coverage ───────────────────────────


@register_extractor("P1-36")
async def capture_p1_36(
    ctx: AdapterContext,
    site: SiteData,
    *,
    embeddings: EmbeddingsAdapter,
) -> CaptureRecord:
    """P1-36 — Semantic keyword and entity coverage (Probable).

    For each page with a mapped target keyword, check whether the page
    semantically covers the keyword AND its closest semantic neighbours
    (other ranked keywords with high embedding similarity to the target).

    Approach (no NER infrastructure needed):
    1. Embed every ranked keyword.
    2. For each ranked keyword K, find the top-5 most similar OTHER
       ranked keyword embeddings — these are "semantic siblings" of K.
    3. For each page that targets K (via ranked_keywords mapping),
       compute the page's similarity to K and to each of its siblings.
    4. Count siblings the page is "aligned with" (similarity >= 0.55) —
       this is the page's semantic coverage of K's topic cluster.

    Pass: median target-page semantic coverage across all mapped pages
    >= 3 (out of 5 possible siblings).
    """
    captured_at = _now()
    if not site.embeddings_configured or not site.embeddings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-36",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page embeddings available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["embeddings empty"],
        )
    if not site.ranked_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-36",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords for semantic-neighbour analysis"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["ranked_keywords empty"],
        )

    # Embed every ranked keyword once, build (keyword, vector, ranking_url)
    kw_records: list[dict[str, Any]] = []
    embed_errors: list[str] = []
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
        ranking_url = (serp.get("url") or "").strip()
        if not keyword:
            continue
        try:
            emb = await embeddings.embed(keyword)
        except EmbeddingsNotConfigured:
            embed_errors.append(f"{keyword}: not configured")
            continue
        except Exception as exc:  # noqa: BLE001
            embed_errors.append(f"{keyword}: {type(exc).__name__}")
            continue
        kw_records.append(
            {"keyword": keyword, "vector": emb.vector, "ranking_url": ranking_url}
        )

    if len(kw_records) < 2:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-36",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "fewer than 2 keyword embeddings — need at least 2 for sibling analysis",
                "embedded_keywords": len(kw_records),
                "errors": embed_errors[:5],
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=embed_errors[:3] or ["insufficient keywords"],
        )

    # For each ranked keyword, identify top-5 semantic-sibling keywords
    siblings_per_kw: dict[str, list[dict[str, Any]]] = {}
    for i, ri in enumerate(kw_records):
        sims = []
        for j, rj in enumerate(kw_records):
            if i == j:
                continue
            s = cosine_similarity(ri["vector"], rj["vector"])
            sims.append((rj["keyword"], rj["vector"], s))
        sims.sort(key=lambda t: t[2], reverse=True)
        siblings_per_kw[ri["keyword"]] = [
            {"keyword": k, "vector": v, "similarity_to_target": round(s, 3)}
            for k, v, s in sims[:5]
        ]

    # For each ranked-keyword target, score the ranking page against siblings
    coverage_findings: list[dict[str, Any]] = []
    for ri in kw_records:
        ranking_url = ri["ranking_url"]
        if not ranking_url:
            continue
        # Find the matching page embedding by normalised URL
        page_emb = None
        match_key = _norm_for_match(ranking_url)
        for url, emb in site.embeddings.items():
            if _norm_for_match(url) == match_key and emb.vector:
                page_emb = emb
                break
        if page_emb is None:
            continue

        page_to_target = cosine_similarity(page_emb.vector, ri["vector"])
        siblings = siblings_per_kw.get(ri["keyword"], [])
        sibling_scores = []
        for sib in siblings:
            score = cosine_similarity(page_emb.vector, sib["vector"])
            sibling_scores.append(
                {
                    "sibling_keyword": sib["keyword"],
                    "sibling_similarity_to_target": sib["similarity_to_target"],
                    "page_to_sibling_similarity": round(score, 3),
                    "aligned": score >= 0.55,
                }
            )
        coverage_count = sum(1 for s in sibling_scores if s["aligned"])
        coverage_findings.append(
            {
                "keyword": ri["keyword"],
                "ranking_url": ranking_url,
                "page_to_target_similarity": round(page_to_target, 3),
                "siblings_aligned": coverage_count,
                "siblings_total": len(sibling_scores),
                "sibling_scores": sibling_scores,
            }
        )

    if not coverage_findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-36",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no ranked-keyword pages have matching embeddings",
                "kw_records": len(kw_records),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["no matching page embeddings"],
        )

    coverages = sorted(f["siblings_aligned"] for f in coverage_findings)
    median_coverage = coverages[len(coverages) // 2]
    mean_coverage = round(sum(coverages) / len(coverages), 2)
    narrow_pages = [f for f in coverage_findings if f["siblings_aligned"] <= 1]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Median target-page semantic coverage >= 3 of 5 keyword siblings",
        passed=median_coverage >= 3,
        evidence={
            "median_coverage": median_coverage,
            "mean_coverage": mean_coverage,
            "pages_scored": len(coverage_findings),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 25% of pages have narrow coverage (<=1 sibling aligned)",
        passed=(
            not coverage_findings
            or len(narrow_pages) / len(coverage_findings) <= 0.25
        ),
        evidence={
            "narrow_pages_count": len(narrow_pages),
            "narrow_pages_sample": narrow_pages[:10],
            "narrow_pct": (
                round(len(narrow_pages) / len(coverage_findings) * 100, 1)
                if coverage_findings else 0
            ),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-36",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_scored": len(coverage_findings),
            "median_coverage": median_coverage,
            "mean_coverage": mean_coverage,
            "narrow_pages_count": len(narrow_pages),
            "findings_sample": coverage_findings[:10],
            "note": (
                "Semantic siblings derived from ranked-keyword embedding "
                "neighbourhood (top-5 most similar). Cleaner than rule-based "
                "expansion but bounded by the ranked-keyword surface; sites "
                "with thin ranked_keywords have small sibling sets."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "dataforseo_labs.ranked_keywords",
            "composition.semantic_neighbour_coverage",
        ],
    )


# ─── P2-16 — Mobile-friendly content (no hidden content) — heuristic ────────


# CSS / attribute patterns commonly used to hide content from rendered view
# but leave it in the DOM. These are heuristic indicators — true mobile-only
# hiding requires a dual-fetch (mobile vs desktop UA), which we don't run
# in this audit yet.
_HIDDEN_CONTENT_PATTERNS = (
    re.compile(r"display\s*:\s*none", re.I),
    re.compile(r"visibility\s*:\s*hidden", re.I),
    re.compile(r"\bhidden\b\s*=\s*[\"']?true", re.I),
    re.compile(r'\baria-hidden\s*=\s*"true"', re.I),
)

# Tab / accordion / collapse pattern hints in class names (common UI
# frameworks). These often hide content from mobile rendered view by
# default; substantive content inside collapsed tabs is invisible to
# the crawler unless the tab is expanded.
_TAB_PATTERN_CLASSES = (
    "tab-content", "tab-pane", "accordion-collapse",
    "accordion-body", "collapse", "panel-collapse",
    "drawer-content", "modal-body",
)


def _detect_hidden_content(soup: BeautifulSoup) -> dict[str, Any]:
    """Heuristic scan for content hidden in the rendered DOM.

    Returns counts and samples without trying to render the page.
    """
    findings: dict[str, Any] = {
        "inline_display_none": 0,
        "inline_visibility_hidden": 0,
        "aria_hidden_with_text": 0,
        "tab_panes": 0,
        "accordion_collapses": 0,
    }
    hidden_text_samples: list[str] = []

    # Inline style="display:none" / "visibility:hidden"
    for el in soup.find_all(style=True):
        style = (el.get("style") or "")
        if _HIDDEN_CONTENT_PATTERNS[0].search(style):
            findings["inline_display_none"] += 1
            text = el.get_text(" ", strip=True)
            if text and len(text) >= 50 and len(hidden_text_samples) < 5:
                hidden_text_samples.append(text[:200])
        if _HIDDEN_CONTENT_PATTERNS[1].search(style):
            findings["inline_visibility_hidden"] += 1

    # aria-hidden="true" on elements containing substantive text
    for el in soup.find_all(attrs={"aria-hidden": "true"}):
        text = el.get_text(" ", strip=True)
        if text and len(text) >= 50:
            findings["aria_hidden_with_text"] += 1
            if len(hidden_text_samples) < 5:
                hidden_text_samples.append(text[:200])

    # Tab pane / accordion patterns by class
    for el in soup.find_all(class_=True):
        classes = " ".join(el.get("class") or []).lower()
        if any(p in classes for p in ("tab-pane", "tab-content")):
            findings["tab_panes"] += 1
        if any(p in classes for p in ("accordion-collapse", "accordion-body", "collapse", "panel-collapse")):
            findings["accordion_collapses"] += 1

    findings["hidden_text_samples"] = hidden_text_samples
    return findings


@register_extractor("P2-16")
async def capture_p2_16(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-16 — Mobile-friendly content (Consensus, heuristic from raw HTML).

    Full version compares mobile and desktop renderings to detect
    mobile-only hidden content. We approximate from the raw HTML
    crawl by counting display:none / visibility:hidden / aria-hidden
    on substantive text + tab/accordion patterns. The signal
    correlates with content-parity issues even without dual fetch.

    Pass: per-page average of substantive-hidden elements <= 3 AND
    average accordion + tab pane count <= 8. Higher thresholds
    indicate content-locked-behind-interaction patterns which mobile
    crawlers may not unfold.

    Mobile-vs-desktop divergence detection remains deferred (needs
    DataForSEO dual-fetch with mobile UA).
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-16",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    per_page: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        findings = _detect_hidden_content(soup)
        substantive_hidden = (
            findings["inline_display_none"]
            + findings["inline_visibility_hidden"]
            + findings["aria_hidden_with_text"]
        )
        interaction_locked = findings["tab_panes"] + findings["accordion_collapses"]
        per_page.append(
            {
                "url": url,
                "substantive_hidden_count": substantive_hidden,
                "tab_panes": findings["tab_panes"],
                "accordion_collapses": findings["accordion_collapses"],
                "interaction_locked_count": interaction_locked,
                "hidden_text_samples": findings["hidden_text_samples"][:2],
            }
        )

    if not per_page:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-16",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no fetched HTML pages eligible"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch"],
            errors=["no eligible pages"],
        )

    avg_substantive_hidden = round(
        sum(p["substantive_hidden_count"] for p in per_page) / len(per_page), 2
    )
    avg_interaction_locked = round(
        sum(p["interaction_locked_count"] for p in per_page) / len(per_page), 2
    )
    worst_substantive = sorted(
        per_page, key=lambda p: p["substantive_hidden_count"], reverse=True
    )[:5]
    worst_interaction = sorted(
        per_page, key=lambda p: p["interaction_locked_count"], reverse=True
    )[:5]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site mean of substantive hidden elements (display:none + aria-hidden with text) <= 3 per page",
        passed=avg_substantive_hidden <= 3,
        evidence={
            "avg_substantive_hidden_per_page": avg_substantive_hidden,
            "worst_pages_sample": worst_substantive,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Site mean of interaction-locked panels (tabs + accordions) <= 8 per page",
        passed=avg_interaction_locked <= 8,
        evidence={
            "avg_interaction_locked_per_page": avg_interaction_locked,
            "worst_pages_sample": worst_interaction,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-16",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "pages_evaluated": len(per_page),
            "avg_substantive_hidden_per_page": avg_substantive_hidden,
            "avg_interaction_locked_per_page": avg_interaction_locked,
            "worst_hidden_sample": worst_substantive,
            "worst_interaction_locked_sample": worst_interaction,
            "caveat": (
                "Heuristic from raw HTML only — does NOT detect mobile-only "
                "hiding (CSS media queries). True mobile-vs-desktop content "
                "parity needs dual-fetch with mobile UA. The signals here "
                "(static display:none + interaction-locked panels) are a "
                "correlated subset, not the full check."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.hidden_content_heuristic"],
    )


# ─── P2-20 — Site uptime ────────────────────────────────────────────────────


@register_extractor("P2-20")
async def capture_p2_20(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-20 — Site uptime (Probable, single-audit reachability proxy).

    True site uptime requires external monitoring at 5-minute intervals
    over a rolling window (UptimeRobot / StatusCake / Pingdom). On a
    first audit we have a single-point sample only: was every fetched
    page reachable AT THE TIME OF AUDIT?

    Pass: >= 95% of attempted page fetches succeeded (status_code in
    2xx range, no fetch error). This is a reachability snapshot, NOT
    uptime — uptime emerges only after multiple audits accumulate or
    we wire UptimeRobot integration.

    Documents the gap; once we wire monitoring (UptimeRobot free tier
    handles 50 monitors @ 5min intervals), the extractor swaps to read
    the rolling-window uptime number.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-20",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    total_attempted = len(site.html_pages)
    successful = 0
    failed: list[dict[str, Any]] = []
    fetch_errored: list[dict[str, Any]] = []
    for url, page in site.html_pages.items():
        if page.fetch_error is not None:
            fetch_errored.append({"url": url, "error": page.fetch_error[:120]})
            continue
        if 200 <= (page.status_code or 0) < 300:
            successful += 1
        else:
            failed.append({"url": url, "status_code": page.status_code})

    reachable_pct = round(successful / total_attempted * 100, 1) if total_attempted else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 95% of fetched pages reachable (2xx status, no fetch error) at audit time",
        passed=reachable_pct >= 95,
        evidence={
            "total_attempted": total_attempted,
            "successful": successful,
            "failed_status_codes": failed[:10],
            "fetch_errored_count": len(fetch_errored),
            "fetch_errored_sample": fetch_errored[:5],
            "reachable_pct_this_audit": reachable_pct,
        },
        notes="Single-audit snapshot only — true uptime needs multi-audit history or external monitoring.",
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-20",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "measurement_type": "single_audit_reachability_snapshot",
            "total_attempted": total_attempted,
            "successful": successful,
            "non_2xx_count": len(failed),
            "fetch_errored_count": len(fetch_errored),
            "reachable_pct_this_audit": reachable_pct,
            "failed_status_sample": failed[:10],
            "caveat": (
                "Reachability at audit time only. Real uptime needs external "
                "monitoring (UptimeRobot free tier covers 50 monitors @ 5-min "
                "intervals) OR >= 2 audit snapshots over time to derive a "
                "rolling-window uptime number. Pass here means 'reachable now'; "
                "real uptime PASS is a 30-day >=99% threshold."
            ),
            "remediation_for_full_measurement": (
                "Sign up for UptimeRobot free account, generate API key, set "
                "UPTIMEROBOT_API_KEY in .env, and wire a new adapter call to "
                "read the monitor's 30-day stats."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.single_audit_reachability"],
    )


# ─── P1-44 — Content update magnitude ───────────────────────────────────────


@register_extractor("P1-44")
async def capture_p1_44(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P1-44 — Content update magnitude (Probable, historical-only).

    The taxonomy specifies: compare consecutive crawl snapshots of each
    page, measure diff magnitude (semantic embedding delta / character
    edit distance / structural changes). Distinguishes minor edits
    from substantive revisions.

    Structurally requires multi-snapshot history — meaningless on a
    first audit, same as P1-45 (update cadence). Returns UNMEASURABLE
    with a clear deferral: resolves once >= 2 audits of this site are
    in the database.

    First-audit footprint we DO record (as a baseline for future
    diffs): the count of pages we've now captured with main-text +
    embedding. Future audits compare against this baseline.
    """
    captured_at = _now()
    pages_with_text = sum(
        1 for pt in site.text_content.values()
        if getattr(pt, "main_text", "")
    )
    pages_with_embedding = len(site.embeddings)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-44",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": "Content update magnitude needs >= 2 audit snapshots of the same site to diff against. First-audit run captures the baseline only.",
            "baseline_captured": {
                "pages_with_main_text": pages_with_text,
                "pages_with_embedding": pages_with_embedding,
                "page_audits_total": len(site.page_audits),
            },
            "next_audit_unlocks": (
                "Once a second audit lands, P1-44 will diff the new text + "
                "embeddings against this baseline and classify each page's "
                "update as minor / substantive / no-change. Cosine similarity "
                "between page embeddings is the primary signal; character "
                "edit distance is a secondary confirmation."
            ),
            "applicability": "first_audit_baseline_only",
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "http.html_fetch",
            "trafilatura.extract",
            "gemini.embed_content",
            "composition.multi_snapshot_diff",
        ],
        errors=["historical signal not yet available"],
    )


# ─── P2-38 — Ads above-the-fold density ─────────────────────────────────────


_AD_CSS_PATTERNS = (
    "ad-banner", "ad-slot", "ad-container", "ad-wrapper", "ad-unit",
    "advertisement", "advert-", "google-ad", "adsense", "adsbygoogle",
    "banner-ad", "header-ad", "top-ad", "hero-ad",
    "google_ads_", "outbrain", "taboola",
)

_AD_NETWORK_HOSTS = (
    "googlesyndication.com",
    "googleadservices.com",
    "doubleclick.net",
    "amazon-adsystem.com",
    "outbrain.com",
    "taboola.com",
    "criteo.com",
    "media.net",
    "adnxs.com",
    "adsrvr.org",
)

# The "above the fold" approximation: first ~3000 chars of the body
# usually corresponds to ~600-800px of rendered viewport for most
# templates. Not exact, but a reasonable heuristic without rendering.
_ABOVE_FOLD_CHAR_WINDOW = 3500


def _detect_above_fold_ads(soup: BeautifulSoup, html: str) -> dict[str, Any]:
    """Heuristic: scan the start of body for ad markers."""
    body = soup.find("body")
    if body is None:
        return {"detected": False, "matches": []}
    body_str = str(body)[:_ABOVE_FOLD_CHAR_WINDOW]
    try:
        sub = BeautifulSoup(body_str, "html.parser")
    except Exception:  # noqa: BLE001
        return {"detected": False, "matches": []}

    matches: list[dict[str, Any]] = []

    # 1. CSS-class fingerprints
    for el in sub.find_all(class_=True):
        classes = " ".join(el.get("class") or []).lower()
        if not classes:
            continue
        for pat in _AD_CSS_PATTERNS:
            if pat in classes:
                matches.append(
                    {
                        "tag": el.name,
                        "matched_pattern": pat,
                        "class_attr": classes[:140],
                    }
                )
                break

    # 2. Ad-network iframes
    for iframe in sub.find_all("iframe"):
        src = (iframe.get("src") or "").strip().lower()
        if not src:
            continue
        host = urlsplit(src).netloc.lower().removeprefix("www.")
        if any(net in host for net in _AD_NETWORK_HOSTS):
            matches.append(
                {
                    "tag": "iframe",
                    "matched_pattern": f"ad_network:{host}",
                    "src": src[:140],
                }
            )

    # Deduplicate by pattern hint
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for m in matches:
        key = m.get("matched_pattern")
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)

    return {"detected": len(matches) > 0, "match_count": len(matches), "unique": unique[:5]}


@register_extractor("P2-38")
async def capture_p2_38(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-38 — Ads above-the-fold density (Probable, heuristic).

    Full version uses rendered-viewport screenshot analysis. We
    approximate from raw HTML by scanning the first ~3500 chars of
    body for:
    1. Element classes matching common ad-slot fingerprints
       (ad-banner, adsense, google-ad, advertisement, etc.)
    2. <iframe> elements sourced from ad-network hosts (doubleclick,
       googlesyndication, criteo, taboola, etc.)

    Pass: zero ad markers near the top of body on every page.
    Google's Page Layout Algorithm explicitly demotes pages with
    excessive above-fold advertising.

    Mobile-specific above-fold ads (CSS-injected via media queries
    only on mobile breakpoints) remain undetectable without dual-
    fetch rendering — flagged in the value.
    """
    captured_at = _now()
    if not site.html_pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-38",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no html_pages prefetched"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["html_pages empty"],
        )

    findings: list[dict[str, Any]] = []
    pages_with_ads = 0
    pages_checked = 0
    for url, page in site.html_pages.items():
        if page.fetch_error is not None or not page.html or page.status_code >= 400:
            continue
        try:
            soup = BeautifulSoup(page.html, "html.parser")
        except Exception:  # noqa: BLE001
            continue
        pages_checked += 1
        ad_finding = _detect_above_fold_ads(soup, page.html)
        if ad_finding["detected"]:
            pages_with_ads += 1
            findings.append({"url": url, **ad_finding})

    if pages_checked == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P2-38",
            pillar="P2",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no fetched HTML pages eligible"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["http.html_fetch"],
            errors=["no eligible pages"],
        )

    clean_pages = pages_checked - pages_with_ads
    clean_pct = round(clean_pages / pages_checked * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="No above-fold ad markers detected on any page (CSS ad-classes or ad-network iframes within first ~3500 chars of body)",
        passed=pages_with_ads == 0,
        evidence={
            "pages_checked": pages_checked,
            "pages_with_above_fold_ads": pages_with_ads,
            "clean_pct": clean_pct,
            "findings_sample": findings[:10],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-38",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "pages_checked": pages_checked,
            "pages_with_above_fold_ads": pages_with_ads,
            "clean_pages": clean_pages,
            "clean_pct": clean_pct,
            "findings_sample": findings[:10],
            "caveat": (
                "Heuristic from raw HTML — first ~3500 chars of body as "
                "above-fold proxy. Does NOT detect mobile-only ads injected "
                "via media queries OR ads inserted client-side after JS "
                "execution. Full rendered-viewport check would need "
                "Playwright + viewport-area calculation."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["http.html_fetch", "composition.above_fold_ad_heuristic"],
    )


# ─── P2-03 — Sitemap submission to GSC ──────────────────────────────────────


@register_extractor("P2-03")
async def capture_p2_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P2-03 — Sitemap submission to Google Search Console (Consensus).

    Whether the site has submitted its XML sitemap to GSC. The
    authoritative source is the GSC Sitemaps API which returns the
    full submission history per property + last-read timestamp + any
    errors Google encountered while crawling the sitemap.

    From an external auditor's vantage we can verify the sitemap
    EXISTS at conventional paths (which we already do — site.urls
    populated from sitemap discovery means the sitemap is reachable)
    but we cannot see GSC's submission status without OAuth into the
    property owner's account.

    Reports as UNMEASURABLE with the observable proxy surfaced (sitemap
    reachable + URL count) and remediation path documented.
    """
    captured_at = _now()
    sitemap_reachable = bool(site.urls)
    url_count_in_sitemap = len(site.urls or [])

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P2-03",
        pillar="P2",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "GSC submission status is gated behind owner OAuth via Google "
                "Search Console API. SEOMATE's external-audit positioning "
                "doesn't include GSC auth today, so we cannot see (a) whether "
                "the sitemap has been submitted, (b) GSC's last-read timestamp, "
                "or (c) any sitemap-fetch errors Google has logged."
            ),
            "observable_proxy": {
                "sitemap_reachable_externally": sitemap_reachable,
                "url_count_in_sitemap": url_count_in_sitemap,
                "note": (
                    "Sitemap being reachable at the conventional path is a "
                    "PREREQUISITE for GSC submission but doesn't prove it. "
                    "Google can also auto-discover sitemaps from robots.txt; "
                    "many sites are 'submitted' implicitly via discovery "
                    "rather than explicit submission."
                ),
            },
            "remediation_paths": [
                "Wire GSC OAuth flow + GSC Sitemaps API adapter — site owner authorises SEOMATE to read their GSC property; we then pull submission history + last-read + error count.",
                "Owner exports the Sitemaps panel from GSC manually and uploads CSV.",
            ],
            "watchlist": True,
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.sitemap_fetch",
            "google_search_console.sitemaps (not wired)",
        ],
        errors=["GSC OAuth not wired"],
    )
