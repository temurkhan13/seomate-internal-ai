"""Pillar 6 — Generative Engine Optimization (GEO) extractors.

GEO is the youngest pillar in the taxonomy and the one with the most
volatile evidence. Most P6 variables either need an LLM call (deferred
to H1c) or paid third-party APIs; the H1a slice we ship here is the
externally-observable subset that needs no auth: entity coverage across
public knowledge bases, robots.txt directives for AI bots, and the
``llms.txt`` declaration file.

Variables operationalised in this module:

- P6-01 — LLM-readable content structure (Consensus; semantic HTML)
- P6-04 — Statistical / numerical specificity (Consensus; regex over text)
- P6-09 — FAQ blocks + schema match (Probable; schema + pattern)
- P6-11 — Entity coverage across Wikipedia / Wikidata / Knowledge Graph
            (Probable; multi-source consensus check.)
- P6-17 — LLM-bot crawler access via robots.txt
            (Consensus; direct robots.txt parse for major AI bot UAs.)
- P6-18 — ``llms.txt`` declaration file presence
            (Speculative; emerging convention proposed by Answer.AI.)
- P6-29 — Knowledge Graph entity completeness
            (Probable; field coverage of the top KG hit.)
- P6-30 — Wikipedia article quality
            (Probable; length / disambiguation / cleanup-template signals.)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from seomate.adapters import (
    AdapterContext,
    KGNotConfigured,
    KGSearchHit,
    KnowledgeGraphAdapter,
    WikidataAdapter,
    WikidataEntity,
    WikipediaAdapter,
    WikipediaArticle,
)
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor
from seomate.pillars.p1_schema import (
    GENERIC_SCHEMA_TYPES,
    HIGH_VALUE_SAMEAS_HOSTS,
    KNOWN_SCHEMA_TYPES,
    _is_homepage as _schema_is_homepage,
)
from seomate.utils.structured_data import SchemaBlock, StructuredData


# ─── Confidence thresholds (mirror P0-16) ───────────────────────────────────

KG_HIGH_CONFIDENCE = 50.0
KG_FUZZY_FLOOR = 5.0

# Wikipedia article-length bands (bytes of wikitext). A genuine
# encyclopaedic article rarely sits below ~2 KB; major brand articles
# typically exceed 10 KB. Stub-class articles (~500–2000 bytes) suggest
# weak coverage even when present.
WIKIPEDIA_STUB_BYTES = 2000
WIKIPEDIA_HEALTHY_BYTES = 10_000

# Cleanup / quality-warning templates that flag editorial concerns.
# We don't enumerate every cleanup template — these are the ones that
# practitioners cite as material signals to LLMs and search engines.
WIKIPEDIA_QUALITY_TEMPLATES = (
    "Template:Notability",
    "Template:Notability (organizations and companies)",
    "Template:Advert",
    "Template:Cleanup",
    "Template:More citations needed",
    "Template:COI",
    "Template:Conflict of interest",
    "Template:Promotional",
    "Template:Refimprove",
    "Template:Unreferenced",
)

# Major LLM-affiliated crawlers we explicitly check for in robots.txt.
# Source: each vendor's published documentation as of 2025-Q4.
LLM_BOT_USER_AGENTS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Applebot-Extended",
    "CCBot",
    "Bytespider",
    "Meta-ExternalAgent",
    "FacebookBot",
    "Amazonbot",
    "Diffbot",
    "Cohere-AI",
    "Cohere-Crawler",
    "Mistral-AI",
)


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
    subject_type: SubjectType = SubjectType.SITE,
    subject_id: str | None = None,
    errors: list[str] | None = None,
    cost_gbp: float = 0.0,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar="P6",
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


def _site_origin(site: SiteData) -> str:
    """Return ``scheme://host`` (no path) for the site's primary URL."""
    parts = urlsplit(site.primary_url)
    return urlunsplit((parts.scheme or "https", parts.netloc, "", "", ""))


# ─── P6-11 — Entity coverage across Wikipedia / Wikidata / Knowledge Graph ──


@register_extractor("P6-11")
async def capture_p6_11(
    ctx: AdapterContext,
    site: SiteData,
    *,
    kg: KnowledgeGraphAdapter,
    wikipedia: WikipediaAdapter,
    wikidata: WikidataAdapter,
) -> CaptureRecord:
    """P6-11 — Entity coverage across Wikipedia, Wikidata, and Google KG.

    For each brand variant, we check three public knowledge bases.
    A brand "fully covered" entity has presence in all three; a brand
    with no presence anywhere is "uncovered". The variable passes when
    every variant resolves in at least two of the three sources, with
    at least one being Wikipedia or Wikidata (the structured-data
    sources LLM training corpora draw most heavily from).
    """
    captured_at = _now()
    brand = site.brand
    if brand is None or not brand.all_variants:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand identity configured for this audit"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "google_kg.entities_search",
                "mediawiki.search",
                "wikidata.search_entities",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name if brand else site.domain,
            errors=["site.brand missing or has no variants"],
        )

    domain = site.domain.lower()
    per_variant: list[dict[str, Any]] = []
    api_errors: list[str] = []

    kg_unconfigured = False

    for variant in brand.all_variants:
        wikipedia_hit: WikipediaArticle | None = None
        wikidata_entity: WikidataEntity | None = None
        kg_top: KGSearchHit | None = None

        # Wikipedia: search, then fetch the top hit's article metadata.
        try:
            w_hits = await wikipedia.search(variant, limit=3)
            if w_hits:
                wikipedia_hit = await wikipedia.get_article(w_hits[0].title)
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"wikipedia/{variant}: {type(exc).__name__}: {exc}")

        # Wikidata: search Q-ids, then fetch the top entity's properties.
        try:
            qids = await wikidata.search(variant, limit=3)
            if qids:
                wikidata_entity = await wikidata.get_entity(qids[0])
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"wikidata/{variant}: {type(exc).__name__}: {exc}")

        # Knowledge Graph: keep the top hit and band it.
        try:
            kg_hits = await kg.search(variant, limit=3)
            kg_top = kg_hits[0] if kg_hits else None
        except KGNotConfigured:
            kg_unconfigured = True
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"kg/{variant}: {type(exc).__name__}: {exc}")

        # Decide whether each source counts as a real, brand-aligned hit.
        has_wikipedia = bool(
            wikipedia_hit
            and not wikipedia_hit.is_disambiguation
            and not wikipedia_hit.is_redirect
        )
        has_wikidata = wikidata_entity is not None
        has_kg = kg_top is not None and kg_top.result_score >= KG_HIGH_CONFIDENCE
        kg_fuzzy = (
            kg_top is not None
            and KG_FUZZY_FLOOR <= kg_top.result_score < KG_HIGH_CONFIDENCE
        )

        # Light domain match check on KG so unrelated entities don't
        # accidentally count toward coverage.
        kg_domain_match = False
        if kg_top is not None:
            url_blob = " ".join(
                str(s) for s in (kg_top.url, *kg_top.same_as) if s
            ).lower()
            kg_domain_match = domain in url_blob

        per_variant.append(
            {
                "variant": variant,
                "wikipedia": {
                    "present": has_wikipedia,
                    "title": wikipedia_hit.title if wikipedia_hit else None,
                    "url": wikipedia_hit.url if wikipedia_hit else None,
                    "length_bytes": wikipedia_hit.length_bytes if wikipedia_hit else 0,
                    "is_disambiguation": wikipedia_hit.is_disambiguation
                    if wikipedia_hit
                    else False,
                },
                "wikidata": {
                    "present": has_wikidata,
                    "qid": wikidata_entity.qid if wikidata_entity else None,
                    "label": wikidata_entity.label if wikidata_entity else None,
                    "sitelinks_count": wikidata_entity.sitelinks_count
                    if wikidata_entity
                    else 0,
                },
                "knowledge_graph": {
                    "present": has_kg,
                    "fuzzy": kg_fuzzy,
                    "domain_match": kg_domain_match,
                    "top_score": kg_top.result_score if kg_top else 0.0,
                    "kg_id": kg_top.kg_id if kg_top else None,
                    "name": kg_top.name if kg_top else None,
                    "configured": not kg_unconfigured,
                },
                "sources_present_count": int(has_wikipedia)
                + int(has_wikidata)
                + int(has_kg),
            }
        )

    # If KG is the only source we could ever query and it's unconfigured,
    # the variable is unmeasurable.
    if (
        kg_unconfigured
        and not any(v["wikipedia"]["present"] for v in per_variant)
        and not any(v["wikidata"]["present"] for v in per_variant)
    ):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "GOOGLE_KG_API_KEY not set and no Wikipedia/Wikidata "
                    "presence found; coverage cannot be assessed."
                ),
                "per_variant": per_variant,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "google_kg.entities_search",
                "mediawiki.search",
                "wikidata.search_entities",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name,
            errors=api_errors or None,
        )

    has_any_wikipedia = any(v["wikipedia"]["present"] for v in per_variant)
    has_any_wikidata = any(v["wikidata"]["present"] for v in per_variant)
    has_any_kg = any(v["knowledge_graph"]["present"] for v in per_variant)
    structured_present = has_any_wikipedia or has_any_wikidata
    sources_present = sum([has_any_wikipedia, has_any_wikidata, has_any_kg])

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Brand has presence in at least two of {Wikipedia, Wikidata, Knowledge Graph}",
        passed=sources_present >= 2,
        evidence={
            "wikipedia_present": has_any_wikipedia,
            "wikidata_present": has_any_wikidata,
            "knowledge_graph_present": has_any_kg,
            "sources_present_count": sources_present,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one structured source (Wikipedia or Wikidata) covers the brand",
        passed=structured_present,
        evidence={
            "wikipedia_present": has_any_wikipedia,
            "wikidata_present": has_any_wikidata,
        },
        notes=(
            "Wikipedia/Wikidata coverage matters disproportionately because "
            "their structured content is heavily weighted in LLM pre-training."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No source returns only a disambiguation page or homonym match for the brand",
        passed=all(
            not v["wikipedia"]["is_disambiguation"] for v in per_variant
        ),
        evidence={
            "disambiguation_hits": [
                v["variant"]
                for v in per_variant
                if v["wikipedia"]["is_disambiguation"]
            ],
        },
    )

    overall_pass = rule_1.passed and rule_2.passed
    status = CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-11",
        captured_at=captured_at,
        status=status,
        value={
            "brand": brand.name,
            "variants_queried": list(brand.all_variants),
            "sources_present": {
                "wikipedia": has_any_wikipedia,
                "wikidata": has_any_wikidata,
                "knowledge_graph": has_any_kg,
            },
            "sources_present_count": sources_present,
            "kg_configured": not kg_unconfigured,
            "per_variant": per_variant,
        },
        rules=[rule_1, rule_2, rule_3],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "google_kg.entities_search",
            "mediawiki.search",
            "mediawiki.get_article",
            "wikidata.search_entities",
            "wikidata.get_entities",
        ],
        subject_type=SubjectType.BRAND,
        subject_id=brand.name,
        errors=api_errors or None,
    )


# ─── P6-17 — LLM-bot crawler access via robots.txt ──────────────────────────


