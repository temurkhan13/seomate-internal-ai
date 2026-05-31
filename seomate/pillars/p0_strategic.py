"""Pillar 0 — Strategic Foundation extractors.

Variables in P0 ground every other pillar's interpretation: who the brand
is, what queries it competes on, what intent class its content serves.
H1a only ships the entity-recognition variables that don't require a
keyword universe; the keyword and YMYL-classification variables come in
later stages.

Variables operationalised in this module:

- P0-16 — Brand entity recognition by Google Knowledge Graph
            (Probable; query Knowledge Graph for every brand variant;
            unmeasurable when GOOGLE_KG_API_KEY is unset.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import re

from seomate.adapters import (
    AdapterContext,
    EmbeddingsAdapter,
    EmbeddingsNotConfigured,
    KGNotConfigured,
    KGSearchHit,
    KnowledgeGraphAdapter,
    cosine_similarity,
)
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor


# ─── KG result-score thresholds ─────────────────────────────────────────────
# Google's resultScore is unitless and varies by entity, but practitioners
# converge on the broad bands below: a brand under ~5 is effectively
# unknown to KG, 5–50 is a fuzzy / ambiguous match (often a homonym), and
# above 50 indicates a confidently-resolved entity. We record the scores
# verbatim in evidence so future reviewers can re-judge if the bands shift.
KG_HIGH_CONFIDENCE = 50.0
KG_FUZZY_FLOOR = 5.0


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
        pillar="P0",
        captured_at=captured_at,
        taxonomy_version=getattr(ctx, "taxonomy_version", "unknown"),
        subject_type=SubjectType.BRAND,
        subject_id=site.brand.name if site.brand else site.domain,
        status=status,
        value=value,
        rules=rules,
        evidence_weight=evidence_weight,
        data_sources_used=data_sources,
        cost_incurred_gbp=cost_gbp,
        errors=errors,
    )


def _hit_summary(hit: KGSearchHit) -> dict[str, Any]:
    """Trim a KG hit down to fields safe to persist in evidence."""
    return {
        "name": hit.name,
        "description": hit.description,
        "types": list(hit.types),
        "url": hit.url,
        "kg_id": hit.kg_id,
        "result_score": hit.result_score,
    }


# ─── P0-16 — Brand entity recognition by Google Knowledge Graph ─────────────


@register_extractor("P0-16")
async def capture_p0_16(
    ctx: AdapterContext,
    site: SiteData,
    *,
    kg: KnowledgeGraphAdapter,
) -> CaptureRecord:
    """P0-16 — Brand entity recognition by Google Knowledge Graph.

    The brand is queried under every variant declared in the audit
    config (canonical name, aliases, legal entities). For each variant
    we capture the top KG hit's resultScore and bin it into:

    - ``high_confidence`` (score >= 50): KG resolves the variant to a
      confident entity match.
    - ``fuzzy`` (5 <= score < 50): KG returns *something*, but the
      score band is where homonyms and weak matches dominate. Recorded
      as evidence; does not by itself flip the variable to passing.
    - ``unknown`` (score < 5 or no hits): no meaningful resolution.

    The variable passes when at least one variant returns a
    high-confidence hit AND that hit's URL or sameAs links resolve to
    the audited domain (verified by substring match against the
    primary URL host). Recorded as ``Probable`` because Google does
    not publicly document KG inclusion criteria — we know presence
    correlates with brand authority signals but the exact mechanics
    are not disclosed.
    """
    captured_at = _now()
    domain = site.domain.lower()
    brand = site.brand
    if brand is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand identity configured for this audit"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["google_kg.entities_search"],
            errors=["site.brand is None"],
        )

    variants = brand.all_variants
    if not variants:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand identity has no name or aliases"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["google_kg.entities_search"],
            errors=["brand.all_variants is empty"],
        )

    per_variant: list[dict[str, Any]] = []
    high_confidence: list[dict[str, Any]] = []
    fuzzy: list[dict[str, Any]] = []
    domain_matches: list[dict[str, Any]] = []
    api_errors: list[str] = []

    for variant in variants:
        try:
            hits = await kg.search(variant, limit=5)
        except KGNotConfigured as exc:
            return _build_record(
                ctx=ctx,
                site=site,
                variable_id="P0-16",
                captured_at=captured_at,
                status=CaptureStatus.UNMEASURABLE,
                value={
                    "reason": "GOOGLE_KG_API_KEY not set; cannot query Knowledge Graph",
                    "variants_planned": list(variants),
                },
                rules=None,
                evidence_weight=EvidenceWeight.PROBABLE,
                data_sources=["google_kg.entities_search"],
                errors=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001 - failure is data
            api_errors.append(f"{variant}: {type(exc).__name__}: {exc}")
            per_variant.append({"variant": variant, "error": str(exc)})
            continue

        top = hits[0] if hits else None
        summary = _hit_summary(top) if top else None
        score = top.result_score if top else 0.0
        band = "unknown"
        if top is not None:
            if score >= KG_HIGH_CONFIDENCE:
                band = "high_confidence"
                high_confidence.append({"variant": variant, **summary})  # type: ignore[arg-type]
            elif score >= KG_FUZZY_FLOOR:
                band = "fuzzy"
                fuzzy.append({"variant": variant, **summary})  # type: ignore[arg-type]

        # Domain verification: does the KG entity's URL or any sameAs
        # link reference the audited site? Used so a "Pixelette" hit for
        # an unrelated entity doesn't count as recognition of *our* brand.
        domain_match = False
        if top is not None:
            url_blob = " ".join(
                str(s) for s in (top.url, *top.same_as) if s
            ).lower()
            domain_match = domain in url_blob
            if domain_match:
                domain_matches.append({"variant": variant, **summary})  # type: ignore[arg-type]

        per_variant.append(
            {
                "variant": variant,
                "hit_count": len(hits),
                "top_score": score,
                "band": band,
                "domain_match": domain_match,
                "top_hit": summary,
            }
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one brand variant returns a high-confidence Knowledge Graph hit (resultScore >= 50)",
        passed=bool(high_confidence),
        evidence={
            "threshold_high_confidence": KG_HIGH_CONFIDENCE,
            "high_confidence_hits": high_confidence,
            "high_confidence_count": len(high_confidence),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="The matched KG entity links back to the audited domain (URL or sameAs contains the site domain)",
        passed=bool(domain_matches),
        evidence={
            "domain_query": domain,
            "matching_hits": domain_matches,
            "matching_count": len(domain_matches),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Fuzzy-band hits are surfaced for review (5 <= score < 50)",
        passed=True,
        evidence={
            "threshold_fuzzy_floor": KG_FUZZY_FLOOR,
            "fuzzy_hits": fuzzy,
            "fuzzy_count": len(fuzzy),
        },
        notes=(
            "Fuzzy hits are common when the brand name is a real word or "
            "shares its name with another entity; they neither pass nor "
            "fail the variable on their own."
        ),
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed
    if api_errors and not high_confidence:
        # We hit transient errors AND found nothing; safer to mark
        # partial than confidently fail.
        status = CaptureStatus.PARTIAL
    else:
        status = CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-16",
        captured_at=captured_at,
        status=status,
        value={
            "brand": brand.name,
            "variants_queried": list(variants),
            "per_variant": per_variant,
            "high_confidence_count": len(high_confidence),
            "fuzzy_count": len(fuzzy),
            "domain_match_count": len(domain_matches),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["google_kg.entities_search"],
        errors=api_errors or None,
    )


# ─── P0-17 — YMYL classification of pages and topics ────────────────────────


@register_extractor("P0-17")
async def capture_p0_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-17 — YMYL classification across the site (Consensus, LLM-classified).

    Aggregates per-page YMYL classifications from the YmylClassifier
    LLM evaluator into a site-level capture: YMYL share, category
    distribution, borderline-page count. The variable passes when
    classification ran cleanly across substantive pages (no errors,
    every page assigned a category).
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("ymyl", {})
    if not evals:
        reason = (
            "ANTHROPIC_API_KEY not set"
            if not site.llm_configured
            else "no substantive pages (>= 100 words) for classification"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-17",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create", "composition.ymyl_classifier"],
            errors=[reason],
        )

    total = len(evals)
    ymyl_count = 0
    borderline_count = 0
    by_category: dict[str, int] = {}
    errored: list[dict[str, Any]] = []
    page_classifications: list[dict[str, Any]] = []

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        raw = ev.raw or {}
        is_ymyl = bool(raw.get("is_ymyl"))
        category = str(raw.get("category") or "none")
        if is_ymyl:
            ymyl_count += 1
        if raw.get("borderline"):
            borderline_count += 1
        by_category[category] = by_category.get(category, 0) + 1
        page_classifications.append(
            {
                "url": url,
                "is_ymyl": is_ymyl,
                "category": category,
                "borderline": bool(raw.get("borderline")),
                "confidence": ev.confidence,
            }
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every substantive page classified (no errors, no missing rows)",
        passed=len(errored) == 0,
        evidence={
            "classified_count": total - len(errored),
            "errored_count": len(errored),
            "errored_sample": errored[:10],
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Borderline cases flagged for human review (some borderline expected on most sites)",
        passed=True,
        evidence={
            "borderline_count": borderline_count,
            "borderline_pct": (
                round(borderline_count / total * 100, 1) if total else 0
            ),
        },
        notes="Surfaced for review rather than enforced as pass/fail.",
    )

    rules = [rule_1, rule_4]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_classified": total - len(errored),
            "pages_errored": len(errored),
            "ymyl_pages": ymyl_count,
            "ymyl_pct": round(ymyl_count / total * 100, 1) if total else 0,
            "borderline_pages": borderline_count,
            "category_distribution": by_category,
            "page_classifications_sample": page_classifications[:20],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["anthropic.messages.create", "composition.ymyl_classifier"],
    )


# ─── P0-01 — Search intent classification per query ─────────────────────────
# Patterns + classifier live in seomate.utils.intent so the orchestrator
# can use them for SERP-seed filtering without a circular dependency.

from seomate.utils.intent import classify_intent as _classify_intent


@register_extractor("P0-01")
async def capture_p0_01(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-01 — Search intent classification per query (Consensus, rule-based).

    For every keyword in ``site.ranked_keywords``, apply rule-based
    pattern matching to classify intent as one of:
    transactional / commercial / navigational / informational.

    Pass if every keyword received a non-fallback classification
    (i.e., at least one pattern matched). Default-fallback keywords are
    reported separately as low-confidence cases.
    """
    captured_at = _now()
    if not site.ranked_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-01",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords available for classification"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["dataforseo_labs.ranked_keywords", "composition.intent_classifier"],
            errors=["ranked_keywords empty"],
        )

    brand_variants = site.brand.all_variants if site.brand else ()
    classifications: list[dict] = []
    intent_counts = {
        "transactional": 0, "commercial": 0,
        "navigational": 0, "informational": 0,
    }
    fallback_count = 0
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        if not keyword:
            continue
        result = _classify_intent(keyword, brand_variants)
        intent_counts[result["intent"]] += 1
        if result["method"] == "default_fallback":
            fallback_count += 1
        classifications.append(
            {
                "keyword": keyword,
                "intent": result["intent"],
                "confidence": result["confidence"],
                "matched_patterns": result["matched_patterns"],
                "method": result["method"],
            }
        )

    total = len(classifications)
    confident_pct = (
        round((total - fallback_count) / total * 100, 1) if total else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every ranked keyword receives an intent classification",
        passed=total > 0,
        evidence={"total_classified": total},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=70% of keywords match an intent pattern (not default fallback)",
        passed=confident_pct >= 70,
        evidence={
            "total": total,
            "matched_pattern_count": total - fallback_count,
            "fallback_count": fallback_count,
            "confident_pct": confident_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_keywords": total,
            "intent_distribution": intent_counts,
            "confident_pct": confident_pct,
            "fallback_count": fallback_count,
            "classifications_sample": classifications[:25],
            "note": "Rule-based pattern matching; LLM fallback for ambiguous queries deferred to future iteration.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "composition.intent_classifier",
        ],
    )


