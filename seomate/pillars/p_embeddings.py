"""Embedding-driven extractors (H1b composition layer).

Variables that derive their answers from page-level Gemini embeddings
rather than from the cheap-layer DataForSEO + HTML parsing inputs.

Variables operationalised in this module:

- P0-11 — Topic clusters across the site (Probable; threshold-based
            single-link agglomeration over cosine similarity)
- P1-25 — Internal-link anchor text relevance (Consensus; embedding
            similarity between anchor text and target page content,
            with generic-anchor detection as a structural rule)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from seomate.adapters import (
    AdapterContext,
    Embedding,
    EmbeddingsAdapter,
    EmbeddingsNotConfigured,
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

# ─── Tunables ───────────────────────────────────────────────────────────────

# Cosine-similarity threshold for two pages to be in the same topic
# cluster. Empirically, ~0.7 is the practitioner-standard band where
# pages cover meaningfully related content; below 0.5 they're
# different topics.
TOPIC_CLUSTER_SIMILARITY_THRESHOLD = 0.70

# Minimum cluster size to count as a "real" cluster. Singletons are
# kept in evidence but excluded from the cluster count rules.
MIN_CLUSTER_SIZE = 2

# Generic anchors that practitioners flag as zero topical signal.
GENERIC_ANCHOR_PHRASES = frozenset({
    "click here",
    "click here.",
    "here",
    "here.",
    "read more",
    "read more.",
    "learn more",
    "learn more.",
    "more",
    "more info",
    "more information",
    "this page",
    "this article",
    "this post",
    "this link",
    "view",
    "view more",
    "see more",
    "see details",
    "details",
    "find out more",
    "go",
    "go here",
    "link",
    "this",
    "->",
    "→",
})

# Anchor-content cosine similarity threshold for "topical".
# Anchors are short; with embeddings trained for semantic similarity,
# 0.5 is a defensible floor for "topically related" — below it, the
# anchor is unrelated to the destination's content.
ANCHOR_TOPICAL_SIMILARITY_FLOOR = 0.50


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
    subject_type: SubjectType = SubjectType.SITE,
    subject_id: str | None = None,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar=pillar,
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


def _embeddings_unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    pillar: str,
    weight: EvidenceWeight,
    captured_at: datetime,
    *,
    reason: str,
) -> CaptureRecord:
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        pillar=pillar,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": reason,
            "embeddings_configured": site.embeddings_configured,
            "pages_with_text": len(site.text_content),
            "pages_with_embedding": len(site.embeddings),
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["gemini.embed_content", "composition.embedding_similarity"],
        errors=[reason],
    )


# ─── P0-11 — Topic clusters across the site ─────────────────────────────────


def _agglomerative_clusters(
    embeddings: dict[str, Embedding],
    *,
    threshold: float,
) -> list[list[str]]:
    """Single-link agglomeration: pages with cosine ≥ threshold join.

    Pure-Python; runs in O(N²). Fine up to several hundred pages.
    Returns clusters as lists of URLs sorted alphabetically within
    each cluster, and the list of clusters sorted descending by size.
    """
    urls = sorted(embeddings.keys())
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
        va = embeddings[a].vector
        if not va:
            continue
        for b in urls[i + 1:]:
            vb = embeddings[b].vector
            if not vb:
                continue
            if cosine_similarity(va, vb) >= threshold:
                _union(a, b)

    groups: dict[str, list[str]] = {}
    for u in urls:
        groups.setdefault(_find(u), []).append(u)
    clusters = [sorted(g) for g in groups.values()]
    clusters.sort(key=lambda g: (-len(g), g[0]))
    return clusters


def _cluster_label_hint(cluster_urls: list[str]) -> str:
    """Heuristic 'label' from URL paths for clusters until P0-LLM lands."""
    paths = [(urlsplit(u).path or "/").strip("/").split("/") for u in cluster_urls]
    flat = [seg for p in paths for seg in p if seg and len(seg) <= 60]
    counts: dict[str, int] = {}
    for seg in flat:
        counts[seg] = counts.get(seg, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return ", ".join(t for t, _ in top)


@register_extractor("P0-11")
async def capture_p0_11(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P0-11 — Topic clusters across the site (Probable, threshold-clustering).

    Single-link agglomeration over Gemini embedding cosine similarity.
    Threshold is 0.70 — the practitioner-defensible floor for
    "meaningfully related content". Cluster labelling is a placeholder
    URL-path-frequency heuristic until the P0 LLM-labelling layer
    lands in H1c.
    """
    captured_at = _now()
    if not site.embeddings_configured:
        return _embeddings_unmeasurable(
            ctx, site, "P0-11", "P0", EvidenceWeight.PROBABLE, captured_at,
            reason="GEMINI_API_KEY not set; cannot embed page content",
        )
    if len(site.embeddings) < 2:
        return _embeddings_unmeasurable(
            ctx, site, "P0-11", "P0", EvidenceWeight.PROBABLE, captured_at,
            reason="fewer than 2 embedded pages; clustering needs a corpus",
        )

    clusters = _agglomerative_clusters(
        site.embeddings, threshold=TOPIC_CLUSTER_SIMILARITY_THRESHOLD,
    )
    real_clusters = [c for c in clusters if len(c) >= MIN_CLUSTER_SIZE]
    singletons = [c[0] for c in clusters if len(c) == 1]
    pages_in_clusters = sum(len(c) for c in real_clusters)

    cluster_summaries = [
        {
            "size": len(c),
            "label_hint": _cluster_label_hint(c),
            "urls": c,
        }
        for c in real_clusters
    ]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has at least one identifiable topic cluster (>= 2 thematically-related pages)",
        passed=len(real_clusters) >= 1,
        evidence={
            "cluster_count": len(real_clusters),
            "min_cluster_size": MIN_CLUSTER_SIZE,
            "similarity_threshold": TOPIC_CLUSTER_SIMILARITY_THRESHOLD,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=(
            "Majority of pages belong to a topic cluster (>= 50% of embedded "
            "pages cluster with at least one peer)"
        ),
        passed=(
            pages_in_clusters / len(site.embeddings) >= 0.5
            if site.embeddings else False
        ),
        evidence={
            "pages_in_clusters": pages_in_clusters,
            "embedded_pages": len(site.embeddings),
            "singleton_count": len(singletons),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No single mega-cluster swallows the whole site (largest cluster < 80% of pages)",
        passed=(
            (max((len(c) for c in real_clusters), default=0) / len(site.embeddings)) < 0.80
            if site.embeddings else True
        ),
        evidence={
            "largest_cluster_size": max((len(c) for c in real_clusters), default=0),
            "embedded_pages": len(site.embeddings),
        },
        notes=(
            "A site where every page clusters together usually means the "
            "embedding model is picking up boilerplate (header, footer, "
            "shared CTA copy) rather than actual topical differentiation."
        ),
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P0-11",
        pillar="P0",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "embedded_pages": len(site.embeddings),
            "cluster_count": len(real_clusters),
            "singleton_count": len(singletons),
            "pages_in_clusters": pages_in_clusters,
            "largest_cluster_size": max(
                (len(c) for c in real_clusters), default=0
            ),
            "similarity_threshold": TOPIC_CLUSTER_SIMILARITY_THRESHOLD,
            "clusters": cluster_summaries[:25],
            "singletons": singletons[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "gemini.embed_content",
            "composition.threshold_clustering",
        ],
    )


# ─── P1-25 — Internal-link anchor text relevance ────────────────────────────


def _is_generic_anchor(anchor: str) -> bool:
    a = (anchor or "").strip().lower()
    if not a:
        return True
    if a in GENERIC_ANCHOR_PHRASES:
        return True
    # Single word that's a known generic vocabulary item.
    return False


@register_extractor("P1-25")
async def capture_p1_25(
    ctx: AdapterContext,
    site: SiteData,
    *,
    embeddings: EmbeddingsAdapter,
) -> CaptureRecord:
    """P1-25 — Internal-link anchor text relevance (Consensus, embedding match).

    For every internal inbound link in the link graph:
    1. Flag generic-anchor links (\"click here\", \"read more\", etc.).
    2. Embed the anchor text and compare to the target page's content
       embedding via cosine similarity.

    A low average similarity per target signals weak topical anchoring
    — those internal links don't tell Google what the destination is
    about. High generic-anchor share is an independent failure mode.
    """
    captured_at = _now()
    if site.link_graph is None or site.link_graph.page_count == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-25",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no link graph available — HTML prefetch produced no usable pages"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "http.html_fetch",
                "gemini.embed_content",
                "composition.anchor_relevance",
            ],
            errors=["site.link_graph is None or empty"],
        )
    if not site.embeddings_configured:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P1-25",
            pillar="P1",
            captured_at=captured_at,
            status=CaptureStatus.PARTIAL,
            value=_partial_anchor_findings(site),
            rules=[
                RuleResult(
                    rule_id=1,
                    rule_text=(
                        "Generic-anchor share < 30% of internal inbound links "
                        "(fully measurable without embeddings)"
                    ),
                    passed=_partial_anchor_findings(site)["generic_anchor_pct"] < 30.0,
                    evidence=_partial_anchor_findings(site),
                ),
                RuleResult(
                    rule_id=2,
                    rule_text=(
                        "Anchor-to-target topical similarity (embedding-based) — "
                        "DEFERRED, GEMINI_API_KEY not set"
                    ),
                    passed=True,
                    evidence={"method": "deferred_until_GEMINI_API_KEY_set"},
                    notes="Embeddings unavailable; topical similarity scoring is pending.",
                ),
            ],
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "http.html_fetch",
                "composition.generic_anchor_detection",
            ],
            errors=["GEMINI_API_KEY not set; partial measurement only"],
        )

    # Full path: embed every distinct anchor text on top of page content
    # embeddings already cached. We keep one anchor embedding per unique
    # text so we never spend twice on identical anchors.
    anchor_texts: set[str] = set()
    for url in site.link_graph.pages:
        for ref in site.link_graph.inbound_internal(url):
            if ref.anchor_text:
                anchor_texts.add(ref.anchor_text.strip())
    anchor_embeddings: dict[str, Embedding] = {}
    api_errors: list[str] = []
    for text in sorted(anchor_texts):
        try:
            anchor_embeddings[text] = await embeddings.embed(text)
        except EmbeddingsNotConfigured:
            return _embeddings_unmeasurable(
                ctx, site, "P1-25", "P1", EvidenceWeight.CONSENSUS, captured_at,
                reason="GEMINI_API_KEY became unset mid-audit",
            )
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"anchor[{text[:40]}]: {type(exc).__name__}: {exc}")

    per_target: list[dict[str, Any]] = []
    sim_total = 0.0
    sim_count = 0
    generic_count = 0
    inbound_total = 0
    targets_below_floor: list[dict[str, Any]] = []

    for url in sorted(site.link_graph.pages):
        target_emb = site.embeddings.get(url)
        inbound = site.link_graph.inbound_internal(url)
        if not inbound:
            continue
        page_anchors: list[dict[str, Any]] = []
        page_sims: list[float] = []
        page_generic = 0
        for ref in inbound:
            anchor = ref.anchor_text.strip()
            inbound_total += 1
            is_generic = _is_generic_anchor(anchor)
            if is_generic:
                generic_count += 1
                page_generic += 1
            sim: float | None = None
            if target_emb is not None and not is_generic and anchor in anchor_embeddings:
                sim = cosine_similarity(
                    anchor_embeddings[anchor].vector, target_emb.vector
                )
                if sim is not None:
                    page_sims.append(sim)
                    sim_total += sim
                    sim_count += 1
            page_anchors.append(
                {
                    "anchor": anchor[:120],
                    "is_generic": is_generic,
                    "similarity": round(sim, 3) if sim is not None else None,
                    "source": ref.source_url,
                }
            )
        avg_page_sim = sum(page_sims) / len(page_sims) if page_sims else None
        per_target.append(
            {
                "url": url,
                "inbound_count": len(inbound),
                "generic_count": page_generic,
                "avg_anchor_similarity": round(avg_page_sim, 3) if avg_page_sim is not None else None,
                "sample_anchors": page_anchors[:5],
            }
        )
        if avg_page_sim is not None and avg_page_sim < ANCHOR_TOPICAL_SIMILARITY_FLOOR:
            targets_below_floor.append(
                {
                    "url": url,
                    "avg_anchor_similarity": round(avg_page_sim, 3),
                    "sample_anchors": page_anchors[:3],
                }
            )

    avg_sim = sim_total / sim_count if sim_count else 0.0
    generic_pct = (generic_count / inbound_total * 100.0) if inbound_total else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Generic-anchor share < 30% of internal inbound links",
        passed=generic_pct < 30.0,
        evidence={
            "generic_count": generic_count,
            "inbound_total": inbound_total,
            "generic_anchor_pct": round(generic_pct, 1),
            "generic_phrases_checked": sorted(GENERIC_ANCHOR_PHRASES),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=(
            "Average anchor-to-target embedding similarity is topical "
            f"(>= {ANCHOR_TOPICAL_SIMILARITY_FLOOR})"
        ),
        passed=avg_sim >= ANCHOR_TOPICAL_SIMILARITY_FLOOR,
        evidence={
            "avg_anchor_similarity": round(avg_sim, 3),
            "anchors_scored": sim_count,
            "topical_floor": ANCHOR_TOPICAL_SIMILARITY_FLOOR,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No target page has an avg inbound anchor similarity below the topical floor",
        passed=len(targets_below_floor) == 0,
        evidence={
            "targets_below_floor": targets_below_floor[:25],
            "below_floor_count": len(targets_below_floor),
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P1-25",
        pillar="P1",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "inbound_total": inbound_total,
            "generic_count": generic_count,
            "generic_anchor_pct": round(generic_pct, 1),
            "anchors_scored": sim_count,
            "avg_anchor_similarity": round(avg_sim, 3),
            "targets_below_floor_count": len(targets_below_floor),
            "per_target_sample": per_target[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "gemini.embed_content",
            "composition.anchor_relevance",
        ],
        errors=api_errors or None,
    )


def _partial_anchor_findings(site: SiteData) -> dict[str, Any]:
    """Compute the generic-anchor share without embeddings."""
    generic = 0
    total = 0
    if site.link_graph is None:
        return {"generic_count": 0, "inbound_total": 0, "generic_anchor_pct": 0.0}
    for url in site.link_graph.pages:
        for ref in site.link_graph.inbound_internal(url):
            total += 1
            if _is_generic_anchor(ref.anchor_text or ""):
                generic += 1
    pct = (generic / total * 100.0) if total else 0.0
    return {
        "generic_count": generic,
        "inbound_total": total,
        "generic_anchor_pct": round(pct, 1),
    }