def _parse_robots_txt(text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse robots.txt into ``{user_agent: [(directive, value), ...]}``.

    Comments and blank lines are skipped. Directives that come before
    any User-agent line bind to the synthetic group ``""``.
    Group names are case-folded; values keep original case.
    """
    groups: dict[str, list[tuple[str, str]]] = {"": []}
    current: list[str] = [""]
    pending_uas: list[str] = []
    in_rules = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key_l = key.strip().lower()
        value = value.strip()
        if key_l == "user-agent":
            if in_rules:
                # New group block starts after a previous rule run.
                pending_uas = []
                in_rules = False
            ua = value.lower()
            pending_uas.append(ua)
            groups.setdefault(ua, [])
            current = pending_uas[:]
        else:
            in_rules = True
            for ua in current or [""]:
                groups.setdefault(ua, []).append((key_l, value))
    return groups


def _classify_bot_access(
    bot: str,
    groups: dict[str, list[tuple[str, str]]],
) -> dict[str, Any]:
    """Classify how robots.txt treats ``bot``.

    Returns ``{"matched_group", "blocked", "allowed_paths", "disallowed_paths"}``.
    A bot is "blocked" iff it has a Disallow: / against either its
    explicit UA group or the wildcard ``*`` group with no overriding
    Allow. We don't try to model RFC 9309 conflict resolution
    fully — for the H1a check we only need the headline status.
    """
    bot_l = bot.lower()
    matched = bot_l if bot_l in groups else "*" if "*" in groups else None
    rules = groups.get(matched, []) if matched else []
    disallowed = [v for k, v in rules if k == "disallow"]
    allowed = [v for k, v in rules if k == "allow"]
    blocked_root = "/" in disallowed and not any(p == "/" for p in allowed)
    return {
        "matched_group": matched,
        "blocked": blocked_root,
        "disallowed_paths": disallowed,
        "allowed_paths": allowed,
    }


@register_extractor("P6-17")
async def capture_p6_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-17 — LLM-bot crawler access via robots.txt.

    We fetch ``/robots.txt`` directly (no adapter — this is the most
    fundamental crawl-control file and we want to record the literal
    bytes the site serves). We then classify each major LLM-affiliated
    crawler as ``allowed`` / ``blocked`` / ``not_mentioned``.

    Recorded as Consensus because robots.txt parsing is RFC-defined
    (RFC 9309) and the bot user agents themselves are documented by
    each vendor.
    """
    captured_at = _now()
    origin = _site_origin(site)
    robots_url = f"{origin}/robots.txt"

    fetched_text: str | None = None
    fetch_status: int | None = None
    fetch_error: str | None = None

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(robots_url)
            fetch_status = resp.status_code
            if 200 <= resp.status_code < 300:
                fetched_text = resp.text
    except Exception as exc:  # noqa: BLE001
        fetch_error = f"{type(exc).__name__}: {exc}"

    if fetched_text is None:
        # Per RFC 9309, a missing robots.txt means "everything is allowed".
        # We record the variable as PASSED in that case but flag the
        # absence in evidence.
        rule_1 = RuleResult(
            rule_id=1,
            rule_text="A robots.txt is served (HTTP 2xx)",
            passed=False,
            evidence={
                "robots_url": robots_url,
                "status_code": fetch_status,
                "fetch_error": fetch_error,
            },
            notes=(
                "Per RFC 9309 a missing robots.txt grants full access to all "
                "crawlers, so absence is not a fail for LLM accessibility — "
                "but it is recorded so practitioners can decide whether to "
                "add explicit directives."
            ),
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-17",
            captured_at=captured_at,
            status=CaptureStatus.PASSED,
            value={
                "robots_url": robots_url,
                "robots_present": False,
                "status_code": fetch_status,
                "fetch_error": fetch_error,
                "implication": "all_crawlers_allowed_by_default",
            },
            rules=[rule_1],
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.robots_txt"],
        )

    groups = _parse_robots_txt(fetched_text)
    per_bot: list[dict[str, Any]] = []
    blocked_bots: list[str] = []
    for bot in LLM_BOT_USER_AGENTS:
        result = _classify_bot_access(bot, groups)
        per_bot.append({"bot": bot, **result})
        if result["blocked"]:
            blocked_bots.append(bot)

    # Wildcard treatment matters as a fallback — if `*` is blocked then
    # every bot without an explicit Allow is blocked too.
    wildcard = _classify_bot_access("*", groups)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="A robots.txt is served (HTTP 2xx)",
        passed=True,
        evidence={"robots_url": robots_url, "status_code": fetch_status},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No major LLM-affiliated crawler is blocked at the site root",
        passed=len(blocked_bots) == 0,
        evidence={
            "blocked_bots": blocked_bots,
            "blocked_count": len(blocked_bots),
            "checked_bots": list(LLM_BOT_USER_AGENTS),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Wildcard (*) group does not block site root",
        passed=not wildcard["blocked"],
        evidence={"wildcard": wildcard},
        notes=(
            "Practitioners flag wildcard-block configurations because "
            "they unintentionally block any LLM bot the site hasn't "
            "explicitly allowed."
        ),
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "robots_url": robots_url,
            "robots_present": True,
            "status_code": fetch_status,
            "robots_size_bytes": len(fetched_text),
            "user_agent_groups": sorted(groups.keys()),
            "wildcard": wildcard,
            "per_bot": per_bot,
            "blocked_bot_count": len(blocked_bots),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.robots_txt"],
    )


# ─── P6-18 — llms.txt declaration file ──────────────────────────────────────


@register_extractor("P6-18")
async def capture_p6_18(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-18 — Presence and shape of an ``llms.txt`` declaration file.

    ``llms.txt`` is a proposed convention (Answer.AI, 2024) for sites to
    expose an LLM-friendly summary of their content. There is no formal
    spec yet — we treat it as Speculative and only record presence,
    shape, and a few markdown-ish heuristics. The variable cannot fail
    in a meaningful sense; it produces an advisory record.
    """
    captured_at = _now()
    origin = _site_origin(site)
    llms_url = f"{origin}/llms.txt"
    llms_full_url = f"{origin}/llms-full.txt"

    async def _fetch(url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"
                },
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
            return {
                "url": url,
                "status_code": resp.status_code,
                "present": 200 <= resp.status_code < 300,
                "content_type": resp.headers.get("content-type"),
                "size_bytes": len(resp.content) if resp.content else 0,
                "first_line": (
                    resp.text.splitlines()[0][:200]
                    if resp.text and 200 <= resp.status_code < 300
                    else None
                ),
                "fetch_error": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "url": url,
                "status_code": None,
                "present": False,
                "content_type": None,
                "size_bytes": 0,
                "first_line": None,
                "fetch_error": f"{type(exc).__name__}: {exc}",
            }

    main = await _fetch(llms_url)
    full = await _fetch(llms_full_url)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="/llms.txt is served (HTTP 2xx)",
        passed=bool(main["present"]),
        evidence=main,
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="/llms-full.txt extended file is served (optional)",
        passed=True,
        evidence=full,
        notes="Optional companion file; absence is not a defect.",
    )

    # Speculative variables don't pass/fail in the strong sense; we mark
    # status PASSED whenever we successfully captured (the file exists
    # OR we confirmed it doesn't), and PARTIAL only when the fetch itself
    # crashed.
    if main["fetch_error"] and full["fetch_error"]:
        status = CaptureStatus.PARTIAL
    else:
        status = CaptureStatus.PASSED

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-18",
        captured_at=captured_at,
        status=status,
        value={
            "llms_txt": main,
            "llms_full_txt": full,
            "any_present": bool(main["present"] or full["present"]),
        },
        rules=[rule_1, rule_2],
        evidence_weight=EvidenceWeight.SPECULATIVE,
        data_sources=["http.llms_txt"],
        errors=[
            e
            for e in (main["fetch_error"], full["fetch_error"])
            if e
        ]
        or None,
    )


# ─── P6-29 — Knowledge Graph entity completeness ────────────────────────────


def _kg_field_coverage(hit: KGSearchHit) -> dict[str, bool]:
    """Map the KG fields we care about to whether they're populated."""
    return {
        "name": bool(hit.name),
        "description": bool(hit.description),
        "detailed_description": bool(hit.detailed_description),
        "image": bool(hit.image_url),
        "url": bool(hit.url),
        "types": bool(hit.types),
        "same_as": bool(hit.same_as),
    }


@register_extractor("P6-29")
async def capture_p6_29(
    ctx: AdapterContext,
    site: SiteData,
    *,
    kg: KnowledgeGraphAdapter,
) -> CaptureRecord:
    """P6-29 — Field coverage of the brand's Knowledge Graph entity.

    A confident-match KG entity should expose name, description,
    detailed description, image, types, and at least one external
    same-as link. Partial coverage is common for small brands and is
    interpreted as a content-graph completeness gap.
    """
    captured_at = _now()
    brand = site.brand
    if brand is None or not brand.all_variants:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-29",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand identity configured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["google_kg.entities_search"],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name if brand else site.domain,
            errors=["site.brand missing or has no variants"],
        )

    best: KGSearchHit | None = None
    best_variant: str | None = None
    api_errors: list[str] = []

    for variant in brand.all_variants:
        try:
            hits = await kg.search(variant, limit=3)
        except KGNotConfigured as exc:
            return _build_record(
                ctx=ctx,
                site=site,
                variable_id="P6-29",
                captured_at=captured_at,
                status=CaptureStatus.UNMEASURABLE,
                value={
                    "reason": "GOOGLE_KG_API_KEY not set; cannot query Knowledge Graph",
                },
                rules=None,
                evidence_weight=EvidenceWeight.PROBABLE,
                data_sources=["google_kg.entities_search"],
                subject_type=SubjectType.BRAND,
                subject_id=brand.name,
                errors=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"{variant}: {type(exc).__name__}: {exc}")
            continue

        for hit in hits:
            if hit.result_score >= KG_HIGH_CONFIDENCE and (
                best is None or hit.result_score > best.result_score
            ):
                best = hit
                best_variant = variant

    if best is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-29",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no high-confidence Knowledge Graph entity to evaluate completeness against",
                "variants_queried": list(brand.all_variants),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["google_kg.entities_search"],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name,
            errors=api_errors or None,
        )

    coverage = _kg_field_coverage(best)
    populated = sum(1 for v in coverage.values() if v)
    expected = len(coverage)
    pct = populated / expected * 100.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Core descriptive fields (name, description, types) are populated",
        passed=coverage["name"] and coverage["description"] and coverage["types"],
        evidence=coverage,
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Extended fields (detailed_description, image, sameAs) are populated",
        passed=all(
            coverage[k]
            for k in ("detailed_description", "image", "same_as")
        ),
        evidence={
            k: coverage[k]
            for k in ("detailed_description", "image", "same_as")
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text=">= 80% of evaluated fields are populated overall",
        passed=pct >= 80.0,
        evidence={
            "fields_populated": populated,
            "fields_expected": expected,
            "fields_pct": round(pct, 1),
        },
    )

    overall_pass = rule_1.passed and rule_3.passed
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-29",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "brand": brand.name,
            "matched_variant": best_variant,
            "kg_id": best.kg_id,
            "name": best.name,
            "result_score": best.result_score,
            "field_coverage": coverage,
            "fields_populated": populated,
            "fields_expected": expected,
            "fields_pct": round(pct, 1),
        },
        rules=[rule_1, rule_2, rule_3],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["google_kg.entities_search"],
        subject_type=SubjectType.BRAND,
        subject_id=brand.name,
        errors=api_errors or None,
    )


# ─── P6-30 — Wikipedia article quality ──────────────────────────────────────