# ─── P0-09 — Site embedding similarity to query ─────────────────────────────


def _site_centroid(site: SiteData) -> tuple[float, ...] | None:
    """Compute the mean embedding across all successfully-embedded pages."""
    if not site.embeddings:
        return None
    vectors = [emb.vector for emb in site.embeddings.values() if emb.vector]
    if not vectors:
        return None
    dim = len(vectors[0])
    centroid = [0.0] * dim
    for v in vectors:
        for i, val in enumerate(v):
            centroid[i] += val
    n = len(vectors)
    return tuple(val / n for val in centroid)


@register_extractor("P0-09")
async def capture_p0_09(
    ctx: AdapterContext,
    site: SiteData,
    *,
    embeddings: EmbeddingsAdapter,
) -> CaptureRecord:
    """P0-09 — Site embedding similarity to query (Probable).

    Cosine similarity between the site's centroid embedding (mean of
    all page embeddings) and each ranked-keyword query embedding.

    Site centroid represents the site's overall topical position.
    High similarity to a query = topical coverage well-aligned with
    that query.

    Pass: site median similarity across all ranked keywords >= 0.5
    AND no ranked keyword scores below 0.3 (no completely off-topic
    queries — if there are, the site is ranking for queries its
    content doesn't actually serve, a topical misalignment signal).
    """
    captured_at = _now()
    if not site.embeddings_configured:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "GEMINI_API_KEY not configured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content", "composition.site_centroid"],
            errors=["embeddings adapter not configured"],
        )
    if not site.ranked_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords to embed"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["ranked_keywords empty"],
        )

    centroid = _site_centroid(site)
    if centroid is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no page embeddings available to compute centroid"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["no embeddings"],
        )

    similarities: list[dict] = []
    embed_errors: list[str] = []
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        if not keyword:
            continue
        try:
            q_emb = await embeddings.embed(keyword)
        except EmbeddingsNotConfigured:
            embed_errors.append(f"{keyword}: not configured")
            continue
        except Exception as exc:  # noqa: BLE001
            embed_errors.append(f"{keyword}: {type(exc).__name__}")
            continue
        sim = cosine_similarity(centroid, q_emb.vector)
        similarities.append({"keyword": keyword, "similarity": round(sim, 3)})

    if not similarities:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no query embeddings succeeded", "errors": embed_errors[:5]},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=embed_errors[:5] or ["no successful embeddings"],
        )

    sims = sorted(s["similarity"] for s in similarities)
    median = sims[len(sims) // 2]
    mean = sum(sims) / len(sims)
    min_sim = sims[0]
    max_sim = sims[-1]
    offtopic_count = sum(1 for s in sims if s < 0.3)
    offtopic_pages = [s for s in similarities if s["similarity"] < 0.3]
    best_match = max(similarities, key=lambda s: s["similarity"])
    worst_match = min(similarities, key=lambda s: s["similarity"])

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site centroid median similarity to ranked keywords >= 0.5",
        passed=median >= 0.5,
        evidence={
            "median_similarity": round(median, 3),
            "mean_similarity": round(mean, 3),
            "queries_evaluated": len(similarities),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No ranked keyword scores below 0.3 (no severely off-topic queries)",
        passed=offtopic_count == 0,
        evidence={
            "offtopic_count": offtopic_count,
            "offtopic_queries": offtopic_pages,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-09",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "queries_evaluated": len(similarities),
            "median_similarity": round(median, 3),
            "mean_similarity": round(mean, 3),
            "min_similarity": round(min_sim, 3),
            "max_similarity": round(max_sim, 3),
            "best_match": best_match,
            "worst_match": worst_match,
            "offtopic_count": offtopic_count,
            "offtopic_queries": offtopic_pages[:10],
            "similarities_sample": similarities[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "dataforseo_labs.ranked_keywords",
            "composition.site_centroid_similarity",
        ],
    )


# ─── P0-10 — Page embedding similarity to query ─────────────────────────────


@register_extractor("P0-10")
async def capture_p0_10(
    ctx: AdapterContext,
    site: SiteData,
    *,
    embeddings: EmbeddingsAdapter,
) -> CaptureRecord:
    """P0-10 — Page embedding similarity to query (Probable).

    For each ranked keyword, embed the query and compute cosine
    similarity against every page embedding. Identify the best-match
    page per query and compare to the page that's actually ranking.

    A mismatch (Google ranks page X for the query, but page Y is the
    semantically best match) signals an internal-linking or canonical
    architecture problem — the content is there but the wrong page is
    surfacing.

    Pass: >= 50% of ranked queries have the actual ranking URL as the
    best-match page (or in the top 3).
    """
    captured_at = _now()
    if not site.embeddings_configured or not site.embeddings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-10",
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
            variable_id="P0-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords to embed"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["ranked_keywords empty"],
        )

    # Pre-extract URL key map for the page embeddings
    page_vectors: list[tuple[str, tuple[float, ...]]] = [
        (url, emb.vector) for url, emb in site.embeddings.items() if emb.vector
    ]
    if not page_vectors:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no non-empty page embeddings"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=["empty embeddings"],
        )

    findings: list[dict] = []
    matches_at_1 = 0
    matches_at_3 = 0
    embed_errors: list[str] = []
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
        ranking_url = (serp.get("url") or "").strip()
        if not keyword:
            continue
        try:
            q_emb = await embeddings.embed(keyword)
        except EmbeddingsNotConfigured:
            embed_errors.append(f"{keyword}: not configured")
            continue
        except Exception as exc:  # noqa: BLE001
            embed_errors.append(f"{keyword}: {type(exc).__name__}")
            continue

        sims = [
            (url, cosine_similarity(q_emb.vector, vec))
            for url, vec in page_vectors
        ]
        sims.sort(key=lambda t: t[1], reverse=True)
        top_3 = sims[:3]
        best_url, best_sim = top_3[0]
        ranking_url_match_top1 = (
            bool(ranking_url) and _url_paths_match(ranking_url, best_url)
        )
        ranking_url_in_top3 = bool(ranking_url) and any(
            _url_paths_match(ranking_url, u) for u, _ in top_3
        )

        if ranking_url_match_top1:
            matches_at_1 += 1
        if ranking_url_in_top3:
            matches_at_3 += 1

        findings.append(
            {
                "keyword": keyword,
                "actual_ranking_url": ranking_url or None,
                "best_match_url": best_url,
                "best_match_similarity": round(best_sim, 3),
                "ranking_url_is_best_match": ranking_url_match_top1,
                "ranking_url_in_top_3": ranking_url_in_top3,
                "top_3": [
                    {"url": u, "similarity": round(s, 3)} for u, s in top_3
                ],
            }
        )

    if not findings:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successful query embeddings", "errors": embed_errors[:5]},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["gemini.embed_content"],
            errors=embed_errors[:5] or ["all query embeddings failed"],
        )

    queries_with_ranking_url = sum(1 for f in findings if f["actual_ranking_url"])
    top1_pct = (
        round(matches_at_1 / queries_with_ranking_url * 100, 1)
        if queries_with_ranking_url else 0
    )
    top3_pct = (
        round(matches_at_3 / queries_with_ranking_url * 100, 1)
        if queries_with_ranking_url else 0
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">=50% of ranked queries have the actual ranking URL as the best semantic match",
        passed=queries_with_ranking_url > 0 and top1_pct >= 50,
        evidence={
            "queries_with_ranking_url": queries_with_ranking_url,
            "top1_matches": matches_at_1,
            "top1_match_pct": top1_pct,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=80% of ranked queries have the actual ranking URL in the semantic top-3",
        passed=queries_with_ranking_url > 0 and top3_pct >= 80,
        evidence={
            "top3_matches": matches_at_3,
            "top3_match_pct": top3_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed
    mismatches = [
        f for f in findings
        if f["actual_ranking_url"] and not f["ranking_url_in_top_3"]
    ]

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "queries_evaluated": len(findings),
            "queries_with_ranking_url": queries_with_ranking_url,
            "top1_match_pct": top1_pct,
            "top3_match_pct": top3_pct,
            "mismatches_count": len(mismatches),
            "mismatches_sample": mismatches[:10],
            "findings_sample": findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "dataforseo_labs.ranked_keywords",
            "composition.page_query_similarity",
        ],
    )


def _url_paths_match(a: str, b: str) -> bool:
    """Compare two URLs by host + path only (ignore scheme + trailing slash)."""
    from urllib.parse import urlsplit
    ap, bp = urlsplit(a), urlsplit(b)
    a_host = (ap.netloc or "").lower().lstrip("www.")
    b_host = (bp.netloc or "").lower().lstrip("www.")
    a_path = (ap.path or "/").rstrip("/") or "/"
    b_path = (bp.path or "/").rstrip("/") or "/"
    return a_host == b_host and a_path == b_path


# ─── P0-06 — Buyer journey stage per keyword ────────────────────────────────


_BUYER_DECISION_PATTERNS = (
    re.compile(r"\b(buy|order|purchase|hire|book|reserve|rent|subscribe)\b", re.I),
    re.compile(r"\b(price|pricing|cost|quote|fee|fees)\b", re.I),
    re.compile(r"\b(near\s+me|near\s+by|in\s+[a-z]{4,}\s+(area|city|town))\b", re.I),
    re.compile(r"\b(discount|deal|sale|coupon|promo|offer)\b", re.I),
)

_BUYER_CONSIDERATION_PATTERNS = (
    re.compile(r"\b(best|top|review|reviews|comparison|compare|alternative|alternatives)\b", re.I),
    re.compile(r"\bvs\.?\b", re.I),
    re.compile(r"\b(pros\s+and\s+cons|advantages|disadvantages)\b", re.I),
    re.compile(r"\b(which\s+(?:is|are|to\s+choose))\b", re.I),
)

_BUYER_AWARENESS_PATTERNS = (
    re.compile(r"\bwhat\s+(?:is|are|does|do)\b", re.I),
    re.compile(r"\bhow\s+(?:to|does|do|can|should)\b", re.I),
    re.compile(r"\bwhy\s+(?:is|does|do|should)\b", re.I),
    re.compile(r"\b(guide|tutorial|introduction|basics|fundamentals)\b", re.I),
    re.compile(r"\b(definition|meaning|explained?)\b", re.I),
)


# ─── P0-14 — Content gap analysis vs ranking competitors ────────────────────


@register_extractor("P0-14")
async def capture_p0_14(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-14 — Content gap analysis vs ranking competitors (Probable).

    For each direct competitor, identify keywords they rank for that
    our site doesn't, plus topical clusters they cover that we don't.
    Requires:
    1. A competitor list (config.audit.competitors), OR
    2. SERP-overlap-based auto-discovery (paid DataForSEO SERP API).

    Without either, the variable is structurally unmeasurable. We
    record this explicitly rather than guess — accuracy matters more
    than coverage padding.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-14",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "Deferred. SERP-overlap auto-discovery was prototyped and "
                "ruled out: discovered competitors reflect only the narrow "
                "topic cluster our current ranked keywords surface on, not "
                "the brand's actual competitive set. For Pixelette this "
                "produced 5 software-development-cost peers, missing every "
                "other service line."
            ),
            "future_approach": (
                "Revisit when the SEOMATE UI lets the user declare "
                "strategic aspirations (which markets / which service "
                "lines they want to rank in). From there: automated "
                "keyword research per declared category, then SERP-overlap "
                "competitor discovery per category. This gives competitive "
                "sets per service-line, not a single global set."
            ),
            "status": "deferred_pending_strategic_input",
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "config.audit.competitors",
            "dataforseo.serp_google_organic",
        ],
        errors=["deferred"],
    )