@register_extractor("P6-30")
async def capture_p6_30(
    ctx: AdapterContext,
    site: SiteData,
    *,
    wikipedia: WikipediaAdapter,
) -> CaptureRecord:
    """P6-30 — Quality of the brand's Wikipedia article.

    Recorded as Probable because article length, disambiguation status,
    and presence of cleanup templates are observable proxies for the
    content's reliability and authority — but the relationship to LLM
    citation rates is correlational, not causal.
    """
    captured_at = _now()
    brand = site.brand
    if brand is None or not brand.all_variants:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-30",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no brand identity configured"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["mediawiki.search", "mediawiki.get_article"],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name if brand else site.domain,
            errors=["site.brand missing or has no variants"],
        )

    best: WikipediaArticle | None = None
    best_variant: str | None = None
    api_errors: list[str] = []

    for variant in brand.all_variants:
        try:
            hits = await wikipedia.search(variant, limit=3)
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"search/{variant}: {type(exc).__name__}: {exc}")
            continue
        for hit in hits:
            try:
                article = await wikipedia.get_article(hit.title)
            except Exception as exc:  # noqa: BLE001
                api_errors.append(
                    f"get_article/{hit.title}: {type(exc).__name__}: {exc}"
                )
                continue
            if article is None:
                continue
            if article.is_disambiguation:
                continue
            if best is None or article.length_bytes > best.length_bytes:
                best = article
                best_variant = variant

    if best is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-30",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no non-disambiguation Wikipedia article found for any brand variant",
                "variants_queried": list(brand.all_variants),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["mediawiki.search", "mediawiki.get_article"],
            subject_type=SubjectType.BRAND,
            subject_id=brand.name,
            errors=api_errors or None,
        )

    quality_templates_present = sorted(
        t for t in best.templates if t in WIKIPEDIA_QUALITY_TEMPLATES
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Article exceeds the stub threshold (length >= 2000 bytes of wikitext)",
        passed=best.length_bytes >= WIKIPEDIA_STUB_BYTES,
        evidence={
            "length_bytes": best.length_bytes,
            "stub_threshold": WIKIPEDIA_STUB_BYTES,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Article reaches the healthy-coverage threshold (length >= 10000 bytes)",
        passed=best.length_bytes >= WIKIPEDIA_HEALTHY_BYTES,
        evidence={
            "length_bytes": best.length_bytes,
            "healthy_threshold": WIKIPEDIA_HEALTHY_BYTES,
        },
        notes=(
            "10 KB is a heuristic floor for an article that covers the "
            "brand substantively rather than as a passing mention."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Article is not flagged with editorial cleanup templates (notability, advert, COI, etc.)",
        passed=len(quality_templates_present) == 0,
        evidence={
            "quality_templates_present": quality_templates_present,
            "templates_checked": list(WIKIPEDIA_QUALITY_TEMPLATES),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Article is not a redirect or disambiguation page",
        passed=not best.is_redirect and not best.is_disambiguation,
        evidence={
            "is_redirect": best.is_redirect,
            "is_disambiguation": best.is_disambiguation,
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = rule_1.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-30",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "brand": brand.name,
            "matched_variant": best_variant,
            "title": best.title,
            "url": best.url,
            "language": best.language,
            "length_bytes": best.length_bytes,
            "is_redirect": best.is_redirect,
            "is_disambiguation": best.is_disambiguation,
            "last_edited": best.last_edited,
            "quality_templates_present": quality_templates_present,
            "wikidata_qid": best.pageprops.get("wikibase_item"),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["mediawiki.search", "mediawiki.get_article"],
        subject_type=SubjectType.BRAND,
        subject_id=brand.name,
        errors=api_errors or None,
    )


# ─── Schema graph helpers (shared by P6-19 and P6-20) ───────────────────────


def _from_https(host_or_url: str) -> str:
    """Lower-case netloc / domain for a same-as URL match."""
    s = host_or_url.lower().strip()
    for prefix in ("https://", "http://", "//"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.split("/", 1)[0]


def _sameas_hosts(values: Any) -> list[str]:
    """Flatten the sameAs property into a list of hostnames."""
    out: list[str] = []
    if isinstance(values, str):
        out.append(_from_https(values))
    elif isinstance(values, list):
        for v in values:
            if isinstance(v, str):
                out.append(_from_https(v))
    return out


def _has_specific_page_type(types: set[str]) -> bool:
    """A non-generic page-type schema is present (Article, Product, Recipe, ...)."""
    non_generic = types - GENERIC_SCHEMA_TYPES
    return bool(non_generic & KNOWN_SCHEMA_TYPES)


# ─── P6-19 — Schema.org structured data depth ───────────────────────────────


@register_extractor("P6-19")
async def capture_p6_19(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-19 — Site-wide schema graph depth (Consensus, 8 rules).

    Depth = the schema isn't just "an Organization block on the
    homepage" — it spans the site (Organization/Person on every page),
    declares specific page types, links pages via BreadcrumbList,
    references the entity layer via sameAs, and composes via @graph.
    """
    captured_at = _now()
    pages = [
        sd
        for url, sd in site.structured_data.items()
        if (
            site.html_pages.get(url) is not None
            and site.html_pages[url].fetch_error is None
            and site.html_pages[url].status_code < 400
        )
    ]
    if not pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no successfully-fetched HTML pages available",
                "html_pages_total": len(site.html_pages),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "extruct.parse_structured_data"],
            errors=["no HTML pages available"],
        )

    pages_with_org: list[str] = []
    pages_without_org: list[str] = []
    pages_with_specific_type: list[str] = []
    pages_without_specific_type: list[str] = []
    non_homepage = [p for p in pages if not _schema_is_homepage(p.url, site)]
    pages_with_breadcrumb: list[str] = []
    pages_without_breadcrumb: list[str] = []
    pages_with_graph_linkage: list[str] = []
    sameas_present_blocks: list[dict[str, Any]] = []
    mentions_present_blocks: list[dict[str, Any]] = []
    pages_with_parse_errors: list[str] = []

    org_or_person_types = {"Organization", "Corporation", "LocalBusiness", "Person"}

    for page in pages:
        types = set(page.all_types)
        if types & org_or_person_types:
            pages_with_org.append(page.url)
        else:
            pages_without_org.append(page.url)

        if _has_specific_page_type(types):
            pages_with_specific_type.append(page.url)
        else:
            pages_without_specific_type.append(page.url)

        if page.graph_refs:
            pages_with_graph_linkage.append(page.url)

        if not _schema_is_homepage(page.url, site):
            if page.blocks_of_type("BreadcrumbList"):
                pages_with_breadcrumb.append(page.url)
            else:
                pages_without_breadcrumb.append(page.url)

        if page.json_ld_parse_errors:
            pages_with_parse_errors.append(page.url)

        for block in page.schema_org_blocks:
            sa_hosts = _sameas_hosts(block.raw.get("sameAs"))
            if sa_hosts:
                sameas_present_blocks.append(
                    {
                        "url": page.url,
                        "types": list(block.types),
                        "sameAs_hosts": sa_hosts,
                        "high_value_count": sum(
                            1
                            for h in sa_hosts
                            if any(hv in h for hv in HIGH_VALUE_SAMEAS_HOSTS)
                        ),
                    }
                )
            mentions = block.raw.get("mentions")
            if mentions:
                mentions_present_blocks.append(
                    {
                        "url": page.url,
                        "types": list(block.types),
                        "mention_count": len(mentions) if isinstance(mentions, list) else 1,
                    }
                )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Organization (or Person) schema present on every page",
        passed=len(pages_without_org) == 0,
        evidence={
            "pages_with_org": len(pages_with_org),
            "pages_without_org": pages_without_org,
            "pages_total": len(pages),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Each substantive page declares a specific page-type schema (not bare WebPage)",
        passed=len(pages_without_specific_type) == 0,
        evidence={
            "pages_with_specific_type": len(pages_with_specific_type),
            "pages_without_specific_type": pages_without_specific_type,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="BreadcrumbList present on every non-homepage URL",
        passed=(
            len(pages_without_breadcrumb) == 0 if non_homepage else True
        ),
        evidence={
            "non_homepage_total": len(non_homepage),
            "with_breadcrumb": len(pages_with_breadcrumb),
            "without_breadcrumb": pages_without_breadcrumb,
        },
        notes=(
            "Pass-through when only homepage is present in the audit set."
            if not non_homepage
            else None
        ),
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Bylined content carries Author Person schema (deferred to per-article scan)",
        passed=True,
        evidence={"method": "deferred_to_article_scan_in_h1b"},
        notes=(
            "Detection of bylined content requires an article-vs-marketing "
            "page classifier; deferred to H1b composition layer."
        ),
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="@graph composition links related entities on a page",
        passed=len(pages_with_graph_linkage) > 0,
        evidence={
            "pages_with_graph_refs": len(pages_with_graph_linkage),
            "pages_total": len(pages),
        },
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="sameAs / mentions populated on entity blocks",
        passed=len(sameas_present_blocks) > 0,
        evidence={
            "sameas_blocks": len(sameas_present_blocks),
            "mentions_blocks": len(mentions_present_blocks),
            "high_value_sameas_count": sum(
                int(b["high_value_count"] > 0) for b in sameas_present_blocks
            ),
        },
    )
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="Schema parses without errors site-wide",
        passed=len(pages_with_parse_errors) == 0,
        evidence={
            "pages_with_parse_errors": pages_with_parse_errors,
            "pages_total": len(pages),
        },
    )
    rule_8 = _p6_19_schema_visible_match_rule(site)
    llm_conclusive = bool(rule_8.evidence.get("conclusive", True))

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6, rule_7, rule_8]
    # Hard rules: 1, 2, 3, 5, 6, 7, 8 (rule 8 is LLM-backed and conditional).
    overall_pass = (
        rule_1.passed
        and rule_2.passed
        and rule_3.passed
        and rule_5.passed
        and rule_6.passed
        and rule_7.passed
        # Rule 8 is LLM-backed and only counts when it reached a conclusive
        # verdict; otherwise it is excluded and the capture degrades to PARTIAL,
        # so an LLM outage can never manufacture a clean PASS.
        and (rule_8.passed if llm_conclusive else True)
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-19",
        captured_at=captured_at,
        # A deterministic failure is still a genuine failure, but we cannot claim
        # a full PASS while an LLM-backed rule went unevaluated.
        status=(
            (CaptureStatus.PASSED if llm_conclusive else CaptureStatus.PARTIAL)
            if overall_pass
            else CaptureStatus.FAILED
        ),
        value={
            "schema_visible_match_conclusive": llm_conclusive,
            "pages_total": len(pages),
            "pages_with_org": len(pages_with_org),
            "pages_with_specific_type": len(pages_with_specific_type),
            "non_homepage_pages": len(non_homepage),
            "pages_with_breadcrumb": len(pages_with_breadcrumb),
            "pages_with_graph_linkage": len(pages_with_graph_linkage),
            "blocks_with_sameas": len(sameas_present_blocks),
            "blocks_with_mentions": len(mentions_present_blocks),
            "pages_with_parse_errors": len(pages_with_parse_errors),
            "sameas_findings": sameas_present_blocks[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.schema_graph_depth",
        ],
    )


# ─── P6-20 — Author and organisation entity markup ──────────────────────────


_ABOUT_CONTACT_PATH_HINTS = ("about", "team", "contact", "company", "who-we-are")


def _path_hint(url: str) -> str:
    return (urlsplit(url).path or "/").lower()


def _is_about_or_contact(url: str) -> bool:
    p = _path_hint(url)
    return any(h in p for h in _ABOUT_CONTACT_PATH_HINTS)


@register_extractor("P6-20")
async def capture_p6_20(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-20 — Author / Organization entity markup (Consensus, 8 rules).

    Operates over the parsed structured-data view. Where rules need
    site-wide context we don't have (bylined-article detection, KG
    cross-reference), the rule is recorded as deferred to H1b/H1c
    rather than auto-passed.
    """
    captured_at = _now()
    pages = [
        sd
        for url, sd in site.structured_data.items()
        if (
            site.html_pages.get(url) is not None
            and site.html_pages[url].fetch_error is None
            and site.html_pages[url].status_code < 400
        )
    ]
    if not pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-20",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "extruct.parse_structured_data"],
            subject_type=SubjectType.BRAND,
            subject_id=site.brand.name if site.brand else site.domain,
            errors=["no HTML pages available"],
        )

    organisation_blocks: list[tuple[str, SchemaBlock]] = []
    person_blocks: list[tuple[str, SchemaBlock]] = []
    for page in pages:
        for block in page.schema_org_blocks:
            type_set = set(block.types)
            if type_set & {"Organization", "Corporation", "LocalBusiness"}:
                organisation_blocks.append((page.url, block))
            if "Person" in type_set:
                person_blocks.append((page.url, block))

    about_pages = [p for p in pages if _is_about_or_contact(p.url)]
    org_on_about = [
        url
        for url, _ in organisation_blocks
        if _is_about_or_contact(url) or _schema_is_homepage(url, site)
    ]

    org_ids = {
        block.raw.get("@id")
        for _, block in organisation_blocks
        if isinstance(block.raw.get("@id"), str)
    }
    org_with_id_count = len(org_ids)

    sameas_quality: list[dict[str, Any]] = []
    high_value_sameas_present = False
    description_present_count = 0
    knowsabout_present_count = 0
    worksfor_linkage_count = 0
    kg_mid_present = False

    for url, block in organisation_blocks + person_blocks:
        sa_hosts = _sameas_hosts(block.raw.get("sameAs"))
        if sa_hosts:
            high_value = [
                h for h in sa_hosts
                if any(hv in h for hv in HIGH_VALUE_SAMEAS_HOSTS)
            ]
            if high_value:
                high_value_sameas_present = True
            sameas_quality.append(
                {
                    "url": url,
                    "block_types": list(block.types),
                    "sameAs_hosts": sa_hosts,
                    "high_value_hosts": high_value,
                }
            )
            for h in sa_hosts:
                if "google.com" in h and "kgmid" in h:
                    kg_mid_present = True
        if isinstance(block.raw.get("description"), str) and block.raw["description"].strip():
            description_present_count += 1
        if block.raw.get("knowsAbout"):
            knowsabout_present_count += 1
        if block.raw.get("worksFor"):
            worksfor_linkage_count += 1

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=(
            "Organization schema lives on the homepage / About / Contact pages "
            "with consistent @id"
        ),
        passed=bool(organisation_blocks) and (org_with_id_count >= 1 or len(organisation_blocks) == 1),
        evidence={
            "organisation_blocks_total": len(organisation_blocks),
            "organisation_blocks_with_id": org_with_id_count,
            "about_or_contact_pages_audited": len(about_pages),
            "org_blocks_on_homepage_or_about": len(org_on_about),
            "consistent_id_count": len(org_ids),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Author Person schema on bylined content (deferred to article scan)",
        passed=True,
        evidence={
            "method": "deferred_to_h1b_article_scan",
            "person_blocks_seen": len(person_blocks),
        },
        notes="Detection of bylined-article subset deferred to H1b.",
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Author bio page exists with ProfilePage + Person schema",
        passed=True,
        evidence={"method": "deferred_to_h1b_article_scan"},
        notes="Author bio page detection deferred to H1b.",
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="sameAs is rich and includes high-authority profiles (LinkedIn / Wikipedia / Wikidata / etc.)",
        passed=high_value_sameas_present,
        evidence={
            "blocks_with_sameas": len(sameas_quality),
            "high_value_sameas_present": high_value_sameas_present,
            "high_value_hosts_checked": list(HIGH_VALUE_SAMEAS_HOSTS),
            "sample": sameas_quality[:10],
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Person / Organization include a disambiguating description",
        passed=description_present_count > 0 if (organisation_blocks or person_blocks) else False,
        evidence={
            "blocks_with_description": description_present_count,
            "blocks_total": len(organisation_blocks) + len(person_blocks),
        },
    )
    rule_6 = RuleResult(
        rule_id=6,
        rule_text="worksFor / member linkage between Person and Organization (advisory)",
        passed=True,
        evidence={
            "worksfor_linkage_count": worksfor_linkage_count,
            "person_blocks_seen": len(person_blocks),
        },
        notes="Advisory: only fails when bylined content is detectable; deferred.",
    )
    rule_7 = RuleResult(
        rule_id=7,
        rule_text="knowsAbout populated for Person blocks where present",
        passed=(
            knowsabout_present_count > 0
            if person_blocks
            else True
        ),
        evidence={
            "knowsabout_count": knowsabout_present_count,
            "person_blocks_seen": len(person_blocks),
        },
        notes="Pass-through when no Person blocks are present in the audit set.",
    )
    rule_8 = RuleResult(
        rule_id=8,
        rule_text="Entity sameAs includes Knowledge Graph MID URL where applicable",
        passed=True,
        evidence={
            "kg_mid_present": kg_mid_present,
            "method": "passive_check_against_kg_id_url_pattern",
        },
        notes=(
            "KG cross-reference is advisory: many SMBs have no KG entity, "
            "so absence is not a fail."
        ),
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5, rule_6, rule_7, rule_8]
    # Hard rules: 1, 4, 5.
    overall_pass = rule_1.passed and rule_4.passed and rule_5.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-20",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "organisation_blocks_total": len(organisation_blocks),
            "person_blocks_total": len(person_blocks),
            "blocks_with_high_value_sameas": sum(
                1 for q in sameas_quality if q["high_value_hosts"]
            ),
            "blocks_with_description": description_present_count,
            "blocks_with_knowsabout": knowsabout_present_count,
            "blocks_with_worksfor": worksfor_linkage_count,
            "kg_mid_referenced": kg_mid_present,
            "sameas_findings": sameas_quality[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "http.html_fetch",
            "extruct.parse_structured_data",
            "composition.author_org_entity_markup",
        ],
        subject_type=SubjectType.BRAND,
        subject_id=site.brand.name if site.brand else site.domain,
    )


def _p6_19_schema_visible_match_rule(site: SiteData) -> RuleResult:
    """P6-19 rule-8 backed by the shared ``schema_visible_match`` eval.

    Sets ``evidence["conclusive"]`` so the caller can distinguish a real verdict
    from an absent or incomplete one. See the P1-22 twin in ``p1_schema.py``:
    a failure is provable from partial data, the ABSENCE of failures is not, so
    "no failing pages" only counts when every page returned a verdict.
    """
    evals = site.llm_evaluations.get("schema_visible_match", {})
    if not evals:
        return RuleResult(
            rule_id=8,
            rule_text="Schema content matches visible content (no hidden facts)",
            passed=True,
            evidence={
                "method": "deferred_until_anthropic_key_set",
                "evaluated_pages": 0,
                "conclusive": False,
            },
            notes=(
                "Not evaluated: the LLM evaluation layer was unavailable. Does not "
                "count toward the verdict; the capture degrades to PARTIAL."
            ),
        )
    failing = []
    errored = []
    passing = 0
    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        if ev.passed:
            passing += 1
        else:
            failing.append(
                {
                    "url": url,
                    "confidence": ev.confidence,
                    "issues": list(ev.issues)[:5],
                }
            )
    # A failure is definitive even with gaps; a clean sheet is only definitive
    # when every page returned a verdict.
    conclusive = bool(failing) or not errored
    return RuleResult(
        rule_id=8,
        rule_text="Schema content matches visible content (no hidden facts)",
        passed=len(failing) == 0,
        evidence={
            "method": "anthropic_llm_per_page_evaluation",
            "pages_evaluated": len(evals),
            "pages_passed": passing,
            "pages_failed": len(failing),
            "pages_errored": len(errored),
            "coverage_pct": round(
                100.0 * (passing + len(failing)) / max(1, len(evals)), 1
            ),
            "conclusive": conclusive,
            "failing_pages": failing[:25],
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


# ─── P6-01 — LLM-readable content structure (semantic HTML, headings) ───────


def _evaluate_html_structure(html: str) -> dict[str, Any]:
    """Run the P6-01 structural checks against one page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    main_count = len(soup.find_all("main"))
    article_count = len(soup.find_all("article"))
    h1_count = len(soup.find_all("h1"))

    # Heading-hierarchy walk: collect levels in DOM order.
    heading_levels = [
        int(h.name[1])
        for h in soup.find_all(re.compile(r"^h[1-6]$"))
    ]
    skipped_levels: list[tuple[int, int]] = []
    for prev, curr in zip(heading_levels, heading_levels[1:]):
        if curr > prev + 1:
            skipped_levels.append((prev, curr))

    p_count = len(soup.find_all("p"))
    list_count = len(soup.find_all(["ul", "ol"]))
    li_count = len(soup.find_all("li"))

    return {
        "main_or_article_count": main_count + article_count,
        "h1_count": h1_count,
        "heading_total": len(heading_levels),
        "skipped_level_count": len(skipped_levels),
        "skipped_level_pairs": skipped_levels[:5],
        "p_count": p_count,
        "list_count": list_count,
        "li_count": li_count,
    }


@register_extractor("P6-01")
async def capture_p6_01(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-01 — LLM-readable content structure (Consensus, semantic HTML)."""
    captured_at = _now()
    pages = [
        (url, page)
        for url, page in site.html_pages.items()
        if page.fetch_error is None and page.status_code < 400 and page.html
    ]
    if not pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-01",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "composition.html_structure_check"],
            errors=["site.html_pages empty"],
        )

    findings: list[dict[str, Any]] = []
    no_main = []
    multi_h1 = []
    no_h1 = []
    skipped_levels = []
    div_paragraph_pages = []

    for url, page in pages:
        check = _evaluate_html_structure(page.html)
        findings.append({"url": url, **check})
        if check["main_or_article_count"] != 1:
            no_main.append({"url": url, "count": check["main_or_article_count"]})
        if check["h1_count"] == 0:
            no_h1.append(url)
        elif check["h1_count"] > 1:
            multi_h1.append({"url": url, "count": check["h1_count"]})
        if check["skipped_level_count"] > 0:
            skipped_levels.append(
                {"url": url, "skips": check["skipped_level_pairs"]}
            )
        if check["p_count"] == 0 and check["heading_total"] > 0:
            div_paragraph_pages.append(url)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Each page wraps primary content in exactly one <main> or <article>",
        passed=len(no_main) == 0,
        evidence={
            "violations": no_main,
            "violation_count": len(no_main),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Each page has exactly one H1",
        passed=len(no_h1) == 0 and len(multi_h1) == 0,
        evidence={
            "no_h1_pages": no_h1,
            "multi_h1_pages": multi_h1,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Heading hierarchy is well-formed (no skipped levels: H2 → H4)",
        passed=len(skipped_levels) == 0,
        evidence={
            "pages_with_skips": skipped_levels[:25],
            "skip_count": len(skipped_levels),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Body text uses <p> tags (no pages with headings but zero <p>)",
        passed=len(div_paragraph_pages) == 0,
        evidence={
            "div_paragraph_pages": div_paragraph_pages,
            "violation_count": len(div_paragraph_pages),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="Lists are real lists (UL/OL/LI present where lists appear)",
        passed=True,
        evidence={
            "pages_with_lists": sum(1 for f in findings if f["list_count"] > 0),
            "pages_total": len(findings),
        },
        notes="Soft check: we don't false-positive flag pages without lists; just record list usage.",
    )

    rules = [rule_1, rule_2, rule_3, rule_4, rule_5]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": len(pages),
            "pages_with_no_main": len(no_main),
            "pages_with_no_h1": len(no_h1),
            "pages_with_multi_h1": len(multi_h1),
            "pages_with_skipped_levels": len(skipped_levels),
            "pages_with_div_paragraphs": len(div_paragraph_pages),
            "page_findings": findings[:30],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "composition.html_structure_check"],
    )


# ─── P6-04 — Statistical / numerical specificity ────────────────────────────


# Patterns for: percentages (47%, 47.3%), currency ($2.3 billion, £100M),
# explicit numbers with units (47 users, 12 months, 2024), bare digits in
# claim contexts. We deliberately don't try to catch ALL numbers (e.g. years
# alone) — the Consensus rule is about substantive numerical CLAIMS.
_NUMERIC_CLAIM_PATTERNS = (
    re.compile(r"\b\d+(?:[.,]\d+)?\s*%"),                     # percentages
    re.compile(r"[£$€¥]\s*\d+(?:[.,]\d+)?\s*[KkMmBb]?"),     # currency
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:million|billion|thousand|trillion)\b", re.I),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:users|customers|visitors|clients|companies|brands|sites|pages|articles)\b", re.I),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:hours|days|weeks|months|years|minutes|seconds)\b", re.I),
    re.compile(r"\b\d+(?:\.\d+){1,2}\b"),                     # versions / decimals like 4.7.1
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                     # ISO dates
)


def _count_numeric_claims(text: str) -> int:
    if not text:
        return 0
    return sum(len(p.findall(text)) for p in _NUMERIC_CLAIM_PATTERNS)


@register_extractor("P6-04")
async def capture_p6_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-04 — Statistical / numerical specificity (Consensus).

    Counts substantive numeric claims per 200 words across pages.
    Real-numerical-claim density is a strong GEO signal because LLMs
    favour pages with verifiable specifics over puffery copy.
    """
    captured_at = _now()
    page_texts = [
        (url, t) for url, t in site.text_content.items()
        if t.main_text and t.word_count >= 100  # skip thin pages from the rule
    ]
    if not page_texts:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-04",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no pages with substantive (>= 100 words) content"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["http.html_fetch", "trafilatura.main_text", "composition.numeric_density"],
            errors=["text_content empty or all pages thin"],
        )

    findings: list[dict[str, Any]] = []
    pages_below_density: list[dict[str, Any]] = []

    for url, t in page_texts:
        claim_count = _count_numeric_claims(t.main_text)
        density = (claim_count * 200.0 / t.word_count) if t.word_count else 0
        record = {
            "url": url,
            "word_count": t.word_count,
            "claim_count": claim_count,
            "claims_per_200_words": round(density, 2),
        }
        findings.append(record)
        if density < 1.0:
            pages_below_density.append(record)

    median_density = sorted(f["claims_per_200_words"] for f in findings)[
        len(findings) // 2
    ] if findings else 0
    pct_below_floor = (len(pages_below_density) / len(findings) * 100) if findings else 0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one numeric claim per 200 words on substantive pages",
        passed=len(pages_below_density) / len(findings) < 0.5 if findings else False,
        evidence={
            "pages_below_density": pages_below_density[:25],
            "below_density_count": len(pages_below_density),
            "below_density_pct": round(pct_below_floor, 1),
            "page_count": len(findings),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Median page numeric density >= 1.0 claims per 200 words",
        passed=median_density >= 1.0,
        evidence={"median_density": median_density},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Sourcing of numbers (DEFERRED — needs LLM eval)",
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_evaluation"},
        notes="Citation/sourcing of numeric claims needs LLM analysis; deferred.",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-04",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_checked": len(findings),
            "median_density": median_density,
            "pages_below_density_count": len(pages_below_density),
            "pages_below_density_pct": round(pct_below_floor, 1),
            "thin_page_skip_threshold_words": 100,
            "page_findings": findings[:30],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["http.html_fetch", "trafilatura.main_text", "composition.numeric_density"],
    )


# ─── P6-09 — FAQ and question-answer blocks ─────────────────────────────────


# Heuristic question-pattern detection for FAQs in prose body.
_FAQ_QUESTION_PATTERN = re.compile(
    r"^\s*(?:Q[:.]\s*|Question[:.]\s*)?"
    r"(How|What|Why|When|Where|Who|Which|Can|Is|Are|Do|Does|Should|Will)\b"
    r"[^.?\n]{0,200}\?",
    re.IGNORECASE | re.MULTILINE,
)


@register_extractor("P6-09")
async def capture_p6_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-09 — FAQ and question-answer blocks (Probable).

    Two signals: FAQPage schema markup + question-pattern density in
    main text. Pages with both are highest-confidence FAQ surfaces;
    schema-only is acceptable, prose-only is acceptable but weaker
    for LLM ingestion.
    """
    captured_at = _now()
    pages = [
        url for url, page in site.html_pages.items()
        if page.fetch_error is None and page.status_code < 400
    ]
    if not pages:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-09",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no successfully-fetched HTML pages"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["extruct.parse_structured_data", "composition.faq_pattern_match"],
            errors=["html_pages empty"],
        )

    findings: list[dict[str, Any]] = []
    pages_with_faq_schema: list[str] = []
    pages_with_prose_qa: list[str] = []
    pages_with_both: list[str] = []

    for url in pages:
        sd = site.structured_data.get(url)
        text = site.text_content.get(url)
        has_faq_schema = False
        if sd is not None:
            has_faq_schema = bool(
                sd.blocks_of_type("FAQPage") or sd.blocks_of_type("QAPage")
            )
        question_count = 0
        if text and text.main_text:
            question_count = len(_FAQ_QUESTION_PATTERN.findall(text.main_text))
        # "Substantive Q&A density" — at least 3 questions in the body
        has_prose_qa = question_count >= 3

        if has_faq_schema:
            pages_with_faq_schema.append(url)
        if has_prose_qa:
            pages_with_prose_qa.append(url)
        if has_faq_schema and has_prose_qa:
            pages_with_both.append(url)

        if has_faq_schema or has_prose_qa:
            findings.append(
                {
                    "url": url,
                    "has_faq_schema": has_faq_schema,
                    "prose_question_count": question_count,
                    "has_prose_qa": has_prose_qa,
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site has at least one page with FAQPage / QAPage schema",
        passed=len(pages_with_faq_schema) > 0,
        evidence={
            "schema_page_count": len(pages_with_faq_schema),
            "schema_pages": pages_with_faq_schema[:25],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Schema-tagged FAQ pages also carry visible Q&A content (matches schema)",
        passed=(
            len(pages_with_both) == len(pages_with_faq_schema)
            if pages_with_faq_schema else True
        ),
        evidence={
            "schema_with_visible_qa": len(pages_with_both),
            "schema_total": len(pages_with_faq_schema),
            "schema_without_visible_qa": [
                u for u in pages_with_faq_schema if u not in pages_with_both
            ],
        },
        notes=(
            "Schema-only FAQ markup without visible Q&A risks the "
            "Google 'hidden information' violation in P1-22 rule 7."
        ),
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Q&A authenticity (DEFERRED — needs LLM eval to detect marketing-puffery questions)",
        passed=True,
        evidence={"method": "deferred_to_h1c_llm_evaluation"},
        notes="Detecting 'Why is our product the best?' style fake FAQs needs LLM analysis.",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-09",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_total": len(pages),
            "pages_with_faq_schema": len(pages_with_faq_schema),
            "pages_with_prose_qa": len(pages_with_prose_qa),
            "pages_with_both": len(pages_with_both),
            "page_findings": findings[:30],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "extruct.parse_structured_data",
            "trafilatura.main_text",
            "composition.faq_pattern_match",
        ],
    )


# ─── P6-02 — Quotability / extractable claims ───────────────────────────────


@register_extractor("P6-02")
async def capture_p6_02(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-02 — Quotability of page content for AI search citation (Consensus)."""
    captured_at = _now()
    evals = site.llm_evaluations.get("quotability", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive pages found to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-02",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create", "composition.quotability_evaluator"],
            errors=[reason],
        )

    total = len(evals)
    passing = 0
    failing: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []
    pages_with_marketing_puffery: list[str] = []
    claim_counts: list[int] = []
    specific_counts: list[int] = []

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            errored.append({"url": url, "error": ev.error})
            continue
        raw = ev.raw or {}
        cc = int(raw.get("self_contained_claim_count") or 0)
        sc = int(raw.get("specific_claim_count") or 0)
        claim_counts.append(cc)
        specific_counts.append(sc)
        if raw.get("has_marketing_puffery_in_quotable_positions"):
            pages_with_marketing_puffery.append(url)
        if ev.passed:
            passing += 1
        else:
            failing.append(
                {
                    "url": url,
                    "self_contained_claims": cc,
                    "specific_claims": sc,
                    "confidence": ev.confidence,
                    "rationale": ev.rationale,
                }
            )

    avg_claim = sum(claim_counts) / len(claim_counts) if claim_counts else 0
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Majority of pages have >= 5 self-contained quotable claims",
        passed=(passing / total) >= 0.5 if total else False,
        evidence={
            "passing_pages": passing,
            "total": total,
            "avg_self_contained_claims": round(avg_claim, 1),
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No marketing puffery in quotable positions (< 30% of pages)",
        passed=(len(pages_with_marketing_puffery) / total) < 0.30 if total else True,
        evidence={
            "puffery_count": len(pages_with_marketing_puffery),
            "puffery_pct": round(len(pages_with_marketing_puffery) / total * 100, 1) if total else 0,
            "sample": pages_with_marketing_puffery[:10],
        },
    )

    rules = [rule_1, rule_5]
    overall_pass = rule_1.passed and rule_5.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-02",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_passing": passing,
            "pages_failing": len(failing),
            "pages_with_marketing_puffery": len(pages_with_marketing_puffery),
            "avg_self_contained_claims": round(avg_claim, 1),
            "failing_pages_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["anthropic.messages.create", "composition.quotability_evaluator"],
    )


# ─── P6-10 — Definitional clarity for entities and concepts ─────────────────


@register_extractor("P6-10")
async def capture_p6_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-10 — Definitional clarity (Probable)."""
    captured_at = _now()
    evals = site.llm_evaluations.get("definitional_clarity", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive pages found to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create", "composition.definitional_clarity_evaluator"],
            errors=[reason],
        )

    total = len(evals)
    passing = 0
    failing: list[dict[str, Any]] = []
    no_def_sentence: list[str] = []
    non_canonical: list[str] = []
    ambiguous: list[str] = []
    circular: list[str] = []

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            continue
        raw = ev.raw or {}
        if ev.passed:
            passing += 1
        if not raw.get("has_definitional_sentence", False):
            no_def_sentence.append(url)
        if not raw.get("uses_canonical_form", False):
            non_canonical.append(url)
        if not raw.get("is_unambiguous", False):
            ambiguous.append(url)
        if raw.get("is_circular", False):
            circular.append(url)
        if not ev.passed:
            failing.append(
                {
                    "url": url,
                    "confidence": ev.confidence,
                    "rationale": ev.rationale,
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Definitional sentence present near top of body on >= 50% of pages",
        passed=((total - len(no_def_sentence)) / total) >= 0.5 if total else False,
        evidence={
            "pages_without_def_sentence": len(no_def_sentence),
            "pages_total": total,
            "sample_missing": no_def_sentence[:10],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Definitions use canonical '[X] is [Y]' form on >= 50% of pages",
        passed=((total - len(non_canonical)) / total) >= 0.5 if total else False,
        evidence={
            "pages_non_canonical": len(non_canonical),
            "sample": non_canonical[:10],
        },
    )
    rule_5 = RuleResult(
        rule_id=5,
        rule_text="No circular definitions detected",
        passed=len(circular) == 0,
        evidence={"circular_pages": circular[:10]},
    )

    rules = [rule_1, rule_2, rule_5]
    overall_pass = rule_1.passed and rule_2.passed and rule_5.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_passing": passing,
            "pages_without_def_sentence": len(no_def_sentence),
            "pages_non_canonical": len(non_canonical),
            "pages_ambiguous": len(ambiguous),
            "pages_circular": len(circular),
            "failing_pages_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["anthropic.messages.create", "composition.definitional_clarity_evaluator"],
    )


# ─── P6-07 — Original research and primary data ─────────────────────────────


@register_extractor("P6-07")
async def capture_p6_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-07 — Original research and primary data (Consensus, LLM-eval).

    Reads from the ``original_research`` evaluator. Per-page check of
    four signals: methodology disclosure, primary data presence,
    limitations acknowledged, attribution to publisher.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("original_research", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no article-like long-form pages eligible for original-research evaluation"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-07",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason, "pages_evaluated": 0},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "anthropic.messages.create",
                "composition.original_research_evaluator",
            ],
            errors=[reason],
        )

    total = len(evals)
    passing = 0
    with_methodology = 0
    with_primary_data = 0
    with_limitations = 0
    with_attribution = 0
    failing: list[dict[str, Any]] = []

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
                    "methodology_disclosed": raw.get("methodology_disclosed"),
                    "has_primary_data": raw.get("has_primary_data"),
                    "limitations_acknowledged": raw.get("limitations_acknowledged"),
                    "data_attributed_to_publisher": raw.get("data_attributed_to_publisher"),
                }
            )
        if raw.get("methodology_disclosed"):
            with_methodology += 1
        if raw.get("has_primary_data"):
            with_primary_data += 1
        if raw.get("limitations_acknowledged"):
            with_limitations += 1
        if raw.get("data_attributed_to_publisher"):
            with_attribution += 1

    # Hard rule: at least one page presents original research. Soft rules
    # surface the per-signal distribution for human review.
    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one page presents original research (all 4 signals pass)",
        passed=passing >= 1,
        evidence={"passing_pages": passing, "pages_evaluated": total},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Methodology disclosure rate (advisory: surfaces the share of pages with explicit methodology)",
        passed=True,
        evidence={
            "with_methodology": with_methodology,
            "with_primary_data": with_primary_data,
            "with_limitations": with_limitations,
            "with_attribution": with_attribution,
            "total": total,
        },
        notes="Advisory only; the headline rule is whether any page meets all four signals.",
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-07",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_passing": passing,
            "pages_failing": len(failing),
            "with_methodology": with_methodology,
            "with_primary_data": with_primary_data,
            "with_limitations": with_limitations,
            "with_attribution": with_attribution,
            "failing_pages_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "anthropic.messages.create",
            "composition.original_research_evaluator",
        ],
    )