def _classify_buyer_stage(keyword: str, intent: str) -> dict:
    """Map intent + query patterns to a buyer journey stage.

    Returns {"stage": one_of_3, "confidence": 0..1, "method": str}.
    """
    if intent == "transactional":
        return {"stage": "decision", "confidence": 0.9, "method": "intent_transactional"}
    if intent == "commercial":
        return {"stage": "consideration", "confidence": 0.85, "method": "intent_commercial"}

    # For informational or navigational, look at patterns
    for pat in _BUYER_DECISION_PATTERNS:
        if pat.search(keyword):
            return {"stage": "decision", "confidence": 0.8, "method": "pattern_decision"}
    for pat in _BUYER_CONSIDERATION_PATTERNS:
        if pat.search(keyword):
            return {"stage": "consideration", "confidence": 0.75, "method": "pattern_consideration"}
    for pat in _BUYER_AWARENESS_PATTERNS:
        if pat.search(keyword):
            return {"stage": "awareness", "confidence": 0.75, "method": "pattern_awareness"}

    # Navigational queries typically don't map cleanly to a single funnel stage
    if intent == "navigational":
        return {"stage": "consideration", "confidence": 0.4, "method": "navigational_default"}
    # Default informational without specific patterns → awareness (most common)
    return {"stage": "awareness", "confidence": 0.4, "method": "informational_default"}