# ─── P6-31 — LLM hallucination resistance (brand-level disambiguation) ──────


@register_extractor("P6-31")
async def capture_p6_31(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-31 — LLM hallucination resistance (Probable, brand-level eval).

    Asks Claude to describe the brand from training-data knowledge
    alone, then compares its response against ground-truth facts we
    have from GBP. Detects fabrication, category mismatch, country
    mismatch, and good hedging behaviour.

    Single-LLM eval; the variable spec asks for cross-LLM testing
    (ChatGPT + Claude + Gemini) — we test Claude only in v1 and flag
    the limitation explicitly. The shape is correct; expanding to
    other LLMs is a future extension.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("brand_hallucination", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "brand or GBP ground-truth missing — cannot run verification"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-31",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": reason,
                "llm_configured": site.llm_configured,
                "has_brand": site.brand is not None,
                "has_gbp": site.gbp_info is not None,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "anthropic.messages.create",
                "composition.brand_hallucination_evaluator",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=site.brand.name if site.brand else site.domain,
            errors=[reason],
        )

    # Single brand-level evaluation.
    ev = next(iter(evals.values()))
    if ev.error:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-31",
            captured_at=captured_at,
            status=CaptureStatus.ERROR,
            value={"reason": ev.error, "raw": ev.raw},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "anthropic.messages.create",
                "composition.brand_hallucination_evaluator",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=site.brand.name if site.brand else site.domain,
            errors=[ev.error],
        )

    raw = ev.raw or {}
    llm_response = raw.get("llm_response") or {}
    ground_truth = raw.get("ground_truth") or {}
    known = bool(llm_response.get("known_with_confidence"))
    hedged = bool(llm_response.get("hedged"))
    issues = list(ev.issues)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Claude either knows the brand with confidence AND matches ground truth, OR correctly hedges",
        passed=bool(ev.passed),
        evidence={
            "known_with_confidence": known,
            "hedged": hedged,
            "issues_detected": issues,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Category description matches ground truth (where Claude claims confidence)",
        passed=not any(i.startswith("category_mismatch") for i in issues),
        evidence={
            "claimed_category": llm_response.get("category_described"),
            "truth_category": ground_truth.get("category"),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Headquarters country matches ground truth (where Claude claims confidence)",
        passed=not any(i.startswith("country_mismatch") for i in issues),
        evidence={
            "claimed_country": llm_response.get("headquarters_country"),
            "truth_country": ground_truth.get("country"),
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="No named executives claimed without ground truth (fabrication risk)",
        passed=not any(i.startswith("executives_claimed") for i in issues),
        evidence={"executives_claimed": llm_response.get("named_executives") or []},
        notes="Hard-fail if Claude names executives we can't verify; surfaces for human review.",
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-31",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "llm_tested": "claude_haiku_4_5",
            "limitation_note": "single-LLM eval; cross-LLM (ChatGPT/Gemini) deferred",
            "known_with_confidence": known,
            "hedged": hedged,
            "claimed_category": llm_response.get("category_described"),
            "claimed_country": llm_response.get("headquarters_country"),
            "claimed_executives": llm_response.get("named_executives") or [],
            "claimed_founded_year": llm_response.get("founded_year"),
            "claimed_primary_products": llm_response.get("primary_products") or [],
            "ground_truth": ground_truth,
            "issues_detected": issues,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.brand_hallucination_evaluator",
        ],
        subject_type=SubjectType.BRAND,
        subject_id=site.brand.name if site.brand else site.domain,
    )


# ─── P6-22 — Topic depth and exhaustiveness ─────────────────────────────────


@register_extractor("P6-22")
async def capture_p6_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-22 — Topic depth and exhaustiveness (Consensus, LLM-evaluated).

    Reads from the ``topic_depth`` evaluator. Each evaluated page gets:
    primary_topic, canonical_subtopics list, coverage_pct,
    addresses_comparisons, acknowledges_limitations.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("topic_depth", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no article-like pages with >= 400 words to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-22",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create", "composition.topic_depth_evaluator"],
            errors=[reason],
        )

    total = len(evals)
    passing = 0
    coverage_pcts: list[int] = []
    addresses_comparisons_count = 0
    acknowledges_limitations_count = 0
    failing: list[dict[str, Any]] = []

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
                    "primary_topic": raw.get("primary_topic"),
                    "coverage_pct": raw.get("coverage_pct"),
                    "rationale": ev.rationale,
                    "subtopics_missed": [
                        t for t in (raw.get("canonical_subtopics") or [])
                        if t not in (raw.get("subtopics_covered") or [])
                    ][:5],
                }
            )
        pct = raw.get("coverage_pct")
        if isinstance(pct, (int, float)):
            coverage_pcts.append(int(pct))
        if raw.get("addresses_comparisons"):
            addresses_comparisons_count += 1
        if raw.get("acknowledges_limitations"):
            acknowledges_limitations_count += 1

    avg_coverage = sum(coverage_pcts) / len(coverage_pcts) if coverage_pcts else 0
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Average canonical-subtopic coverage >= 75% across evaluated pages",
        passed=avg_coverage >= 75.0,
        evidence={"avg_coverage_pct": round(avg_coverage, 1)},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="At least 50% of evaluated pages address obvious comparisons",
        passed=(addresses_comparisons_count / total) >= 0.5 if total else False,
        evidence={
            "addresses_comparisons_count": addresses_comparisons_count,
            "total": total,
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="At least 30% of evaluated pages acknowledge limitations / exceptions",
        passed=(acknowledges_limitations_count / total) >= 0.3 if total else False,
        evidence={
            "acknowledges_limitations_count": acknowledges_limitations_count,
            "total": total,
        },
    )

    rules = [rule_2, rule_3, rule_4]
    overall_pass = rule_2.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-22",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_passing": passing,
            "pages_failing": len(failing),
            "avg_coverage_pct": round(avg_coverage, 1),
            "addresses_comparisons_count": addresses_comparisons_count,
            "acknowledges_limitations_count": acknowledges_limitations_count,
            "failing_pages_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "anthropic.messages.create",
            "composition.topic_depth_evaluator",
        ],
    )