@register_extractor("P0-06")
async def capture_p0_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-06 — Buyer journey stage per keyword (Probable, composition).

    For each ranked keyword, classify into:
    - **awareness** — early information-seeking ("what is", "how to")
    - **consideration** — active evaluation ("best", "vs", "review")
    - **decision** — purchase-ready ("buy", "price", "near me")

    Derived from P0-01 intent classification + extra query-pattern checks.

    Pass: every keyword receives a classification AND >= 70% have
    confidence > 0.5 (not just fallback defaults).
    """
    captured_at = _now()
    if not site.ranked_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-06",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no ranked_keywords"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["dataforseo_labs.ranked_keywords"],
            errors=["ranked_keywords empty"],
        )

    brand_variants = site.brand.all_variants if site.brand else ()
    classifications: list[dict] = []
    stage_counts = {"awareness": 0, "consideration": 0, "decision": 0}
    confidence_sum = 0.0
    for item in site.ranked_keywords:
        kw_data = item.get("keyword_data") or {}
        keyword = (kw_data.get("keyword") or "").strip()
        if not keyword:
            continue
        intent_result = _classify_intent(keyword, brand_variants)
        intent = intent_result["intent"]
        stage_result = _classify_buyer_stage(keyword, intent)
        stage_counts[stage_result["stage"]] += 1
        confidence_sum += stage_result["confidence"]
        classifications.append(
            {
                "keyword": keyword,
                "intent": intent,
                "stage": stage_result["stage"],
                "confidence": stage_result["confidence"],
                "method": stage_result["method"],
            }
        )

    total = len(classifications)
    mean_confidence = round(confidence_sum / total, 2) if total else 0
    confident_count = sum(1 for c in classifications if c["confidence"] > 0.5)
    confident_pct = round(confident_count / total * 100, 1) if total else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every keyword receives a buyer journey stage classification",
        passed=total > 0,
        evidence={"total_classified": total},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=">=70% of keywords classified with confidence >0.5",
        passed=confident_pct >= 70,
        evidence={
            "confident_count": confident_count,
            "confident_pct": confident_pct,
            "mean_confidence": mean_confidence,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-06",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_keywords": total,
            "stage_distribution": stage_counts,
            "stage_distribution_pct": {
                k: round(v / total * 100, 1) if total else 0
                for k, v in stage_counts.items()
            },
            "mean_confidence": mean_confidence,
            "confident_pct": confident_pct,
            "classifications_sample": classifications[:25],
            "note": "Stage derived from P0-01 intent + query patterns; LLM refinement deferred.",
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "dataforseo_labs.ranked_keywords",
            "composition.intent_classifier",
            "composition.buyer_journey_classifier",
        ],
    )


# ─── P0-05 — SERP feature presence per query ────────────────────────────────


# Map DataForSEO `type` field → friendly feature name. The most
# operationally relevant features are included; obscure types fall
# through to "other".
_SERP_FEATURE_TYPES = {
    "ai_overview": "AI Overview",
    "ai_mode": "AI Overview",
    "featured_snippet": "Featured Snippet",
    "people_also_ask": "People Also Ask",
    "knowledge_graph": "Knowledge Panel",
    "local_pack": "Local Pack",
    "map": "Map",
    "images": "Image Pack",
    "video": "Video Pack",
    "shopping": "Shopping Pack",
    "top_stories": "Top Stories",
    "twitter": "Twitter / X",
    "events": "Events Pack",
    "jobs": "Jobs Pack",
    "podcasts": "Podcasts",
    "related_searches": "Related Searches",
    "answer_box": "Answer Box",
    "carousel": "Carousel",
    "sitelinks": "Sitelinks",
}


@register_extractor("P0-05")
async def capture_p0_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-05 — SERP feature presence per query (Consensus).

    Reads each prefetched SERP and collects the set of SERP feature
    types Google shows for that query. Feature inventory matters for
    organic CTR (AI Overview suppresses, Featured Snippet amplifies)
    and indicates query type.

    Pass: every keyword in the prefetched SERP set has a feature
    inventory recorded (no failed fetches).
    """
    captured_at = _now()
    serps = site.serp_results or {}
    if not serps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERP prefetch results available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["serp.google.organic"],
            errors=["no SERPs"],
        )

    per_kw: list[dict[str, Any]] = []
    feature_counts: dict[str, int] = {}
    for kw, result in serps.items():
        items = result.get("items") or []
        types_present: set[str] = set()
        for item in items:
            t = item.get("type")
            if not isinstance(t, str):
                continue
            if t == "organic":
                continue  # organic rows are the baseline, not a "feature"
            friendly = _SERP_FEATURE_TYPES.get(t, t)
            types_present.add(friendly)
        for f in types_present:
            feature_counts[f] = feature_counts.get(f, 0) + 1
        per_kw.append(
            {
                "keyword": kw,
                "features": sorted(types_present),
                "feature_count": len(types_present),
            }
        )

    feature_counts_sorted = dict(
        sorted(feature_counts.items(), key=lambda kv: kv[1], reverse=True)
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every queried keyword has a SERP feature inventory recorded",
        passed=len(per_kw) == len(serps),
        evidence={
            "queries_with_inventory": len(per_kw),
            "queries_attempted": len(serps),
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "queries_inspected": len(per_kw),
            "feature_frequency_across_queries": feature_counts_sorted,
            "per_keyword": per_kw,
            "note": (
                "Single-point snapshot for top-N ranked keywords (default 10). "
                "SERP feature inventory shifts day-to-day; weekly multi-audit "
                "tracking gives the stable trend per Whitespark / Ahrefs."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["serp.google.organic", "composition.serp_feature_inventory"],
    )


# ─── P0-18 — Big-brand preference threshold detection ──────────────────────


@register_extractor("P0-18")
async def capture_p0_18(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-18 — Big-brand preference threshold detection (Probable).

    Looks at each prefetched ranked-keyword SERP and counts how many of
    the top-10 organic results belong to recognised big-brand /
    authority domains (Wikipedia, .gov, .edu, tier-1 publications,
    large consultancies, tech giants). When the share is high, smaller
    sites have minimal ranking opportunity regardless of on-page work.

    Full version uses per-domain DR lookups (paid backlinks API or
    Ahrefs); our heuristic uses a curated authority host list as a
    proxy.

    Pass: <= 30% of total top-10 slots across all queried SERPs are
    occupied by big-brand hosts (rough threshold; high ratios indicate
    big-brand-dominated SERPs).
    """
    captured_at = _now()
    from seomate.pillars.p6_geo import _BIG_BRAND_AUTHORITY_HOSTS

    serps = site.serp_results or {}
    if not serps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERP prefetch results available"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no SERPs"],
        )

    # Exclude the brand-name SERP — there it's natural for the brand
    # itself to dominate; we want competing SERPs only
    brand_name = (site.brand.name if site.brand else "").lower()
    per_keyword: list[dict] = []
    total_slots = 0
    total_big_brand = 0
    for kw, result in serps.items():
        if brand_name and brand_name in kw.lower():
            continue
        items = result.get("items") or []
        organic = [i for i in items if i.get("type") == "organic"][:10]
        big_brand_hosts: list[str] = []
        for it in organic:
            domain = (it.get("domain") or "").lower().lstrip("www.")
            url = (it.get("url") or "").lower()
            for frag in _BIG_BRAND_AUTHORITY_HOSTS:
                if frag in domain or frag in url:
                    big_brand_hosts.append(domain)
                    break
        per_keyword.append(
            {
                "keyword": kw,
                "organic_count": len(organic),
                "big_brand_count": len(big_brand_hosts),
                "big_brand_pct": (
                    round(len(big_brand_hosts) / len(organic) * 100, 1)
                    if organic else 0
                ),
                "big_brand_hosts": big_brand_hosts[:5],
            }
        )
        total_slots += len(organic)
        total_big_brand += len(big_brand_hosts)

    if total_slots == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P0-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no non-brand SERPs with organic results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no eligible SERPs"],
        )

    aggregate_pct = round(total_big_brand / total_slots * 100, 1)
    dominated_keywords = [p for p in per_keyword if p["big_brand_pct"] >= 50]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="<=30% of total top-10 slots across queried SERPs occupied by big-brand authority hosts",
        passed=aggregate_pct <= 30,
        evidence={
            "total_slots": total_slots,
            "total_big_brand_slots": total_big_brand,
            "aggregate_big_brand_pct": aggregate_pct,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<=25% of queried keywords are big-brand-dominated SERPs (>=50% big-brand share)",
        passed=(
            len(dominated_keywords) / len(per_keyword) <= 0.25
            if per_keyword else True
        ),
        evidence={
            "dominated_count": len(dominated_keywords),
            "dominated_pct": (
                round(len(dominated_keywords) / len(per_keyword) * 100, 1)
                if per_keyword else 0
            ),
            "dominated_sample": dominated_keywords[:5],
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-18",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "keywords_analysed": len(per_keyword),
            "total_slots": total_slots,
            "total_big_brand_slots": total_big_brand,
            "aggregate_big_brand_pct": aggregate_pct,
            "dominated_keywords": dominated_keywords[:10],
            "per_keyword": per_keyword,
            "note": (
                "Big-brand detection uses a curated authority-host list as a "
                "proxy for high domain authority. True per-domain DR scoring "
                "needs Ahrefs / paid DataForSEO Backlinks (not wired). The "
                "curated list covers Wikipedia, .gov/.edu, tier-1 publications, "
                "major consultancies, and tech giants — common SERP-dominators."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "serp.google.organic",
            "composition.big_brand_share_estimate",
        ],
    )