# ─── P6-28 — Brand sentiment in LLM outputs ─────────────────────────────────


@register_extractor("P6-28")
async def capture_p6_28(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-28 — Brand sentiment in LLM outputs (Probable, single-LLM eval).

    Reads from the brand_sentiment evaluator. Same single-LLM caveat
    as P6-31: this tests Claude only; cross-LLM testing (ChatGPT /
    Gemini / Perplexity) deferred. The variable is informative even
    in single-LLM form because it surfaces whether Claude's training-
    data view of the brand is positive / neutral / negative.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("brand_sentiment", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no brand configured for sentiment evaluation"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-28",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "anthropic.messages.create",
                "composition.brand_sentiment_evaluator",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=site.brand.name if site.brand else site.domain,
            errors=[reason],
        )

    ev = next(iter(evals.values()))
    if ev.error:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-28",
            captured_at=captured_at,
            status=CaptureStatus.ERROR,
            value={"reason": ev.error, "raw": ev.raw},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "anthropic.messages.create",
                "composition.brand_sentiment_evaluator",
            ],
            subject_type=SubjectType.BRAND,
            subject_id=site.brand.name if site.brand else site.domain,
            errors=[ev.error],
        )

    raw = ev.raw or {}
    polarity = raw.get("polarity") or "unknown"
    hedged = bool(raw.get("hedged"))
    outdated = bool(raw.get("outdated_anchoring"))
    recommend = raw.get("would_recommend_brand") or "unknown"
    negatives = list(ev.issues)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Direct-description sentiment is positive or neutral (not negative)",
        passed=polarity in {"positive", "neutral"},
        evidence={"polarity": polarity, "hedged": hedged},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="LLM does not surface explicit negative claims about the brand",
        passed=len(negatives) == 0,
        evidence={"explicit_negative_claims": negatives[:10]},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Comparative tone is not adversarial (LLM does not systematically recommend competitor)",
        passed=recommend != "recommend_competitor",
        evidence={"would_recommend_brand": recommend},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="No outdated negative anchoring (no anchoring on historic resolved events)",
        passed=not outdated,
        evidence={"outdated_anchoring": outdated},
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-28",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "llm_tested": "claude_haiku_4_5",
            "limitation_note": "single-LLM eval; cross-LLM (ChatGPT/Gemini) deferred",
            "polarity": polarity,
            "hedged": hedged,
            "outdated_anchoring": outdated,
            "would_recommend_brand": recommend,
            "explicit_negative_claims": negatives,
            "direct_description_snippet": str(raw.get("direct_description", ""))[:300],
            "comparative_description_snippet": str(raw.get("comparative_description", ""))[:300],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.brand_sentiment_evaluator",
        ],
        subject_type=SubjectType.BRAND,
        subject_id=site.brand.name if site.brand else site.domain,
    )


# ─── P6-23 — Recency and freshness for time-sensitive queries ───────────────


# Expected staleness threshold (days) per time_sensitivity class.
# Pages older than this for their class are stale by topic standard.
_TIME_SENSITIVITY_MAX_AGE_DAYS = {
    "very_fresh": 60,    # ~2 months
    "fresh": 365,        # ~1 year
    "evergreen": 1825,   # 5 years
}


@register_extractor("P6-23")
async def capture_p6_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-23 — Recency for time-sensitive queries (Consensus, composition).

    Joins the per-page time-sensitivity classification (LLM) with the
    page-modification age (from htmldate prefetch used by P4-02). A
    page passes when its last-modified age is within the threshold for
    its declared time-sensitivity class.

    Pages classified evergreen are always treated as fresh enough.
    Very-fresh pages with stale dates are the strongest failure mode.
    """
    captured_at = _now()
    classifications = site.llm_evaluations.get("time_sensitivity", {})
    if not classifications:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no substantive pages to classify"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-23",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=[
                "anthropic.messages.create",
                "composition.time_sensitivity_classifier",
                "htmldate.find_date",
            ],
            errors=[reason],
        )

    # We need page ages — run htmldate over cached HTML in this extractor.
    # Same approach as P4-02.
    from htmldate import find_date
    from datetime import date, datetime as _dt, timezone as _tz

    today = _dt.now(_tz.utc).date()

    by_class: dict[str, dict[str, int]] = {
        "very_fresh": {"total": 0, "stale": 0, "fresh": 0, "undated": 0},
        "fresh": {"total": 0, "stale": 0, "fresh": 0, "undated": 0},
        "evergreen": {"total": 0, "stale": 0, "fresh": 0, "undated": 0},
    }
    stale_findings: list[dict[str, Any]] = []
    classified_count = 0

    for url, ev in classifications.items():
        if ev.error or ev.passed is None:
            continue
        sensitivity = (ev.raw or {}).get("time_sensitivity") or "evergreen"
        if sensitivity not in by_class:
            sensitivity = "evergreen"
        bucket = by_class[sensitivity]
        bucket["total"] += 1
        classified_count += 1
        page = site.html_pages.get(url)
        if page is None or page.fetch_error is not None or not page.html:
            bucket["undated"] += 1
            continue
        try:
            modified_str = find_date(page.html, original_date=False, url=url)
        except Exception:  # noqa: BLE001
            modified_str = None
        if not modified_str:
            bucket["undated"] += 1
            continue
        try:
            modified = date.fromisoformat(modified_str[:10])
        except ValueError:
            bucket["undated"] += 1
            continue
        age_days = (today - modified).days
        threshold = _TIME_SENSITIVITY_MAX_AGE_DAYS[sensitivity]
        if age_days > threshold:
            bucket["stale"] += 1
            stale_findings.append(
                {
                    "url": url,
                    "time_sensitivity": sensitivity,
                    "age_days": age_days,
                    "threshold_days": threshold,
                    "modified": modified.isoformat(),
                }
            )
        else:
            bucket["fresh"] += 1

    very_fresh_stale = by_class["very_fresh"]["stale"]
    fresh_stale = by_class["fresh"]["stale"]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Every very-fresh page is updated within 60 days",
        passed=very_fresh_stale == 0,
        evidence={
            "very_fresh_total": by_class["very_fresh"]["total"],
            "very_fresh_stale": very_fresh_stale,
            "threshold_days": _TIME_SENSITIVITY_MAX_AGE_DAYS["very_fresh"],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Every fresh-class page is updated within 12 months",
        passed=fresh_stale == 0,
        evidence={
            "fresh_total": by_class["fresh"]["total"],
            "fresh_stale": fresh_stale,
            "threshold_days": _TIME_SENSITIVITY_MAX_AGE_DAYS["fresh"],
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No more than 20% of classified pages are stale-for-class",
        passed=(
            (very_fresh_stale + fresh_stale) / classified_count < 0.20
            if classified_count else False
        ),
        evidence={
            "total_stale": very_fresh_stale + fresh_stale,
            "classified_count": classified_count,
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = all(r.passed for r in rules)

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "classified_count": classified_count,
            "by_class": by_class,
            "thresholds_days": _TIME_SENSITIVITY_MAX_AGE_DAYS,
            "stale_findings_sample": stale_findings[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "anthropic.messages.create",
            "composition.time_sensitivity_classifier",
            "htmldate.find_date",
        ],
    )


# ─── P6-05 — Direct quotes from named experts ───────────────────────────────


@register_extractor("P6-05")
async def capture_p6_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-05 — Direct quotes from named experts (Probable, LLM-evaluated).

    Reads from the expert_quote evaluator. Per-page check: does the
    page include at least one direct quote from a named expert with
    full attribution (name + title/affiliation), where the quote
    carries substantive content?
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("expert_quote", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "no article-like substantive pages to evaluate"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-05",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=[
                "anthropic.messages.create",
                "composition.expert_quote_evaluator",
            ],
            errors=[reason],
        )

    total = len(evals)
    pages_with_named_quote = 0
    total_quotes = 0
    total_filler = 0
    failing: list[dict[str, Any]] = []

    for url, ev in evals.items():
        if ev.error or ev.passed is None:
            continue
        raw = ev.raw or {}
        if ev.passed:
            pages_with_named_quote += 1
        total_quotes += int(raw.get("quote_count") or 0)
        total_filler += int(raw.get("filler_quote_count") or 0)
        if not ev.passed:
            failing.append(
                {
                    "url": url,
                    "filler_quote_count": raw.get("filler_quote_count"),
                    "rationale": ev.rationale,
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 30% of article-like pages carry a named-expert quote",
        passed=(pages_with_named_quote / total) >= 0.30 if total else False,
        evidence={
            "pages_with_named_quote": pages_with_named_quote,
            "total_evaluated": total,
            "pct": round(pages_with_named_quote / total * 100, 1) if total else 0,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least one named-expert quote exists across the site",
        passed=pages_with_named_quote >= 1,
        evidence={
            "total_quotes_found": total_quotes,
            "total_filler_quotes": total_filler,
        },
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_evaluated": total,
            "pages_with_named_quote": pages_with_named_quote,
            "total_named_quotes": total_quotes,
            "total_filler_quotes": total_filler,
            "failing_sample": failing[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.expert_quote_evaluator",
        ],
    )


# ─── P6-27 — ChatGPT, Claude, Gemini answer-citation frequency (Claude only v1) ──


@register_extractor("P6-27")
async def capture_p6_27(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-27 — Cross-assistant LLM citation/mention frequency (Probable).

    The full spec is cross-assistant testing (ChatGPT + Claude + Gemini +
    Copilot). We currently test Claude only via the existing
    ``brand_hallucination`` evaluator, which asks Claude to describe
    the brand from training-data knowledge alone. That gives us:

    - known_with_confidence: Claude has substantive specific knowledge
      of the brand (i.e., the brand IS in Claude's training corpus)
    - hedged: Claude declines / hedges (brand not in training or
      Claude correctly recognises low confidence)
    - the inverse — fabricated detail when known_with_confidence is
      false — is captured by P6-31

    Per the taxonomy's rule 6 (mention accuracy), the mention is only
    useful if accurate. So P6-27 v1 reports Claude's recognition rate
    *and* its accuracy on category/country signals.

    Coverage of ChatGPT, Gemini, Copilot deferred — needs OpenAI key,
    Gemini text-generation API integration, Copilot Search API. The
    rule structure is built so adding each LLM later is a single
    extension.

    Pass: Claude knows the brand with confidence AND the eval has no
    fabrication issues.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("brand_hallucination", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "brand or GBP ground-truth missing — brand_hallucination eval did not run"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-27",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create"],
            errors=[reason],
        )

    # brand_hallucination is a brand-level (single-call) eval; pull the
    # one entry
    eval_record = next(iter(evals.values()), None)
    if eval_record is None or eval_record.error:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-27",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "brand_hallucination eval errored",
                "error": eval_record.error if eval_record else "no eval record",
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["anthropic.messages.create"],
            errors=[
                eval_record.error if eval_record else "no record"
            ],
        )

    raw = eval_record.raw or {}
    claude_knows = bool(raw.get("known_with_confidence"))
    claude_hedged = bool(raw.get("hedged"))
    confidence = float(raw.get("confidence") or 0.0)
    primary_products = raw.get("primary_products") or []
    category = raw.get("category_described") or ""
    hq_country = raw.get("headquarters_country") or ""
    # P6-31 already flagged any mismatch — we read the same eval for
    # cross-assistant framing
    fabrication_issues = bool(eval_record.passed is False)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Claude has substantive specific knowledge of the brand (not generic guess, not declined)",
        passed=claude_knows and not claude_hedged,
        evidence={
            "claude_known_with_confidence": claude_knows,
            "claude_hedged": claude_hedged,
            "claude_confidence_self_reported": confidence,
            "claude_category_described": category,
            "claude_hq_country": hq_country,
            "claude_primary_products_recalled": primary_products,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Claude's brand description is accurate (no category/country fabrication flagged by P6-31)",
        passed=not fabrication_issues,
        evidence={
            "p6_31_passed": eval_record.passed,
            "p6_31_issues": list(eval_record.issues),
            "rationale": eval_record.rationale,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-27",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "assistants_tested": ["Claude (Anthropic)"],
            "assistants_deferred": [
                "ChatGPT — needs OpenAI API integration",
                "Gemini text-generation — needs Gemini text API integration (we use Gemini only for embeddings today)",
                "Microsoft Copilot — needs Copilot Search API",
            ],
            "claude": {
                "known_with_confidence": claude_knows,
                "hedged": claude_hedged,
                "self_reported_confidence": confidence,
                "category_described": category,
                "hq_country": hq_country,
                "primary_products_recalled": primary_products,
                "fabrication_issues": list(eval_record.issues),
                "p6_31_overall_passed": eval_record.passed,
                "rationale": eval_record.rationale,
            },
            "note": (
                "v1: Claude-only single-point sample. The full P6-27 spec "
                "needs cross-assistant query batteries with web-search tools "
                "enabled per provider; this batch tests internal-knowledge "
                "recall rather than web-search citation. Pass result here "
                "means Claude recognises the brand from training — a "
                "necessary but not sufficient condition for the full var."
            ),
            "watchlist": False,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "anthropic.messages.create",
            "composition.brand_hallucination_evaluator",
        ],
    )


# ─── P6-12 — Brand mentions across LLM training corpora ─────────────────────


@register_extractor("P6-12")
async def capture_p6_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-12 — Brand mentions across LLM training corpora (Consensus).

    The most direct externally-observable test: ask an LLM whose
    training corpus we want to probe to describe the brand from
    training-data knowledge alone (web search disabled). If the LLM
    has substantive specific knowledge, the brand is present in that
    training corpus. If it declines / hedges, the brand likely isn't.

    Reuses the existing ``brand_hallucination`` evaluator output —
    which is exactly this probe, run once at audit start against
    Claude.

    Pass: Claude shows substantive specific knowledge of the brand
    (known_with_confidence=true and not hedged). This is the
    Anthropic training-corpus signal.

    Other corpus signals (OpenAI, Google) deferred behind their
    respective API integrations. Indirect Common Crawl signals
    (P6-13 forum presence, P6-14 video, P6-15 podcast, P6-16 news)
    would corroborate but each needs its own external API.
    """
    captured_at = _now()
    evals = site.llm_evaluations.get("brand_hallucination", {})
    if not evals:
        reason = (
            "LLM eval pending: evaluate via a Claude session (export-brief + ingest), or set ANTHROPIC_API_KEY for headless eval"
            if not site.llm_configured
            else "brand_hallucination eval did not run (likely no brand/GBP ground truth)"
        )
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-12",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": reason},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create"],
            errors=[reason],
        )

    eval_record = next(iter(evals.values()), None)
    if eval_record is None or eval_record.error:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-12",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "brand_hallucination eval errored",
                "error": eval_record.error if eval_record else "no record",
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["anthropic.messages.create"],
            errors=[
                eval_record.error if eval_record else "no record"
            ],
        )

    raw = eval_record.raw or {}
    claude_knows = bool(raw.get("known_with_confidence"))
    claude_hedged = bool(raw.get("hedged"))
    confidence = float(raw.get("confidence") or 0.0)
    # Specific detail recall is the strongest signal — if Claude can
    # name founding year, executives, primary products, it has
    # substantive corpus presence
    founded_year = raw.get("founded_year")
    named_executives = raw.get("named_executives") or []
    primary_products = raw.get("primary_products") or []
    specific_detail_count = sum(
        [
            bool(founded_year),
            bool(named_executives),
            len(primary_products) >= 2,
        ]
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Brand is present in at least one major LLM training corpus (Anthropic Claude)",
        passed=claude_knows and not claude_hedged,
        evidence={
            "claude_known_with_confidence": claude_knows,
            "claude_hedged": claude_hedged,
            "claude_self_reported_confidence": confidence,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="LLM can recall specific identifying detail (>= 2 of: founded_year, named_executives, primary_products with >=2 items)",
        passed=specific_detail_count >= 2,
        evidence={
            "specific_detail_count": specific_detail_count,
            "founded_year_recalled": founded_year,
            "named_executives_recalled": named_executives,
            "primary_products_recalled": primary_products,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-12",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "corpora_tested": ["Anthropic Claude (via brand_hallucination eval)"],
            "corpora_deferred": [
                "OpenAI GPT training corpus — needs OpenAI API + parallel eval",
                "Google Gemini training corpus — needs Gemini text-gen integration",
                "Common Crawl direct inspection — needs CC search/download infrastructure (heavy)",
            ],
            "claude": {
                "known_with_confidence": claude_knows,
                "hedged": claude_hedged,
                "self_reported_confidence": confidence,
                "founded_year_recalled": founded_year,
                "named_executives_recalled": named_executives,
                "primary_products_recalled": primary_products,
                "specific_detail_count": specific_detail_count,
            },
            "note": (
                "Single LLM corpus test. Cross-platform coverage (P6-12 ideal "
                "spec) corroborates via forum mentions (P6-13), video (P6-14), "
                "podcast (P6-15), news (P6-16) — each needs its own API. "
                "Claude's positive recall is strong evidence of corpus "
                "presence; negative recall is weaker (Claude's training data "
                "is not Common Crawl, so absence here is suggestive but "
                "not definitive)."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "anthropic.messages.create",
            "composition.brand_hallucination_evaluator",
        ],
    )


# P6-25 is wired in p6_serp.py — kept there for historical continuity.
# Reads from site.serp_results (the orchestrator's shared SERP prefetch).


# ─── Shared helpers for brand-SERP-driven vars (P6-13 / P6-14 / P6-16) ──────


_FORUM_HOSTS = (
    "reddit.com", "old.reddit.com",
    "quora.com",
    "stackoverflow.com", "stackexchange.com", "serverfault.com", "superuser.com",
    "news.ycombinator.com", "ycombinator.com",
    "linkedin.com/posts", "linkedin.com/pulse",
    "medium.com",
    "discourse.org",
)

# Domains commonly recognised as authority / big-brand on SERPs.
# Used by P0-18 (big-brand preference threshold) — when these
# dominate the top results, smaller sites have minimal ranking
# opportunity regardless of on-page optimisation.
_BIG_BRAND_AUTHORITY_HOSTS = (
    # Reference / educational
    "wikipedia.org", ".gov", ".edu", ".ac.uk", ".gov.uk",
    "investopedia.com",
    # Tier-1 publications (overlaps with news list)
    "bbc.co.uk", "bbc.com", "theguardian.com", "ft.com",
    "nytimes.com", "wsj.com", "reuters.com", "bloomberg.com",
    "forbes.com", "businessinsider.com", "techcrunch.com",
    "wired.com", "theverge.com", "cnbc.com", "cnn.com", "economist.com",
    # Big consultancies / research firms
    "mckinsey.com", "deloitte.com", "pwc.com", "kpmg.com", "ey.com",
    "gartner.com", "forrester.com", "hbr.org",
    "accenture.com", "bain.com", "bcg.com", "capgemini.com",
    # Tech giants
    "google.com", "microsoft.com", "amazon.com", "apple.com",
    "meta.com", "facebook.com", "linkedin.com",
    "ibm.com", "oracle.com", "salesforce.com", "adobe.com",
    "developer.mozilla.org", "developers.google.com", "web.dev",
)

# Major directory / citation platforms — UK + global. Used by P5-06.
_DIRECTORY_CITATION_HOSTS = (
    # Global business directories
    "yelp.com", "yelp.co.uk",
    "bbb.org", "tripadvisor.com", "tripadvisor.co.uk",
    "yell.com", "yellowpages.com",
    "manta.com", "foursquare.com", "city-data.com",
    "ezlocal.com", "merchantcircle.com", "showmelocal.com",
    "cylex-uk.co.uk", "cylex.uk.com",
    "hotfrog.co.uk", "hotfrog.com",
    "thomsonlocal.com",
    "192.com",
    "scoot.co.uk",
    "bing.com/maps", "bingplaces.com",
    "apple.com/maps", "maps.apple.com",
    "duckduckgo.com",
    # Companies registries (UK-specific but commonly cited)
    "find-and-update.company-information.service.gov.uk",
    "companieshouse.gov.uk", "endole.co.uk",
    "duedil.com", "opencorporates.com",
)

# Software-dev / IT services industry directories — appropriate for
# Pixelette and similar B2B tech agencies. Used by P5-08.
_NICHE_TECH_AGENCY_HOSTS = (
    "clutch.co",
    "goodfirms.co",
    "designrush.com",
    "topdevelopers.co",
    "thinkmobiles.com",
    "businessofapps.com",
    "appfutura.com",
    "extract.co", "extract.app",
    "upwork.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com", "trustpilot.co.uk",
    "softwareadvice.com",
    "getapp.com",
    "expertise.com",
    "linkedin.com/company",
    "crunchbase.com",
    "agency.com",
    "the-manifest.com", "themanifest.com",
)

_VIDEO_HOSTS = (
    "youtube.com", "youtu.be",
    "vimeo.com",
    "wistia.com", "wistia.net",
    "loom.com",
    "twitch.tv",
    "dailymotion.com",
)

_NEWS_TIER1_HOSTS = (
    # UK
    "bbc.co.uk", "bbc.com", "theguardian.com", "ft.com", "thetimes.co.uk",
    "telegraph.co.uk", "independent.co.uk", "city-am.com",
    # US
    "nytimes.com", "wsj.com", "washingtonpost.com",
    "reuters.com", "bloomberg.com", "ap.org", "apnews.com",
    "forbes.com", "businessinsider.com", "fortune.com",
    "techcrunch.com", "wired.com", "theverge.com", "arstechnica.com",
    "venturebeat.com", "techradar.com", "engadget.com", "zdnet.com",
    "cnbc.com", "cnn.com",
    # International
    "economist.com", "afr.com", "smh.com.au",
)


def _brand_serp_items(site: SiteData) -> tuple[str, list[dict]] | None:
    """Locate the brand-name SERP among prefetched results.

    Returns (query_used, items_list) or None if no brand SERP is present.
    """
    if not site.serp_results or site.brand is None or not site.brand.name:
        return None
    brand_name = site.brand.name
    # Try exact match first, then any seed containing the brand name
    direct = site.serp_results.get(brand_name)
    if direct:
        return brand_name, direct.get("items") or []
    brand_lower = brand_name.lower()
    for q, result in site.serp_results.items():
        if brand_lower in q.lower():
            return q, result.get("items") or []
    return None


def _scan_brand_serp_for_hosts(
    site: SiteData,
    host_fragments: tuple[str, ...],
) -> dict[str, Any]:
    """Walk brand-SERP organic items, count matches against host fragments."""
    located = _brand_serp_items(site)
    if located is None:
        return {"brand_serp_found": False}
    query, items = located
    matches: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") not in ("organic", "video", "top_stories"):
            continue
        # Build candidate host strings: direct domain + url netloc + breadcrumb
        url = (item.get("url") or "").lower()
        domain = (item.get("domain") or "").lower()
        for frag in host_fragments:
            if frag in domain or frag in url:
                matches.append(
                    {
                        "type": item.get("type"),
                        "rank_absolute": item.get("rank_absolute"),
                        "domain": item.get("domain"),
                        "url": item.get("url"),
                        "title": (item.get("title") or "")[:120],
                        "matched_fragment": frag,
                    }
                )
                break
    return {
        "brand_serp_found": True,
        "brand_query": query,
        "total_organic_items_inspected": sum(
            1 for i in items if i.get("type") in ("organic", "video", "top_stories")
        ),
        "matches": matches,
    }


def _serp_feature_present_in_brand_serp(site: SiteData, feature_types: tuple[str, ...]) -> bool:
    located = _brand_serp_items(site)
    if located is None:
        return False
    _, items = located
    return any(item.get("type") in feature_types for item in items)


# ─── P6-13 — Reddit, Quora, and forum presence ─────────────────────────────


@register_extractor("P6-13")
async def capture_p6_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-13 — Reddit, Quora, and forum presence (Consensus).

    External-observable detection: search Google for the brand name,
    check whether forum/community discussion platforms (Reddit, Quora,
    Stack Exchange, Hacker News, LinkedIn posts, Medium) appear in
    the organic results. If they do, those threads exist and are
    indexed by Google.

    Pass: at least 1 forum host appears in brand SERP organic results.

    Taxonomy specifies a 6-rule check; sub-rules around sentiment,
    astroturfing detection, recency, topical-coverage match all need
    Reddit/Stack Exchange APIs + LLM sentiment analysis. Reported here
    as deferred.
    """
    captured_at = _now()
    finding = _scan_brand_serp_for_hosts(site, _FORUM_HOSTS)
    if not finding.get("brand_serp_found"):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-13",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "brand-name SERP not present in prefetched results — orchestrator's SERP prefetch seeds the brand name first; this should only happen when SERP prefetch entirely failed.",
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )

    matches = finding["matches"]
    hosts_present = sorted({m["matched_fragment"] for m in matches})

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one forum / community-discussion host appears in the brand-name SERP organic results",
        passed=len(matches) >= 1,
        evidence={
            "match_count": len(matches),
            "hosts_present": hosts_present,
            "matches": matches[:5],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-13",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "brand_query": finding["brand_query"],
            "match_count": len(matches),
            "hosts_present": hosts_present,
            "matches": matches[:10],
            "deferred_features": [
                "sentiment_of_forum_discussion (rule 4) — needs Reddit / Quora content + LLM",
                "astroturfing_detection (rule 3) — needs reviewer profile analysis",
                "topical_relevance_match (rule 5) — needs LLM topical comparison",
                "recency_within_18_months (rule 1 sub) — needs per-thread timestamps from Reddit / Stack Exchange APIs",
            ],
            "note": (
                "Detection: Google-indexed brand mentions on forum platforms. "
                "Stronger signals (per-thread sentiment, recency, astroturfing "
                "checks) require platform-specific APIs and LLM evaluation."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["serp.google.organic", "composition.brand_serp_host_scan"],
    )


# ─── P6-14 — YouTube and video transcript presence ─────────────────────────


@register_extractor("P6-14")
async def capture_p6_14(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-14 — YouTube and video transcript presence (Probable).

    External-observable detection: search Google for the brand name,
    check (a) whether video hosts (YouTube, Vimeo, Loom, etc.) appear
    in organic results, and (b) whether the SERP shows a Video Pack
    feature. Both signal that video content about the brand exists
    and is indexed.

    Pass: at least 1 video-host result in brand SERP OR a Video Pack
    feature is present.

    Sub-rules around transcript availability/accuracy, video duration,
    title/description optimisation, view counts, channel authority,
    and on-site VideoObject schema all need the YouTube Data API +
    per-video inspection — deferred.
    """
    captured_at = _now()
    finding = _scan_brand_serp_for_hosts(site, _VIDEO_HOSTS)
    if not finding.get("brand_serp_found"):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-14",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand-name SERP not present in prefetched results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )

    matches = finding["matches"]
    video_pack_present = _serp_feature_present_in_brand_serp(
        site, ("video", "video_pack", "videos")
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one video-host result OR a Video Pack feature appears in the brand SERP",
        passed=len(matches) >= 1 or video_pack_present,
        evidence={
            "video_host_match_count": len(matches),
            "video_pack_in_brand_serp": video_pack_present,
            "matches": matches[:5],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-14",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "brand_query": finding["brand_query"],
            "video_host_match_count": len(matches),
            "video_pack_in_brand_serp": video_pack_present,
            "matches": matches[:10],
            "deferred_features": [
                "transcript_availability_and_accuracy (rule 2) — needs YouTube Data API",
                "title_description_optimisation (rule 3) — needs YouTube metadata",
                "view_count_and_engagement (rule 4) — needs YouTube Data API",
                "VideoObject_schema_on_embed_pages (rule 5) — needs schema inspection on owned pages",
                "channel_authority (rule 6) — needs YouTube Data API channel stats",
            ],
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["serp.google.organic", "composition.brand_serp_video_scan"],
    )


# ─── P6-16 — News and tier-1 publication coverage ──────────────────────────


@register_extractor("P6-16")
async def capture_p6_16(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-16 — News and tier-1 publication coverage (Probable).

    External-observable detection: search Google for the brand name,
    check (a) whether tier-1 news/business publications appear in
    organic results, and (b) whether the SERP shows a Top Stories
    feature. Both signal that news coverage of the brand exists.

    Pass: at least 1 tier-1 news host in brand SERP organic OR a
    Top Stories feature is present.

    Sub-rules around per-article recency, sentiment of coverage,
    journalist credibility, and link-back-to-brand-site all need
    article-content extraction + LLM analysis — deferred.
    """
    captured_at = _now()
    finding = _scan_brand_serp_for_hosts(site, _NEWS_TIER1_HOSTS)
    if not finding.get("brand_serp_found"):
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P6-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand-name SERP not present in prefetched results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )

    matches = finding["matches"]
    top_stories_present = _serp_feature_present_in_brand_serp(
        site, ("top_stories",)
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one tier-1 news / business publication appears in brand SERP organic OR a Top Stories feature is present",
        passed=len(matches) >= 1 or top_stories_present,
        evidence={
            "news_host_match_count": len(matches),
            "top_stories_in_brand_serp": top_stories_present,
            "matches": matches[:5],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-16",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "brand_query": finding["brand_query"],
            "news_host_match_count": len(matches),
            "top_stories_in_brand_serp": top_stories_present,
            "matches": matches[:10],
            "deferred_features": [
                "article_recency_within_window — needs per-article publication dates",
                "sentiment_of_coverage — needs article content + LLM",
                "journalist_credibility — needs author lookup",
                "link_back_to_brand — needs article content scrape",
            ],
            "note": (
                "Conservative tier-1 list: UK + US major publications + tech "
                "press + business wire. Niche industry publications (which "
                "may be more relevant for B2B brands) are not on this list. "
                "Custom tier-list per industry would refine this further."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["serp.google.organic", "composition.brand_serp_news_scan"],
    )


# ─── P6-26 — Perplexity citation frequency ─────────────────────────────────


@register_extractor("P6-26")
async def capture_p6_26(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P6-26 — Perplexity citation frequency (Consensus).

    Perplexity is the most citation-transparent AI search engine —
    every answer surfaces its cited sources. Tracking Perplexity
    citation rate across a target query set is operationally
    equivalent to AI Overview tracking (P6-25), and is treated as a
    primary GEO outcome metric.

    The query path needs a Perplexity API key (or SerpAPI's Perplexity
    wrapper, or a headless browser). None of those are wired in
    SEOMATE today, so this variable is UNMEASURABLE pending a
    Perplexity integration.

    Reports the clear remediation path: when the integration lands,
    the same query universe used for P6-25 (top-N ranked keywords)
    can be tested against Perplexity in parallel — single new adapter
    method, one extra prefetch step.
    """
    captured_at = _now()
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P6-26",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "Perplexity AI doesn't expose a free public lookup; querying it "
                "needs the Perplexity API (paid, ~$5/month entry plus per-query) "
                "OR SerpAPI's Perplexity wrapper (paid) OR a headless-browser "
                "scrape (fragile + ToS-grey). None of those are wired in "
                "SEOMATE today."
            ),
            "structure_parallel_to_p6_25": (
                "When wired, the var reads the same query universe as P6-25 "
                "(top-N ranked keywords), runs each against Perplexity, parses "
                "the citation array per answer, and applies the same coverage "
                "/ inclusion / position rule set. Pass criterion: brand cited "
                "in >= 5% of queries (matches P6-25 emerging-brand benchmark)."
            ),
            "remediation_paths": [
                "Perplexity API direct (https://docs.perplexity.ai/) — sign up, get API key, set PERPLEXITY_API_KEY env var, add adapter method, add orchestrator prefetch step.",
                "SerpAPI Perplexity wrapper — fewer setup steps but pricier per query.",
                "Defer indefinitely — the existing P6-25 (AI Overview) + P6-27 (Claude recall) already cover two of the four major AI surfaces. Perplexity adds incremental coverage; whether it justifies the $5+/mo depends on whether the user's audience uses Perplexity (research-heavy professional audience: yes; consumer audience: less so).",
            ],
            "watchlist": True,
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["perplexity.api (not wired)"],
        errors=["Perplexity API integration not wired"],
    )