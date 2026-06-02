"""Pillar 5 — Local SEO extractors.

GBP profile is auto-discovered at audit start via brand-name search
against DataForSEO Business Data. Discovery method is recorded on
SiteData so reviewers know whether the GBP was a direct domain-matched
hit or a top-hit-without-domain-match.

Variables operationalised in this module:

- P5-04 — GBP profile completeness                          (Consensus)
- P5-05 — NAP consistency across site + GBP                 (Consensus)
- P5-09 — Review count                                      (Consensus)
- P5-10 — Review average star rating                        (Consensus)
- P5-26 — LocalBusiness schema markup presence + validity   (Consensus)

P5 variables that depend on GBP-owner-only data (review-level details,
Q&A activity, posts cadence, engagement clicks/calls/directions) are
not in this batch; those need the GBP API authorised by the owner.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import json as _json

from seomate.adapters import AdapterContext
from seomate.adapters.llm import LlmAdapter, LlmNotConfigured
from seomate.data_contract import (
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    RuleResult,
    SubjectType,
)
from seomate.pillars._base import SiteData, register_extractor

# ─── GBP fields we expect on a complete profile ─────────────────────────────

GBP_REQUIRED_FIELDS = (
    "title",
    "description",
    "category",
    "address",
    "phone",
    "url",
)

GBP_RECOMMENDED_FIELDS = (
    "logo",
    "additional_categories",
    "rating",
    "latitude",
    "longitude",
)

# Review count benchmarks (Consensus floor: any reviews; healthy: >= 20).
REVIEW_COUNT_FLOOR = 1
REVIEW_COUNT_HEALTHY = 20

# Review rating bands.
REVIEW_RATING_GOOD = 4.0   # below this is recognised "low rating"
REVIEW_RATING_HEALTHY = 4.5

# Phone-normalisation regex: strip everything but digits.
_DIGITS_RE = re.compile(r"\D+")


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
    subject_type: SubjectType = SubjectType.BUSINESS,
    subject_id: str | None = None,
) -> CaptureRecord:
    return CaptureRecord(
        audit_id=ctx.audit_id,
        variable_id=variable_id,
        pillar="P5",
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


def _no_gbp_unmeasurable(
    ctx: AdapterContext,
    site: SiteData,
    variable_id: str,
    weight: EvidenceWeight,
    captured_at: datetime,
) -> CaptureRecord:
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id=variable_id,
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": "no Google Business Profile found for this brand",
            "discovery_method": site.gbp_discovery_method,
            "brand": site.brand.name if site.brand else None,
        },
        rules=None,
        evidence_weight=weight,
        data_sources=["business_data.google.my_business_info"],
        errors=["site.gbp_info is None"],
    )


def _normalise_phone(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _DIGITS_RE.sub("", value)


def _normalise_address(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().replace(",", " ").split())


# ─── P5-04 — GBP profile completeness ───────────────────────────────────────


@register_extractor("P5-04")
async def capture_p5_04(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-04 — GBP profile completeness (Consensus).

    Checks the GBP profile has all required + recommended fields
    populated. Unmeasurable when no GBP is discoverable for the brand.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-04", EvidenceWeight.CONSENSUS, captured_at,
        )

    required_present = {f: bool(gbp.get(f)) for f in GBP_REQUIRED_FIELDS}
    recommended_present = {f: bool(gbp.get(f)) for f in GBP_RECOMMENDED_FIELDS}
    missing_required = [f for f, ok in required_present.items() if not ok]
    missing_recommended = [f for f, ok in recommended_present.items() if not ok]
    has_description_substantive = (
        isinstance(gbp.get("description"), str)
        and len(gbp["description"].strip()) >= 100
    )
    is_claimed = bool(gbp.get("is_claimed"))

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="All GBP required fields populated (title, description, category, address, phone, url)",
        passed=len(missing_required) == 0,
        evidence={
            "missing_required": missing_required,
            "present_required": sorted(f for f, ok in required_present.items() if ok),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Description is substantive (>= 100 chars)",
        passed=has_description_substantive,
        evidence={
            "description_length": len((gbp.get("description") or "")),
            "min_chars": 100,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Profile is claimed (owner-verified)",
        passed=is_claimed,
        evidence={"is_claimed": is_claimed},
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Recommended fields populated (logo, additional_categories, rating, lat/lng)",
        passed=len(missing_recommended) == 0,
        evidence={
            "missing_recommended": missing_recommended,
            "present_recommended": sorted(f for f, ok in recommended_present.items() if ok),
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-04",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "title": gbp.get("title"),
            "place_id": gbp.get("place_id"),
            "is_claimed": is_claimed,
            "required_fields_present": sum(1 for ok in required_present.values() if ok),
            "required_fields_total": len(GBP_REQUIRED_FIELDS),
            "recommended_fields_present": sum(1 for ok in recommended_present.values() if ok),
            "recommended_fields_total": len(GBP_RECOMMENDED_FIELDS),
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "description_length": len(gbp.get("description") or ""),
            "discovery_method": site.gbp_discovery_method,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.my_business_info"],
    )


# ─── P5-05 — NAP consistency across site + GBP ──────────────────────────────


def _gather_site_nap(site: SiteData) -> dict[str, set[str]]:
    """Collect candidate NAP values from cached structured data.

    Walks every schema.org block looking for Organization /
    LocalBusiness types and pulls name / address / phone candidates.
    """
    names: set[str] = set()
    addresses: set[str] = set()
    phones: set[str] = set()
    target_types = {"Organization", "LocalBusiness", "Corporation"}
    for sd in site.structured_data.values():
        for block in sd.schema_org_blocks:
            if not (set(block.types) & target_types):
                continue
            raw = block.raw
            name = raw.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
            addr = raw.get("address")
            if isinstance(addr, dict):
                # PostalAddress shape
                parts = [
                    addr.get(k)
                    for k in (
                        "streetAddress", "addressLocality", "addressRegion",
                        "postalCode", "addressCountry",
                    )
                    if isinstance(addr.get(k), str)
                ]
                if parts:
                    addresses.add(_normalise_address(" ".join(parts)))
            elif isinstance(addr, str):
                addresses.add(_normalise_address(addr))
            phone = raw.get("telephone") or raw.get("phone")
            if isinstance(phone, str) and phone.strip():
                phones.add(_normalise_phone(phone))
            # Some sites stick contactPoint with telephone inside.
            cp = raw.get("contactPoint")
            if isinstance(cp, list):
                for c in cp:
                    if isinstance(c, dict) and isinstance(c.get("telephone"), str):
                        phones.add(_normalise_phone(c["telephone"]))
            elif isinstance(cp, dict) and isinstance(cp.get("telephone"), str):
                phones.add(_normalise_phone(cp["telephone"]))
    return {
        "names": names,
        "addresses": addresses,
        "phones": {p for p in phones if p},
    }


@register_extractor("P5-05")
async def capture_p5_05(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-05 — NAP consistency between GBP and the audited site (Consensus).

    Compares the brand's name / address / phone as Google sees it (GBP)
    versus what's declared on the site itself (Organization /
    LocalBusiness schema). Inconsistencies confuse map citations and
    are a Consensus-tier local-SEO failure.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-05", EvidenceWeight.CONSENSUS, captured_at,
        )

    site_nap = _gather_site_nap(site)
    gbp_name = (gbp.get("title") or "").strip()
    gbp_address = _normalise_address(gbp.get("address") or "")
    gbp_phone = _normalise_phone(gbp.get("phone") or "")

    name_match = (
        gbp_name in site_nap["names"]
        or any(gbp_name.lower() == n.lower() for n in site_nap["names"])
    )
    address_match = False
    if gbp_address:
        # Fuzzy: site address must contain key tokens from GBP address.
        gbp_tokens = set(gbp_address.split())
        for site_addr in site_nap["addresses"]:
            site_tokens = set(site_addr.split())
            if gbp_tokens and len(gbp_tokens & site_tokens) / len(gbp_tokens) >= 0.5:
                address_match = True
                break
    phone_match = bool(gbp_phone and gbp_phone in site_nap["phones"])

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="GBP name matches at least one Organization/LocalBusiness name declared on site",
        passed=name_match,
        evidence={
            "gbp_name": gbp_name,
            "site_names": sorted(site_nap["names"]),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="GBP address tokens match at least 50% of an address declared on site",
        passed=address_match,
        evidence={
            "gbp_address": gbp.get("address"),
            "site_addresses_normalised": sorted(site_nap["addresses"]),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="GBP phone (digits-only) appears in at least one schema phone on site",
        passed=phone_match,
        evidence={
            "gbp_phone_normalised": gbp_phone,
            "site_phones_normalised": sorted(site_nap["phones"]),
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-05",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "name_match": name_match,
            "address_match": address_match,
            "phone_match": phone_match,
            "gbp": {
                "name": gbp_name,
                "address": gbp.get("address"),
                "phone": gbp.get("phone"),
            },
            "site": {
                "names": sorted(site_nap["names"])[:10],
                "addresses": sorted(site_nap["addresses"])[:5],
                "phones": sorted(site_nap["phones"])[:5],
            },
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
            "extruct.parse_structured_data",
            "composition.nap_consistency_check",
        ],
    )


# ─── P5-09 — Review count ───────────────────────────────────────────────────


@register_extractor("P5-09")
async def capture_p5_09(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-09 — Review count on the GBP profile (Consensus)."""
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-09", EvidenceWeight.CONSENSUS, captured_at,
        )

    rating = gbp.get("rating") or {}
    votes = int(rating.get("votes_count") or 0)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"GBP has at least {REVIEW_COUNT_FLOOR} review",
        passed=votes >= REVIEW_COUNT_FLOOR,
        evidence={"votes_count": votes, "floor": REVIEW_COUNT_FLOOR},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"GBP has a healthy review base (>= {REVIEW_COUNT_HEALTHY} reviews)",
        passed=votes >= REVIEW_COUNT_HEALTHY,
        evidence={"votes_count": votes, "healthy_threshold": REVIEW_COUNT_HEALTHY},
    )

    rules = [rule_1, rule_2]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-09",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "votes_count": votes,
            "place_id": gbp.get("place_id"),
            "thresholds": {
                "floor": REVIEW_COUNT_FLOOR,
                "healthy": REVIEW_COUNT_HEALTHY,
            },
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.my_business_info"],
    )


# ─── P5-10 — Review average star rating ─────────────────────────────────────


@register_extractor("P5-10")
async def capture_p5_10(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-10 — Review average star rating (Consensus)."""
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-10", EvidenceWeight.CONSENSUS, captured_at,
        )

    rating = gbp.get("rating") or {}
    value = rating.get("value")
    if value is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-10",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "GBP has no rating value yet (likely <1 review)"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["business_data.google.my_business_info"],
            errors=["rating.value is None"],
        )
    rating_value = float(value)
    distribution = gbp.get("rating_distribution") or {}

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=f"Average rating >= {REVIEW_RATING_GOOD} (acceptable band)",
        passed=rating_value >= REVIEW_RATING_GOOD,
        evidence={"rating": rating_value, "threshold": REVIEW_RATING_GOOD},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text=f"Average rating >= {REVIEW_RATING_HEALTHY} (healthy band)",
        passed=rating_value >= REVIEW_RATING_HEALTHY,
        evidence={"rating": rating_value, "threshold": REVIEW_RATING_HEALTHY},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Rating distribution is non-degenerate (more than one star bucket has reviews)",
        passed=sum(1 for v in distribution.values() if isinstance(v, int) and v > 0) >= 2,
        evidence={"distribution": distribution},
        notes="Useful for detecting fake-review patterns (all-5-stars suspicious for many-review profiles).",
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-10",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "rating": rating_value,
            "votes_count": int(rating.get("votes_count") or 0),
            "rating_distribution": distribution,
            "thresholds": {"good": REVIEW_RATING_GOOD, "healthy": REVIEW_RATING_HEALTHY},
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.my_business_info"],
    )


# ─── P5-26 — LocalBusiness schema markup ────────────────────────────────────


# Properties recommended for a LocalBusiness schema block per
# schema.org docs and Google's structured-data requirements.
LOCAL_BUSINESS_PROPS = (
    "name",
    "address",
    "telephone",
    "url",
    "openingHours",
    "geo",
    "image",
    "priceRange",
)


@register_extractor("P5-26")
async def capture_p5_26(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-26 — LocalBusiness schema markup presence and completeness (Consensus).

    Free check from cached structured data. Doesn't depend on a GBP
    being discoverable. Local businesses should declare
    ``LocalBusiness`` (or a more specific subtype) on their homepage
    with name + address + telephone at minimum.
    """
    captured_at = _now()
    if not site.structured_data:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-26",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no structured-data captured for any page"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["extruct.parse_structured_data"],
            subject_type=SubjectType.SITE,
            errors=["structured_data empty"],
        )

    target_types = {
        "LocalBusiness",
        "Store",
        "Restaurant",
        "Dentist",
        "ProfessionalService",
        "MedicalBusiness",
        "AutomotiveBusiness",
        "FinancialService",
        "LegalService",
        "RealEstateAgent",
        "TravelAgency",
        "ChildCare",
        "HomeAndConstructionBusiness",
        "FoodEstablishment",
    }

    pages_with_lb: list[dict[str, Any]] = []
    for url, sd in site.structured_data.items():
        for block in sd.schema_org_blocks:
            matched_types = set(block.types) & target_types
            if not matched_types:
                continue
            props_present = [p for p in LOCAL_BUSINESS_PROPS if block.raw.get(p)]
            props_missing = [p for p in LOCAL_BUSINESS_PROPS if not block.raw.get(p)]
            pages_with_lb.append(
                {
                    "url": url,
                    "types": sorted(matched_types),
                    "props_present": props_present,
                    "props_missing": props_missing,
                    "props_present_count": len(props_present),
                }
            )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Site declares LocalBusiness (or a more specific subtype) schema on at least one page",
        passed=len(pages_with_lb) > 0,
        evidence={
            "pages_with_localbusiness": len(pages_with_lb),
            "subtypes_accepted": sorted(target_types),
        },
    )

    # Best block — the one with the most populated props.
    best = (
        max(pages_with_lb, key=lambda b: b["props_present_count"])
        if pages_with_lb else None
    )
    minimum_props = {"name", "address", "telephone"}
    minimum_ok = (
        bool(best) and minimum_props.issubset(set(best["props_present"]))
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="LocalBusiness block has minimum required properties (name + address + telephone)",
        passed=minimum_ok,
        evidence={
            "best_block": best,
            "minimum_required": sorted(minimum_props),
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="LocalBusiness block has at least 5 of the recommended properties",
        passed=bool(best) and best["props_present_count"] >= 5,
        evidence={
            "best_block_props_present": best["props_present"] if best else [],
            "props_evaluated": list(LOCAL_BUSINESS_PROPS),
        },
    )

    rules = [rule_1, rule_2, rule_3]
    overall_pass = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-26",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "pages_with_localbusiness": len(pages_with_lb),
            "best_block": best,
            "best_block_props_count": best["props_present_count"] if best else 0,
            "page_findings": pages_with_lb[:25],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["extruct.parse_structured_data", "composition.localbusiness_schema_check"],
        subject_type=SubjectType.SITE,
    )


# ─── P5-02 — GBP primary category alignment ─────────────────────────────────


def _category_tokens(category: str) -> set[str]:
    """Tokenise a GBP category for fuzzy alignment matching.

    "Software company" -> {"software", "company"}; stopwords stripped.
    """
    stop = {"company", "service", "services", "and", "of", "the", "a", "an"}
    toks = re.findall(r"[a-z0-9]+", (category or "").lower())
    return {t for t in toks if t and len(t) > 2 and t not in stop}


@register_extractor("P5-02")
async def capture_p5_02(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-02 — GBP primary category alignment (Consensus).

    Checks the GBP primary category is set and aligns with the
    business's actual offering as represented by:
    - homepage title + H1 text
    - ranked-keyword head terms (the queries the business surfaces for)

    The Whitespark 2026 study ranks primary category as the top
    GBP-controlled local-pack factor. Misalignment is a Consensus-tier
    local SEO problem.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-02", EvidenceWeight.CONSENSUS, captured_at,
        )

    primary_category = (gbp.get("category") or "").strip()
    cat_tokens = _category_tokens(primary_category)

    # Site-side anchors for alignment: homepage title + h1, plus all ranked keywords.
    home_audit = None
    for audit in site.successful_audits:
        path = (urlsplit(audit.url).path or "/").strip("/")
        if not path:
            home_audit = audit
            break
    home_text_parts: list[str] = []
    if home_audit is not None:
        if home_audit.title:
            home_text_parts.append(home_audit.title)
        home_text_parts.extend(home_audit.h1)
        home_text_parts.extend(home_audit.h2)
    home_text = " ".join(home_text_parts).lower()
    home_tokens = set(re.findall(r"[a-z0-9]+", home_text))

    ranked_keywords_text = " ".join(
        ((item.get("keyword_data") or {}).get("keyword") or "")
        for item in (site.ranked_keywords or [])
    ).lower()
    rk_tokens = set(re.findall(r"[a-z0-9]+", ranked_keywords_text))

    home_overlap = cat_tokens & home_tokens
    rk_overlap = cat_tokens & rk_tokens
    has_home_alignment = bool(home_overlap) if cat_tokens else False
    has_rk_alignment = bool(rk_overlap) if cat_tokens else False

    # Rule 6: business name in GBP should not be keyword-stuffed
    # (compare GBP title length vs configured brand name length)
    gbp_title = (gbp.get("title") or "").strip()
    brand_name = (site.brand.name if site.brand else "") or ""
    title_kw_stuffed = (
        bool(brand_name)
        and len(gbp_title) > len(brand_name) * 1.5
        and brand_name.lower() in gbp_title.lower()
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="GBP primary category is set",
        passed=bool(primary_category),
        evidence={"primary_category": primary_category},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Primary category tokens appear in homepage title/H1/H2 (offering alignment)",
        passed=has_home_alignment,
        evidence={
            "category_tokens": sorted(cat_tokens),
            "homepage_overlap_tokens": sorted(home_overlap),
            "homepage_title": getattr(home_audit, "title", None) if home_audit else None,
        },
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="Primary category tokens appear in at least one ranked keyword (query alignment)",
        passed=has_rk_alignment or not site.ranked_keywords,
        evidence={
            "category_tokens": sorted(cat_tokens),
            "ranked_keyword_overlap_tokens": sorted(rk_overlap),
            "ranked_keywords_inspected": len(site.ranked_keywords or []),
        },
        notes=("ranked_keywords empty — rule skipped"
               if not site.ranked_keywords else None),
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="GBP business name is not keyword-stuffed (matches configured brand name)",
        passed=not title_kw_stuffed,
        evidence={
            "gbp_title": gbp_title,
            "brand_name": brand_name,
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-02",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "primary_category": primary_category,
            "category_tokens": sorted(cat_tokens),
            "homepage_overlap_tokens": sorted(home_overlap),
            "homepage_title": getattr(home_audit, "title", None) if home_audit else None,
            "ranked_keyword_overlap_tokens": sorted(rk_overlap),
            "ranked_keywords_inspected": len(site.ranked_keywords or []),
            "gbp_title": gbp_title,
            "title_keyword_stuffed": title_kw_stuffed,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
            "dataforseo_on_page.instant_pages",
            "dataforseo_labs.ranked_keywords",
            "composition.gbp_category_alignment",
        ],
    )


# ─── P5-03 — GBP secondary categories ───────────────────────────────────────


@register_extractor("P5-03")
async def capture_p5_03(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-03 — GBP secondary categories (Consensus).

    Checks the additional_categories list is present, reasonable size
    (1-9), no duplicates with the primary, and the names are distinct
    enough not to be near-duplicates of each other.

    Owner-data rules from the taxonomy (services-list alignment,
    attribute alignment) need authorised GBP API access — flagged as
    deferred in the value blob.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-03", EvidenceWeight.CONSENSUS, captured_at,
        )

    primary_category = (gbp.get("category") or "").strip()
    additional = gbp.get("additional_categories") or []
    if not isinstance(additional, list):
        additional = []
    additional = [str(c).strip() for c in additional if str(c).strip()]

    total_categories = (1 if primary_category else 0) + len(additional)
    duplicates_with_primary = [
        c for c in additional if c.lower() == primary_category.lower()
    ]

    # Near-duplicate detection across additional list
    near_dupe_pairs: list[tuple[str, str]] = []
    seen_token_sets: list[tuple[str, set[str]]] = []
    for cat in additional:
        toks = _category_tokens(cat)
        for prev_cat, prev_toks in seen_token_sets:
            if toks and prev_toks:
                overlap = len(toks & prev_toks) / max(len(toks), len(prev_toks))
                if overlap >= 0.75:
                    near_dupe_pairs.append((prev_cat, cat))
        seen_token_sets.append((cat, toks))

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one secondary category declared",
        passed=len(additional) >= 1,
        evidence={"secondary_count": len(additional)},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No secondary category duplicates the primary category",
        passed=len(duplicates_with_primary) == 0,
        evidence={"duplicates_with_primary": duplicates_with_primary},
    )
    rule_3 = RuleResult(
        rule_id=3,
        rule_text="No near-duplicate categories within the additional list (>=75% token overlap)",
        passed=len(near_dupe_pairs) == 0,
        evidence={
            "near_duplicate_pairs": [list(p) for p in near_dupe_pairs],
        },
    )
    rule_4 = RuleResult(
        rule_id=4,
        rule_text="Total categories within Google's 10-slot limit (1 primary + up to 9 secondary)",
        passed=total_categories <= 10,
        evidence={
            "total_categories": total_categories,
            "primary_present": bool(primary_category),
            "additional_count": len(additional),
        },
    )

    rules = [rule_1, rule_2, rule_3, rule_4]
    overall_pass = (
        rule_1.passed and rule_2.passed and rule_3.passed and rule_4.passed
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-03",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall_pass else CaptureStatus.FAILED,
        value={
            "primary_category": primary_category,
            "additional_categories": additional,
            "secondary_count": len(additional),
            "total_categories": total_categories,
            "duplicates_with_primary": duplicates_with_primary,
            "near_duplicate_pairs": [list(p) for p in near_dupe_pairs],
            "deferred_owner_rules": [
                "services_list_alignment (needs GBP owner API)",
                "attribute_alignment (needs GBP owner API)",
                "keyword_stuffing_check (needs category-versus-services semantic check)",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
            "composition.gbp_secondary_category_check",
        ],
    )


# ─── P5-21 — GBP photos count and freshness ─────────────────────────────────


@register_extractor("P5-21")
async def capture_p5_21(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-21 — GBP photos count and freshness (Consensus).

    Reads ``total_photos`` from the cached GBP profile. Per Whitespark
    + GBP guidelines, profiles should carry >= 10 photos covering
    exterior / interior / products / team for a complete listing.

    Photo freshness (upload recency) is not returned by DataForSEO's
    basic ``google_my_business_info`` endpoint — would require the
    paid ``business_data/google/extended_business_info`` or similar.
    We report count only; freshness flagged as a sub-rule the basic
    response cannot resolve.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-21", EvidenceWeight.CONSENSUS, captured_at,
        )

    total_photos = int(gbp.get("total_photos") or 0)
    main_image = gbp.get("main_image")
    logo = gbp.get("logo")

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="GBP has >= 10 photos (Whitespark / GBP completeness baseline)",
        passed=total_photos >= 10,
        evidence={"total_photos": total_photos, "baseline": 10},
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="GBP has both a logo and a main / cover image",
        passed=bool(logo) and bool(main_image),
        evidence={
            "has_logo": bool(logo),
            "has_main_image": bool(main_image),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-21",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_photos": total_photos,
            "has_logo": bool(logo),
            "has_main_image": bool(main_image),
            "logo_url": logo,
            "main_image_url": main_image,
            "freshness_deferred": (
                "Photo upload-date data not returned by DataForSEO basic "
                "my_business_info endpoint; would need extended_business_info "
                "(paid) for per-photo timestamps to evaluate freshness rule."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
        ],
    )


# ─── P5-24 — GBP attributes ─────────────────────────────────────────────────


@register_extractor("P5-24")
async def capture_p5_24(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-24 — GBP attributes (Consensus).

    Reads ``attributes.available_attributes`` from the cached GBP
    profile. Attributes (wheelchair-accessible, women-owned,
    offers-online-appointments, etc.) help searchers filter and
    improve local-pack relevance for queries that explicitly mention
    a feature.

    Pass: at least 3 attributes declared (any category), AND a logo
    is set as the GBP profile picture (a baseline trust signal).
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-24", EvidenceWeight.CONSENSUS, captured_at,
        )

    attributes = gbp.get("attributes") or {}
    available = attributes.get("available_attributes") or {}
    unavailable = attributes.get("unavailable_attributes") or {}
    if not isinstance(available, dict):
        available = {}
    if not isinstance(unavailable, dict):
        unavailable = {}

    flat_available: list[str] = []
    available_by_category: dict[str, int] = {}
    for cat, items in available.items():
        if isinstance(items, list):
            available_by_category[cat] = len(items)
            for v in items:
                flat_available.append(f"{cat}.{v}")
    flat_unavailable: list[str] = []
    for cat, items in unavailable.items():
        if isinstance(items, list):
            for v in items:
                flat_unavailable.append(f"{cat}.{v}")

    total_available = len(flat_available)
    category_count = len(available_by_category)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 3 GBP attributes declared across any category",
        passed=total_available >= 3,
        evidence={
            "total_available": total_available,
            "by_category": available_by_category,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="GBP attributes span at least 2 distinct categories",
        passed=category_count >= 2,
        evidence={
            "category_count": category_count,
            "categories": list(available_by_category),
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-24",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_available": total_available,
            "category_count": category_count,
            "available_by_category": available_by_category,
            "available_attributes_flat": flat_available[:30],
            "unavailable_count": len(flat_unavailable),
            "unavailable_attributes_flat": flat_unavailable[:15],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
        ],
    )


# ─── P5-25 — Service area / hours completeness ──────────────────────────────


_DAYS_OF_WEEK = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)


@register_extractor("P5-25")
async def capture_p5_25(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-25 — Service area / hours completeness (Consensus).

    Reads ``work_time.work_hours.timetable`` from the cached GBP
    profile. Per Google's GBP Help, regular hours should be populated
    for every day the business operates (closed days marked closed,
    not blank).

    Externally-observable subset of the taxonomy's 7 evaluation rules:
    1. Hours declared for every day (closed days explicitly marked).
    4. Service area populated for SAB businesses — flagged as
       unmeasurable from this endpoint (DataForSEO returns 'address'
       rather than 'service_area' object; storefront businesses have
       only address).
    6. "Open 24 hours" sanity check — flag any day declared 00:00-24:00.

    Special-hours coverage (rule 2), cross-platform NAP match (rule 3),
    overreaching SAB (rule 5), and temporary closure (rule 7) are not
    derivable from this single endpoint.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-25", EvidenceWeight.CONSENSUS, captured_at,
        )

    work_time = gbp.get("work_time") or {}
    work_hours = work_time.get("work_hours") or {}
    timetable = work_hours.get("timetable") or {}
    if not isinstance(timetable, dict):
        timetable = {}

    days_declared: dict[str, dict[str, Any]] = {}
    days_missing: list[str] = []
    open_24h_days: list[str] = []
    for day in _DAYS_OF_WEEK:
        entry = timetable.get(day)
        if entry is None:
            # null means closed in DataForSEO's response convention
            days_declared[day] = {"status": "closed_or_unspecified"}
            days_missing.append(day)
            continue
        if isinstance(entry, list):
            ranges = []
            for span in entry:
                open_ = span.get("open") or {}
                close_ = span.get("close") or {}
                open_str = f"{open_.get('hour', '?'):02}:{open_.get('minute', 0):02}"
                close_str = f"{close_.get('hour', '?'):02}:{close_.get('minute', 0):02}"
                ranges.append({"open": open_str, "close": close_str})
                # "Open 24 hours" appears two ways in DataForSEO: close hour 24,
                # or a full 00:00->00:00 span. Closed days are null (handled
                # above), so a non-null 00:00-00:00 span here means all-day.
                if (
                    open_.get("hour") == 0 and open_.get("minute") == 0
                    and close_.get("minute") == 0
                    and close_.get("hour") in (24, 0)
                ):
                    open_24h_days.append(day)
            days_declared[day] = {"status": "open", "ranges": ranges}
        else:
            days_declared[day] = {"status": "unknown_format"}

    is_storefront = bool(gbp.get("address"))
    is_24x7 = len(open_24h_days) == 7

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="All 7 days of the week have a status declared (open hours OR explicit closed)",
        passed=len(days_missing) == 0,
        evidence={
            "days_missing_or_null": days_missing,
            "days_declared": {d: days_declared[d]["status"] for d in _DAYS_OF_WEEK},
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="\"Open 24 hours\" declared only when business is genuinely 24x7 (all 7 days 00:00-24:00 → genuine; mixed 24h on some days → suspicious)",
        passed=(len(open_24h_days) == 0) or is_24x7,
        evidence={
            "open_24h_days": open_24h_days,
            "is_24x7_business": is_24x7,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-25",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "days_declared": days_declared,
            "days_missing_or_null": days_missing,
            "open_24h_days": open_24h_days,
            "is_24x7_declared": is_24x7,
            "address_present": is_storefront,
            "deferred_rules": [
                "rule_2_special_hours_coverage (needs special_hours field, not in basic endpoint)",
                "rule_3_cross_platform_hours_match (needs P5-05 NAP infrastructure extended to hours)",
                "rule_4_service_area_populated (DataForSEO returns address only; service_area object not present)",
                "rule_5_service_area_not_overreaching (needs service area field)",
                "rule_7_temporary_closure (needs is_temporarily_closed flag)",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
        ],
    )


# ─── P5-23 — GBP Q&A activity ───────────────────────────────────────────────


@register_extractor("P5-23")
async def capture_p5_23(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-23 — GBP Q&A activity (Consensus).

    Reads ``questions_and_answers_count`` from cached GBP. Owner-
    seeded Q&A pairs are a Whitespark completeness criterion and
    surface in local-pack rich results.

    Pass: at least 1 Q&A pair declared. Sub-rules around owner
    response rate, recency, accuracy need
    ``extended_business_info`` (paid) — flagged as deferred.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-23", EvidenceWeight.CONSENSUS, captured_at,
        )

    qa_count = int(gbp.get("questions_and_answers_count") or 0)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="GBP has at least one Q&A pair",
        passed=qa_count >= 1,
        evidence={"questions_and_answers_count": qa_count},
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-23",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "questions_and_answers_count": qa_count,
            "deferred_rules": [
                "owner_response_rate (needs Q&A detail endpoint)",
                "response_recency (needs per-Q&A timestamps)",
                "accuracy_review (needs Q&A content + LLM evaluation)",
            ],
            "note": (
                "Basic GBP endpoint returns count only. Whitespark suggests "
                "~5+ seeded Q&A pairs for completeness; threshold here is "
                "lenient at 1 to first verify any activity."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=[
            "business_data.google.my_business_info",
        ],
    )


# ─── P5-19 — Review sentiment ──────────────────────────────────────────────


@register_extractor("P5-19")
async def capture_p5_19(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-19 — Review sentiment (Probable, distribution-based).

    Taxonomy specifies LLM-driven per-review sentiment classification
    using GBP review text. The basic DataForSEO endpoint returns
    aggregate ``rating_distribution`` (per-star vote counts) rather
    than individual reviews. We use the distribution as a directional
    sentiment signal: weighted average plus negative-share.

    Per-review LLM analysis (aspect-based sentiment, mixed-text-on-
    high-rating detection) requires the ``business_data/google/reviews``
    endpoint (paid) — flagged as deferred.

    Pass: weighted average >= 4.0 AND negative share (1- + 2-star
    votes) <= 10% of total votes.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-19", EvidenceWeight.PROBABLE, captured_at,
        )

    distribution = gbp.get("rating_distribution") or {}
    rating = gbp.get("rating") or {}
    if not isinstance(distribution, dict) or not distribution:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no rating_distribution returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.my_business_info"],
            errors=["no distribution"],
        )

    counts: dict[int, int] = {}
    total = 0
    weighted_sum = 0
    for stars_str, count in distribution.items():
        try:
            stars = int(stars_str)
            n = int(count or 0)
        except (TypeError, ValueError):
            continue
        if stars < 1 or stars > 5 or n < 0:
            continue
        counts[stars] = n
        total += n
        weighted_sum += stars * n

    if total == 0:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-19",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "rating_distribution present but no reviews to evaluate"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.my_business_info"],
            errors=["zero reviews"],
        )

    weighted_avg = round(weighted_sum / total, 2)
    negative_count = counts.get(1, 0) + counts.get(2, 0)
    neutral_count = counts.get(3, 0)
    positive_count = counts.get(4, 0) + counts.get(5, 0)
    negative_pct = round(negative_count / total * 100, 1)
    positive_pct = round(positive_count / total * 100, 1)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Weighted average rating >= 4.0 (broadly positive sentiment)",
        passed=weighted_avg >= 4.0,
        evidence={
            "weighted_average": weighted_avg,
            "total_reviews": total,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Negative share (1- and 2-star) <= 10% of total votes",
        passed=negative_pct <= 10,
        evidence={
            "negative_count": negative_count,
            "negative_pct": negative_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-19",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "weighted_average": weighted_avg,
            "total_reviews": total,
            "distribution": {f"{s}_star": counts.get(s, 0) for s in range(1, 6)},
            "negative_count": negative_count,
            "negative_pct": negative_pct,
            "neutral_count": neutral_count,
            "positive_count": positive_count,
            "positive_pct": positive_pct,
            "advertised_rating": rating.get("value"),
            "deferred_features": [
                "per_review_aspect_sentiment (needs business_data/google/reviews endpoint + LLM analysis)",
                "mixed_text_on_high_rating_detection (needs review text)",
                "service_category_sentiment_breakdown (needs review text + LLM aspect extraction)",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "business_data.google.my_business_info",
            "composition.rating_distribution_sentiment",
        ],
    )


# ─── P5-22 — GBP posts activity ────────────────────────────────────────────


@register_extractor("P5-22")
async def capture_p5_22(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-22 — GBP posts activity (Probable).

    Counts and recency of GBP posts (offers, events, news, product
    updates). Per Whitespark, posting consistency is part of the
    engagement signal cluster contributing to local pack visibility.

    Data path: the GBP API ``localPosts`` endpoint returns full post
    inventory + timestamps, but the endpoint is gated behind owner
    OAuth (verified profile owners only). The basic DataForSEO
    ``google_my_business_info`` endpoint we use for external audits
    does NOT return posts data.

    Reports UNMEASURABLE with a clear remediation path. Surfaces the
    one related externally-observable signal we DO have:
    ``is_claimed`` (a claimed profile is a prerequisite for posting).
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-22", EvidenceWeight.PROBABLE, captured_at,
        )

    is_claimed = bool(gbp.get("is_claimed"))

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-22",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "GBP posts inventory + timestamps are not returned by the "
                "DataForSEO basic my_business_info endpoint used for external "
                "auditing. The data lives in the GBP API localPosts resource, "
                "which is gated behind owner OAuth — outside SEOMATE's external-"
                "audit positioning."
            ),
            "observable_prerequisite": {
                "is_claimed": is_claimed,
                "note": (
                    "A claimed profile is a prerequisite for posting. Pixelette "
                    f"is_claimed={is_claimed}; unclaimed profiles cannot post "
                    "regardless of intent."
                ),
            },
            "remediation_paths": [
                "Scrape the public GBP card directly for post snippets (fragile, ToS-grey).",
                "DataForSEO extended_business_info / google_my_business_extended endpoint (paid, returns more fields).",
                "Owner OAuth via GBP API (requires Humza's authorisation — contradicts external-audit positioning).",
            ],
            "watchlist": True,
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.my_business_info"],
        errors=["posts data not in basic endpoint"],
    )


# ─── P5-27 — Engagement signals (owner-only metrics) ───────────────────────


@register_extractor("P5-27")
async def capture_p5_27(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-27 — Engagement signals (Probable, externally unobservable).

    Whitespark and BrightLocal both treat profile-level engagement
    metrics (clicks to website, calls, direction requests, listing
    views) as a strong contributor to local pack ranking — Google sees
    "this listing actually drives action" and rewards it.

    These metrics are tracked exclusively in the owner's GBP
    dashboard. No public API or DataForSEO endpoint exposes them,
    and they are NOT inferable from any externally-observable signal
    we can collect. Properly UNMEASURABLE from an external auditor's
    vantage point.

    Reports the structural gap with the only remediation honest to
    SEOMATE's external-audit positioning: ask the owner to share
    their GBP dashboard exports.
    """
    captured_at = _now()
    gbp = site.gbp_info
    if gbp is None:
        return _no_gbp_unmeasurable(
            ctx, site, "P5-27", EvidenceWeight.PROBABLE, captured_at,
        )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-27",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "Engagement signals (clicks, calls, direction requests, listing "
                "views) are tracked exclusively in the GBP owner dashboard. No "
                "public API or DataForSEO endpoint exposes them, and they are "
                "not inferable from any externally-observable signal. From an "
                "external auditor's vantage, this variable is structurally "
                "unmeasurable."
            ),
            "remediation_paths": [
                "Owner exports GBP Insights / Performance dashboard CSVs and uploads them into SEOMATE manually.",
                "Owner authorises the GBP API (contradicts external-audit positioning).",
            ],
            "watchlist": True,
            "applicability": "structurally_unmeasurable_externally",
        },
        rules=None,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["gbp_owner_dashboard.not_exposed"],
        errors=["owner-only data"],
    )


# ─── P5-06 — Local citations count ─────────────────────────────────────────


@register_extractor("P5-06")
async def capture_p5_06(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-06 — Local citations count (Probable).

    External-observable detection: search Google for the brand name,
    count how many recognised directory / citation platforms appear in
    the organic results. Each hit represents a citation (NAP listing)
    that Google has indexed.

    Pass: >= 3 distinct citation platforms appear in brand SERP.
    (Whitespark baseline for "active citation profile" varies by
    industry; 3 is a lenient floor.)

    Sub-rules around NAP consistency across each citation (rule 3 in
    P5-05 cross-pillar) and citation freshness are not derivable from
    SERP organic alone — they need each citation page fetched + parsed.
    """
    from seomate.pillars.p6_geo import _brand_serp_items, _DIRECTORY_CITATION_HOSTS

    captured_at = _now()
    located = _brand_serp_items(site)
    if located is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-06",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand-name SERP not present in prefetched results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )
    query, items = located
    matches: list[dict[str, Any]] = []
    seen_platforms: set[str] = set()
    for item in items:
        if item.get("type") != "organic":
            continue
        domain = (item.get("domain") or "").lower().removeprefix("www.")
        url = (item.get("url") or "").lower()
        for frag in _DIRECTORY_CITATION_HOSTS:
            if frag in domain or frag in url:
                if frag in seen_platforms:
                    break
                seen_platforms.add(frag)
                matches.append(
                    {
                        "platform": frag,
                        "domain": item.get("domain"),
                        "url": item.get("url"),
                        "title": (item.get("title") or "")[:120],
                        "rank_absolute": item.get("rank_absolute"),
                    }
                )
                break

    distinct_platforms = len(seen_platforms)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 3 distinct citation/directory platforms appear in brand SERP organic",
        passed=distinct_platforms >= 3,
        evidence={
            "distinct_platforms": distinct_platforms,
            "platforms": sorted(seen_platforms),
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-06",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "brand_query": query,
            "distinct_platforms": distinct_platforms,
            "platforms": sorted(seen_platforms),
            "matches": matches,
            "deferred_features": [
                "per_citation_NAP_consistency — cross-pillar with P5-05; needs each citation page fetched + parsed",
                "citation_freshness — needs per-listing crawl date",
                "full_citation_universe — brand SERP returns top-N hits only; the long-tail of citations (specialised directories, regional sites) need Whitespark Local Citation Finder or BrightLocal scan",
            ],
            "note": (
                "Detection via brand-name Google SERP is a strong proxy: Google "
                "indexes citation pages and ranks them on brand searches. The "
                "long-tail of small / regional / industry-specific citations "
                "may not surface in the top SERP results — full coverage would "
                "need a dedicated citation-discovery tool."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["serp.google.organic", "composition.brand_serp_citation_scan"],
    )


# ─── P5-08 — Niche/industry citation presence ──────────────────────────────


@register_extractor("P5-08")
async def capture_p5_08(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-08 — Niche/industry citation presence (Probable).

    External-observable detection: search Google for the brand name,
    count how many industry-specific platforms appear in the organic
    results. For software-dev / IT-services agencies (Pixelette's
    category), this means Clutch, GoodFirms, DesignRush, G2, Capterra,
    Crunchbase, the-manifest, etc.

    The host list in p6_geo._NICHE_TECH_AGENCY_HOSTS is curated for
    software / IT services. A future iteration should swap the list
    based on industry from P5-02 GBP primary category.

    Pass: >= 2 distinct niche platforms appear in brand SERP organic.
    """
    from seomate.pillars.p6_geo import _brand_serp_items, _NICHE_TECH_AGENCY_HOSTS

    captured_at = _now()
    located = _brand_serp_items(site)
    if located is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-08",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand-name SERP not present in prefetched results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )
    query, items = located
    matches: list[dict[str, Any]] = []
    seen_platforms: set[str] = set()
    for item in items:
        if item.get("type") != "organic":
            continue
        domain = (item.get("domain") or "").lower().removeprefix("www.")
        url = (item.get("url") or "").lower()
        for frag in _NICHE_TECH_AGENCY_HOSTS:
            if frag in domain or frag in url:
                if frag in seen_platforms:
                    break
                seen_platforms.add(frag)
                matches.append(
                    {
                        "platform": frag,
                        "domain": item.get("domain"),
                        "url": item.get("url"),
                        "title": (item.get("title") or "")[:120],
                        "rank_absolute": item.get("rank_absolute"),
                    }
                )
                break

    distinct_platforms = len(seen_platforms)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 2 distinct niche / industry platforms appear in brand SERP",
        passed=distinct_platforms >= 2,
        evidence={
            "distinct_platforms": distinct_platforms,
            "platforms": sorted(seen_platforms),
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-08",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "brand_query": query,
            "industry_assumption": "software / IT services agency (matches Pixelette GBP primary category 'Software company')",
            "distinct_platforms": distinct_platforms,
            "platforms": sorted(seen_platforms),
            "matches": matches,
            "deferred_features": [
                "industry-aware host list — currently hard-coded to software/IT services. Future version should pivot off P5-02 GBP primary category to select the right niche list (Avvo for lawyers, Healthgrades for medical, etc.).",
                "per_listing_completeness — needs each platform page fetched + parsed for NAP/profile completeness",
                "presence_on_industry_long_tail — small niche review sites won't surface in top SERP results",
            ],
            "note": (
                "Niche-host list is software-/IT-services-specific (Clutch, "
                "GoodFirms, DesignRush, G2, Capterra, Crunchbase, etc.). For "
                "businesses in other industries this variable would need a "
                "different host list selected per industry."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["serp.google.organic", "composition.brand_serp_niche_scan"],
    )


# ─── P5-07 — Local citation authority and platform diversity ───────────────


# Qualitative authority bands for citation platforms — set from
# practitioner knowledge of typical Ahrefs DR ranges. Used by P5-07
# in lieu of paid per-domain DR lookups. When DataForSEO Backlinks
# subscription lands, swap this for real DR-per-citation data.
_CITATION_TIER_HIGH = (  # ~DR 90+
    "wikipedia.org",
    "linkedin.com",
    "youtube.com",
    "crunchbase.com",
    "yelp.com",
    "yellowpages.com",
    "tripadvisor.com", "tripadvisor.co.uk",
    "bbb.org",
    "trustpilot.com", "trustpilot.co.uk",
    "g2.com",
    "find-and-update.company-information.service.gov.uk",
    "companieshouse.gov.uk",
)
_CITATION_TIER_MEDIUM = (  # ~DR 70-90
    "yelp.co.uk",
    "yell.com",
    "clutch.co",
    "goodfirms.co",
    "capterra.com",
    "softwareadvice.com",
    "getapp.com",
    "foursquare.com",
    "manta.com",
    "192.com",
    "designrush.com",
    "expertise.com",
    "ezlocal.com",
)
_CITATION_TIER_LOW = (  # ~DR 50-70 or niche
    "merchantcircle.com",
    "showmelocal.com",
    "cylex-uk.co.uk", "cylex.uk.com",
    "hotfrog.co.uk", "hotfrog.com",
    "thomsonlocal.com",
    "scoot.co.uk",
    "topdevelopers.co",
    "thinkmobiles.com",
    "appfutura.com",
    "the-manifest.com", "themanifest.com",
    "endole.co.uk",
    "duedil.com",
    "opencorporates.com",
)


def _classify_citation_tier(platform_host: str) -> str:
    """Map a citation platform host to its authority tier (high/medium/low/unknown)."""
    h = platform_host.lower().removeprefix("www.")
    for frag in _CITATION_TIER_HIGH:
        if frag in h:
            return "high"
    for frag in _CITATION_TIER_MEDIUM:
        if frag in h:
            return "medium"
    for frag in _CITATION_TIER_LOW:
        if frag in h:
            return "low"
    return "unknown"


@register_extractor("P5-07")
async def capture_p5_07(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-07 — Local citation authority and platform diversity (Probable).

    Reads the same brand-SERP scan as P5-06 / P5-08, classifies each
    detected citation platform into a qualitative authority tier
    (high / medium / low) based on practitioner-known DR ranges,
    then evaluates:
    - presence of at least one HIGH-authority citation
    - diversity across tiers (citations spread across high+medium,
      not concentrated in only one tier)

    Pass: at least 1 HIGH-tier citation AND citations span at least
    2 tiers.

    Future unlock: when DataForSEO Backlinks subscription lands,
    replace the hard-coded tier table with real DR per citation.
    """
    from seomate.pillars.p6_geo import (
        _brand_serp_items,
        _DIRECTORY_CITATION_HOSTS,
        _NICHE_TECH_AGENCY_HOSTS,
    )

    captured_at = _now()
    located = _brand_serp_items(site)
    if located is None:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-07",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "brand-name SERP not present in prefetched results"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["serp.google.organic"],
            errors=["no brand serp"],
        )

    query, items = located
    # Combine the directory + niche host lists — P5-07 considers both
    # categories of citation
    combined_hosts = set(_DIRECTORY_CITATION_HOSTS) | set(_NICHE_TECH_AGENCY_HOSTS)

    citations: list[dict[str, Any]] = []
    seen_platforms: set[str] = set()
    for item in items:
        if item.get("type") != "organic":
            continue
        domain = (item.get("domain") or "").lower().removeprefix("www.")
        url = (item.get("url") or "").lower()
        matched_host = None
        for frag in combined_hosts:
            if frag in domain or frag in url:
                matched_host = frag
                break
        if matched_host is None or matched_host in seen_platforms:
            continue
        seen_platforms.add(matched_host)
        tier = _classify_citation_tier(matched_host)
        citations.append(
            {
                "platform": matched_host,
                "tier": tier,
                "domain": item.get("domain"),
                "url": item.get("url"),
                "rank_absolute": item.get("rank_absolute"),
            }
        )

    tier_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for c in citations:
        tier_counts[c["tier"]] += 1
    distinct_tiers = sum(1 for t, n in tier_counts.items() if n > 0 and t != "unknown")
    has_high = tier_counts["high"] >= 1

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 high-authority citation present (Wikipedia / LinkedIn / Yelp / BBB / Crunchbase / Trustpilot / etc.)",
        passed=has_high,
        evidence={
            "high_tier_count": tier_counts["high"],
            "high_tier_platforms": [c["platform"] for c in citations if c["tier"] == "high"],
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Citations span at least 2 authority tiers (not concentrated in one tier)",
        passed=distinct_tiers >= 2,
        evidence={
            "distinct_tiers": distinct_tiers,
            "tier_counts": tier_counts,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-07",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "brand_query": query,
            "total_citations_detected": len(citations),
            "tier_counts": tier_counts,
            "distinct_tiers_present": distinct_tiers,
            "citations_by_tier": {
                tier: [
                    {"platform": c["platform"], "url": c["url"]}
                    for c in citations
                    if c["tier"] == tier
                ]
                for tier in ("high", "medium", "low", "unknown")
            },
            "method_note": (
                "Authority tier from hard-coded host bands (practitioner "
                "knowledge of typical Ahrefs DR ranges). When DataForSEO "
                "Backlinks subscription lands, this should be replaced with "
                "real DR per citation domain."
            ),
            "deferred_features": [
                "per_citation_real_DR (needs DataForSEO Backlinks subscription)",
                "geographic_relevance_of_citation (UK-vs-US directory tagging)",
                "citation_recency (per-listing crawl date)",
            ],
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=[
            "serp.google.organic",
            "composition.citation_authority_tiering",
        ],
    )


# ─── P5-01 — Proximity to searcher ─────────────────────────────────────────


@register_extractor("P5-01")
async def capture_p5_01(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-01 — Proximity to searcher (Consensus).

    Whitespark identifies proximity as the dominant local-pack ranking
    factor (~55% of weight). Direct measurement is impossible (each
    searcher has their own location); we approximate by checking
    whether Pixelette appears in the ``local_pack`` SERP feature on
    any of the prefetched SERPs.

    Externally we cannot vary the searcher's location without paid
    geo-shifted SERP queries (per-location cost). What we CAN see:
    when a SERP triggers a local pack (Google decided this is a
    local-intent query), does our business show up?

    Pass: at least 1 prefetched SERP triggered local_pack AND
    Pixelette appears within it.
    """
    captured_at = _now()
    gbp = site.gbp_info
    serps = site.serp_results or {}
    if not serps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-01",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no SERP prefetch results available"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["serp.google.organic"],
            errors=["no SERPs"],
        )

    our_host = site.domain.lower().removeprefix("www.")
    our_gbp_title = (gbp.get("title") if gbp else "") or ""
    our_place_id = (gbp.get("place_id") if gbp else "") or ""

    serps_with_local_pack: list[dict[str, Any]] = []
    serps_we_appear_in: list[dict[str, Any]] = []
    for kw, result in serps.items():
        items = result.get("items") or []
        # Find every local_pack block in this SERP
        for item in items:
            if item.get("type") not in ("local_pack", "map"):
                continue
            block_items = item.get("items") or []
            # Some DataForSEO local_pack blocks have a flat items array;
            # others nest. Walk both shapes.
            pack_entries = []
            if isinstance(block_items, list) and block_items:
                pack_entries.extend(block_items)
            elif "details" in item:
                pack_entries.append(item)
            # Each entry: title, place_id, url, domain typically
            entry_summaries = []
            we_in_pack = False
            for entry in pack_entries:
                if not isinstance(entry, dict):
                    continue
                e_title = (entry.get("title") or "").strip()
                e_place = (entry.get("place_id") or "").strip()
                e_domain = (entry.get("domain") or "").lower().removeprefix("www.")
                e_url = (entry.get("url") or "")
                match = False
                if our_place_id and e_place == our_place_id:
                    match = True
                elif our_gbp_title and e_title.lower() == our_gbp_title.lower():
                    match = True
                elif our_host and our_host in e_domain:
                    match = True
                entry_summaries.append(
                    {
                        "title": e_title,
                        "place_id": e_place,
                        "domain": e_domain,
                        "url": e_url,
                        "is_us": match,
                    }
                )
                if match:
                    we_in_pack = True
            serp_record = {
                "keyword": kw,
                "block_type": item.get("type"),
                "pack_entries": entry_summaries,
                "pack_size": len(entry_summaries),
                "we_in_pack": we_in_pack,
            }
            serps_with_local_pack.append(serp_record)
            if we_in_pack:
                serps_we_appear_in.append(serp_record)
            break  # one pack per SERP is enough

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least one prefetched SERP triggered a local_pack feature (means at least one query had local intent in Google's view)",
        passed=len(serps_with_local_pack) >= 1,
        evidence={
            "serps_with_local_pack_count": len(serps_with_local_pack),
            "total_serps_prefetched": len(serps),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Business appears in at least one local_pack where one was triggered",
        passed=len(serps_we_appear_in) >= 1,
        evidence={
            "serps_we_appear_in_count": len(serps_we_appear_in),
            "serps_with_local_pack_count": len(serps_with_local_pack),
            "appearances": serps_we_appear_in[:3],
        },
        notes=(
            "Auto-passes when there are no local_pack-triggering SERPs in "
            "the prefetched set (no opportunity to compete on proximity)."
        ),
    )

    rules = [rule_1, rule_2]
    # Pass if either we appear in a local pack OR there were no local-pack
    # opportunities to begin with (rule_2 auto-passes)
    if not serps_with_local_pack:
        # No local-pack triggers — variable is structurally not applicable
        # to the queried keyword set. Report PARTIAL with the rationale.
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-01",
            captured_at=captured_at,
            status=CaptureStatus.PARTIAL,
            value={
                "reason": "none of the prefetched SERPs triggered a local_pack — the queried keyword set has no local intent in Google's current view",
                "serps_prefetched": len(serps),
                "deferred_features": [
                    "geo-shifted proximity simulation (rule per taxonomy Step 4) — needs paid SERP queries with location_code shifted across the target service area",
                    "review-distribution geographic-coherence cross-check (rule 7 in P5-28) — needs reviewer location data from a paid reviews endpoint",
                ],
            },
            rules=rules,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["serp.google.organic", "composition.local_pack_appearance"],
        )

    overall = rule_1.passed and rule_2.passed
    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-01",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "serps_with_local_pack": serps_with_local_pack,
            "serps_we_appear_in_count": len(serps_we_appear_in),
            "appearances": serps_we_appear_in[:5],
            "note": (
                "Externally-observable subset: we see local_pack presence on "
                "Google's default location for the queried keyword. The full "
                "P5-01 spec calls for proximity simulation from various "
                "target-area centres (paid per-location SERP queries) — "
                "deferred. The signal here answers 'does Pixelette show up "
                "in any local-intent SERP from Google's geo-default?'"
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["serp.google.organic", "composition.local_pack_appearance"],
    )


# ─── Helpers for business-reviews-driven vars (P5-11/12/13/14/15/16/17/20) ──


def _parse_dfs_timestamp(value: Any) -> datetime | None:
    """Parse a DataForSEO timestamp string into a tz-aware datetime.

    DataForSEO Business Data Reviews returns timestamps as strings in
    formats like ``"2025-11-20 21:35:04 +00:00"`` or sometimes
    ``"2025-11-20T21:35:04+00:00"``. Both shapes parse via
    ``datetime.fromisoformat`` after normalising the space to T.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        s = value.strip().replace("Z", "+00:00")
        # Replace first space with 'T' when followed by digits (datetime format)
        if " " in s and "T" not in s:
            try:
                date_part, rest = s.split(" ", 1)
                s = f"{date_part}T{rest}"
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _parse_review_timestamp(review: dict) -> datetime | None:
    """Extract the review's posted-at timestamp."""
    return _parse_dfs_timestamp(review.get("timestamp"))


def _has_owner_response(review: dict) -> bool:
    """True iff the review has an owner answer."""
    ans = review.get("owner_answer")
    return isinstance(ans, str) and ans.strip() != ""


def _owner_response_timestamp(review: dict) -> datetime | None:
    """Extract the owner-response timestamp (top-level field on the review)."""
    return _parse_dfs_timestamp(review.get("owner_timestamp"))


# ─── P5-12 — Review recency ─────────────────────────────────────────────────


@register_extractor("P5-12")
async def capture_p5_12(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-12 — Review recency (Consensus).

    Per Whitespark / BrightLocal, listings with recent reviews
    outperform listings whose reviews are years old — fresh reviews
    signal an active business and Google's local-pack ranking
    correlates with this.

    Pass: latest review within the last 90 days AND at least one
    review within the last 30 days (active recent flow).
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-12",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no review records returned by DataForSEO Reviews endpoint "
                    "— either the GBP has no public reviews OR the reviews "
                    "task failed / timed out"
                ),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    now = _now()
    timestamps: list[datetime] = []
    for r in reviews:
        ts = _parse_review_timestamp(r)
        if ts is not None:
            timestamps.append(ts)

    if not timestamps:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-12",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "reviews returned but none have parseable timestamps",
                "reviews_returned": len(reviews),
            },
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["business_data.google.reviews"],
            errors=["no timestamps"],
        )

    latest = max(timestamps)
    days_since_latest = (now - latest).days
    last_30_count = sum(1 for t in timestamps if (now - t).days <= 30)
    last_90_count = sum(1 for t in timestamps if (now - t).days <= 90)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Latest review within the last 90 days",
        passed=days_since_latest <= 90,
        evidence={
            "days_since_latest_review": days_since_latest,
            "latest_review_at": latest.isoformat(),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="At least 1 review in the last 30 days",
        passed=last_30_count >= 1,
        evidence={
            "reviews_last_30d": last_30_count,
            "reviews_last_90d": last_90_count,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-12",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "reviews_inspected": len(reviews),
            "reviews_with_timestamp": len(timestamps),
            "latest_review_at": latest.isoformat(),
            "days_since_latest_review": days_since_latest,
            "reviews_last_30d": last_30_count,
            "reviews_last_90d": last_90_count,
            "oldest_review_at": min(timestamps).isoformat(),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.reviews", "composition.review_recency"],
    )


# ─── P5-13 — Review response rate ──────────────────────────────────────────


@register_extractor("P5-13")
async def capture_p5_13(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-13 — Review response rate (Consensus).

    The fraction of reviews the business owner has responded to.
    Whitespark identifies response rate as a primary engagement
    signal — responding to reviews demonstrates active management
    and improves customer perception. BrightLocal surveys show
    consumers expect a response within 1-7 days.

    Pass: >= 50% of reviews have an owner response.
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-13",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.CONSENSUS,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    total = len(reviews)
    with_response = sum(1 for r in reviews if _has_owner_response(r))
    response_pct = round(with_response / total * 100, 1) if total else 0
    no_response_sample: list[dict[str, Any]] = []
    for r in reviews:
        if _has_owner_response(r):
            continue
        rating = r.get("rating") or {}
        rating_val = rating.get("value") if isinstance(rating, dict) else rating
        no_response_sample.append(
            {
                "rating": rating_val,
                "snippet": (r.get("review_text") or r.get("text") or "")[:120],
            }
        )
        if len(no_response_sample) >= 5:
            break

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 50% of reviews have an owner response",
        passed=response_pct >= 50,
        evidence={
            "reviews_with_response": with_response,
            "total_reviews": total,
            "response_pct": response_pct,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-13",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_reviews": total,
            "reviews_with_response": with_response,
            "response_pct": response_pct,
            "no_response_sample": no_response_sample,
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.reviews", "composition.response_rate"],
    )


# ─── P5-15 — Review response speed ─────────────────────────────────────────


@register_extractor("P5-15")
async def capture_p5_15(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-15 — Review response speed (Probable).

    The median lag between a review being posted and the owner's
    response. Faster response signals attentiveness; BrightLocal
    surveys cite a 1-7 day expectation. Slow responses (>14 days)
    suggest unmonitored profile management.

    Pass: median response lag <= 7 days AND no individual response
    > 30 days late.
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-15",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    lags_days: list[float] = []
    no_lag_count = 0
    for r in reviews:
        if not _has_owner_response(r):
            continue
        rev_ts = _parse_review_timestamp(r)
        resp_ts = _owner_response_timestamp(r)
        if rev_ts is None or resp_ts is None:
            no_lag_count += 1
            continue
        lag_seconds = (resp_ts - rev_ts).total_seconds()
        if lag_seconds < 0:
            # owner-response before the review timestamp is a data quirk;
            # ignore
            continue
        lags_days.append(lag_seconds / 86400.0)

    if not lags_days:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-15",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no owner-response pairs with both review and response timestamps",
                "reviews_inspected": len(reviews),
                "responses_with_unparseable_timestamps": no_lag_count,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no usable response lags"],
        )

    sorted_l = sorted(lags_days)
    median_days = round(sorted_l[len(sorted_l) // 2], 1)
    max_days = round(sorted_l[-1], 1)
    mean_days = round(sum(lags_days) / len(lags_days), 1)
    slow_responses = [d for d in lags_days if d > 30]

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="Median response lag <= 7 days",
        passed=median_days <= 7,
        evidence={
            "median_lag_days": median_days,
            "mean_lag_days": mean_days,
            "responses_measured": len(lags_days),
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="No individual response > 30 days late",
        passed=len(slow_responses) == 0,
        evidence={
            "slow_response_count": len(slow_responses),
            "max_lag_days": max_days,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-15",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "responses_measured": len(lags_days),
            "median_lag_days": median_days,
            "mean_lag_days": mean_days,
            "max_lag_days": max_days,
            "slow_response_count": len(slow_responses),
            "responses_with_unparseable_timestamps": no_lag_count,
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews", "composition.response_lag"],
    )


# ─── P5-28 — Location demotion (irrelevant geography) ──────────────────────


@register_extractor("P5-28")
async def capture_p5_28(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-28 — Location demotion / irrelevant geography (Consensus).

    Per the taxonomy's 7-rule check, location-demotion detection
    requires:
    - service-area-vs-operational-reality matching (needs operations
      records the auditor doesn't have)
    - doorway-page detection across geo-targeted pages (we have site
      audits but no per-page geo-tagging)
    - schema areaServed cross-checking (we have structured_data)
    - reviewer geographic distribution (needs paid review endpoint)
    - geo-shifted SERP queries (paid per location)

    Most rules need data SEOMATE doesn't currently fetch. Reports as
    UNMEASURABLE with the remediation path documented. Records two
    proxies we CAN observe: service-area / address declared on GBP,
    schema areaServed declarations on the site.
    """
    captured_at = _now()
    gbp = site.gbp_info

    # Observable proxies (cheap structured-data scan)
    schema_area_served: list[str] = []
    if site.structured_data:
        for sd in site.structured_data.values():
            for block in sd.schema_org_blocks:
                if "LocalBusiness" not in block.types and "Organization" not in block.types:
                    continue
                area = block.raw.get("areaServed")
                if isinstance(area, str) and area.strip():
                    schema_area_served.append(area.strip()[:80])
                elif isinstance(area, list):
                    for a in area:
                        if isinstance(a, str):
                            schema_area_served.append(a.strip()[:80])
                        elif isinstance(a, dict):
                            n = a.get("name")
                            if isinstance(n, str):
                                schema_area_served.append(n.strip()[:80])

    gbp_address = (gbp.get("address") if gbp else "") or ""

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-28",
        captured_at=captured_at,
        status=CaptureStatus.UNMEASURABLE,
        value={
            "reason": (
                "Location demotion detection requires data SEOMATE doesn't "
                "currently fetch: geo-shifted SERP queries (paid per "
                "location), reviewer geographic distribution (paid reviews "
                "endpoint), and operational-records matching (not "
                "externally observable)."
            ),
            "observable_proxies": {
                "gbp_address": gbp_address,
                "schema_areaServed_declarations": schema_area_served[:10],
                "note": (
                    "These two signals form the 'declared geography' side "
                    "of the rule set. Rule 5 (schema areaServed matches GBP "
                    "service area) IS partially auditable from these — "
                    "but the full demotion check needs the other inputs."
                ),
            },
            "remediation_paths": [
                "Geo-shifted SERP prefetch: run brand + service-keyword SERPs from N location codes covering the target service area (~$0.002 per location). Detects geographies where the business unexpectedly does or doesn't appear.",
                "DataForSEO Business Data Reviews endpoint: pulls reviewer geographic distribution → cross-check rule 7.",
                "Manual operational audit: human reviewer compares declared service area to actual customer fulfilment records.",
            ],
            "watchlist": True,
        },
        rules=None,
        evidence_weight=EvidenceWeight.CONSENSUS,
        data_sources=["business_data.google.my_business_info", "extruct.parse_structured_data"],
        errors=["needs geo-SERP + reviews endpoint"],
    )


# ─── P5-11 — Review velocity ───────────────────────────────────────────────


@register_extractor("P5-11")
async def capture_p5_11(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-11 — Review velocity (Probable).

    Rate at which new reviews accrue. Steady inflow signals an
    active, in-demand business; declining velocity or long gaps
    correlates with weakening local-pack performance.

    Computes:
    - Reviews per 30-day window across the historical inventory
    - Mean and max gap between consecutive reviews
    - Trend: are the recent 90 days outpacing or trailing the
      historical baseline?

    Pass:
    - At least 1 review in the last 90 days, AND
    - Recent-90-day rate is >= 50% of the historical 12-month rate
      (no severe deceleration)
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned by DataForSEO Reviews endpoint"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    now = _now()
    timestamps: list[datetime] = []
    for r in reviews:
        ts = _parse_review_timestamp(r)
        if ts is not None:
            timestamps.append(ts)

    if len(timestamps) < 2:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-11",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "fewer than 2 reviews with parseable timestamps; velocity needs at least 2 data points",
                "reviews_with_timestamp": len(timestamps),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["fewer than 2 parseable timestamps"],
        )

    timestamps.sort()
    earliest = timestamps[0]
    latest = timestamps[-1]
    span_days = max(1, (latest - earliest).days)

    gaps_days = [
        (timestamps[i] - timestamps[i - 1]).days
        for i in range(1, len(timestamps))
    ]
    mean_gap = round(sum(gaps_days) / len(gaps_days), 1)
    max_gap = max(gaps_days)

    last_90_count = sum(1 for ts in timestamps if (now - ts).days <= 90)
    last_180_count = sum(1 for ts in timestamps if (now - ts).days <= 180)
    last_365_count = sum(1 for ts in timestamps if (now - ts).days <= 365)

    # Historical rate (per 90 days) computed over full span; recent rate
    # over last 365 days. Use rate_per_90d so the comparison units match.
    full_rate_per_90d = round(len(timestamps) / span_days * 90, 2)
    recent_rate_per_90d = round(last_90_count, 2)

    decel_ratio = (
        round(recent_rate_per_90d / full_rate_per_90d, 2)
        if full_rate_per_90d > 0
        else None
    )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="At least 1 review in the last 90 days (recent activity)",
        passed=last_90_count >= 1,
        evidence={
            "last_90d_count": last_90_count,
            "days_since_latest_review": (now - latest).days,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="Recent 90-day rate >= 50% of historical baseline (no severe deceleration)",
        passed=(decel_ratio is not None and decel_ratio >= 0.5),
        evidence={
            "recent_rate_per_90d": recent_rate_per_90d,
            "historical_rate_per_90d": full_rate_per_90d,
            "deceleration_ratio": decel_ratio,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-11",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "reviews_sampled": len(timestamps),
            "earliest_review": earliest.isoformat(),
            "latest_review": latest.isoformat(),
            "span_days": span_days,
            "mean_gap_days": mean_gap,
            "max_gap_days": max_gap,
            "last_90d_count": last_90_count,
            "last_180d_count": last_180_count,
            "last_365d_count": last_365_count,
            "historical_rate_per_90d": full_rate_per_90d,
            "recent_rate_per_90d": recent_rate_per_90d,
            "deceleration_ratio": decel_ratio,
            "note": (
                "Velocity uses the sample of reviews DataForSEO returned "
                "(depth-bounded). Sites with very few reviews will show "
                "high gap variance. Long gaps + recent silence is the "
                "actionable signal."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews"],
    )


# ─── P5-14 — Review response personalisation ───────────────────────────────


# Generic response templates that signal copy-paste owner replies.
# Sourced from typical patterns observed in local-business owner-response
# audits.
_GENERIC_RESPONSE_PATTERNS = (
    "thank you for your review",
    "thanks for your review",
    "thank you for taking the time",
    "we appreciate your feedback",
    "thank you for your feedback",
    "we appreciate your business",
    "glad you had a great experience",
    "we look forward to seeing you again",
    "we hope to see you again",
    "thanks for choosing us",
    "thank you for choosing us",
)


def _is_generic_response(text: str) -> tuple[bool, list[str]]:
    """Heuristic: response is mostly a generic template if no
    personalised content (no first-person specifics, no reviewer name,
    no service mention, short length).

    Returns (is_generic, matched_patterns).
    """
    if not text or len(text.strip()) < 20:
        return True, ["too short"]
    lower = text.lower()
    matches = [p for p in _GENERIC_RESPONSE_PATTERNS if p in lower]
    if matches and len(text) < 120:
        # Short response with template phrase = almost certainly generic
        return True, matches
    return False, matches


@register_extractor("P5-14")
async def capture_p5_14(
    ctx: AdapterContext,
    site: SiteData,
    *,
    llm: LlmAdapter,
) -> CaptureRecord:
    """P5-14 — Review response personalisation (Probable, LLM-assisted).

    Owner responses that mention specifics (the reviewer's name, the
    service they used, a personalised follow-up) signal active
    engagement. Copy-paste template responses ("Thank you for your
    review!") signal automated handling and fail to build the trust
    Google's local-pack quality signals reward.

    Two-pass:
    1. Heuristic generic-template detection on response text
    2. LLM (Haiku) classification of remaining responses as
       personalised / partially-personalised / generic

    Pass: >= 50% of responses classified as personalised.
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-14",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews", "llm.anthropic_haiku"],
            errors=["no reviews"],
        )

    with_response: list[dict[str, Any]] = []
    for r in reviews:
        if not _has_owner_response(r):
            continue
        with_response.append(
            {
                "owner_answer": r.get("owner_answer", "")[:600],
                "review_text": (r.get("review_text") or r.get("text") or "")[:200],
                "reviewer": r.get("profile_name") or r.get("reviewer_name") or "",
            }
        )

    if not with_response:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-14",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no reviews have owner responses; personalisation is "
                    "undefined when there are no responses to classify. "
                    "See P5-13 (response rate) for the underlying gap."
                ),
                "total_reviews": len(reviews),
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no owner responses"],
        )

    # Pass 1: heuristic generic detection
    heuristic_generic = 0
    candidates_for_llm: list[tuple[int, dict[str, Any]]] = []
    for i, item in enumerate(with_response):
        is_generic, _ = _is_generic_response(item["owner_answer"])
        if is_generic:
            heuristic_generic += 1
        else:
            candidates_for_llm.append((i, item))

    # Pass 2: LLM classification of the remaining (non-trivially-generic)
    llm_personalised = 0
    llm_partial = 0
    llm_generic = 0
    llm_unclassified = 0
    llm_examples_personalised: list[dict[str, Any]] = []
    llm_examples_generic: list[dict[str, Any]] = []

    if candidates_for_llm and llm.is_configured:
        sample_payload = [
            {
                "idx": idx,
                "owner_response": it["owner_answer"][:400],
                "reviewer_name": it["reviewer"],
                "review_snippet": it["review_text"][:150],
            }
            for idx, it in candidates_for_llm
        ]
        system_prompt = (
            "You are auditing how a business responds to its Google reviews. "
            "For each owner response, classify whether it is genuinely "
            "personalised (mentions the reviewer's name OR the specific "
            "service/situation in the review), partially personalised "
            "(some specifics but mostly templated), or generic "
            "(template thanks with no specifics). Reply ONLY with a JSON "
            "array."
        )
        user_prompt = (
            "For each item below, return a JSON object with: `idx` (int), "
            "`personalisation` (one of: 'personalised', 'partial', "
            "'generic'), and `reason` (short string, ≤ 100 chars). Return "
            "one object per input item.\n\n"
            f"Responses:\n{_json.dumps(sample_payload, ensure_ascii=False)}"
        )
        try:
            result = await llm.batch_evaluate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
            parsed = result.parsed if result.parsed else []
        except (LlmNotConfigured, Exception):  # noqa: BLE001
            parsed = []

        by_idx = {int(c.get("idx", -1)): c for c in parsed if isinstance(c, dict)}
        for idx, item in candidates_for_llm:
            cls = by_idx.get(idx)
            if cls is None:
                llm_unclassified += 1
                continue
            label = (cls.get("personalisation") or "").lower()
            example = {
                "owner_response_snippet": item["owner_answer"][:200],
                "reviewer_name": item["reviewer"],
                "reason": cls.get("reason", ""),
            }
            if label == "personalised":
                llm_personalised += 1
                if len(llm_examples_personalised) < 8:
                    llm_examples_personalised.append(example)
            elif label == "partial":
                llm_partial += 1
            elif label == "generic":
                llm_generic += 1
                if len(llm_examples_generic) < 8:
                    llm_examples_generic.append(example)
            else:
                llm_unclassified += 1
    else:
        # No LLM available — treat all non-heuristic-generic as "partial"
        # (we can't confidently distinguish personalised from partial
        # without LLM, so the fall-back is conservative).
        llm_partial = len(candidates_for_llm)

    total = len(with_response)
    total_generic = heuristic_generic + llm_generic
    personalised_pct = round(llm_personalised / total * 100, 1) if total else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 50% of responses classified as personalised",
        passed=personalised_pct >= 50.0,
        evidence={
            "personalised_count": llm_personalised,
            "personalised_pct": personalised_pct,
            "total_responses": total,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-14",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_responses": total,
            "heuristic_generic": heuristic_generic,
            "llm_personalised": llm_personalised,
            "llm_partial": llm_partial,
            "llm_generic": llm_generic,
            "llm_unclassified": llm_unclassified,
            "total_generic": total_generic,
            "personalised_pct": personalised_pct,
            "llm_examples_personalised": llm_examples_personalised,
            "llm_examples_generic": llm_examples_generic,
            "note": (
                "Two-pass: heuristic flags trivially-templated responses "
                "('thanks for your review' under 120 chars), LLM grades "
                "the rest. When LLM is unavailable, non-trivially-generic "
                "responses fall back to 'partial' so the rule fails "
                "conservatively rather than passing falsely."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews", "llm.anthropic_haiku"],
    )


# ─── P5-16 — Review keyword content ────────────────────────────────────────


@register_extractor("P5-16")
async def capture_p5_16(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-16 — Review keyword content (Probable).

    Reviews that mention specific services, products, or locations
    pass topical signals to Google's local-pack algorithm. A review
    that says "Pixelette built our custom CRM, great team in
    Manchester" is more valuable than "Great company, recommend!"
    because Google can tie the mention to the searcher's query.

    Detects mentions of:
    - Brand variants (already known from the site brand config)
    - Service keywords (extracted from the audited site's own
      page titles — the services we say we offer)
    - Location keywords (locality / region from any address /
      "in [city]" mentions on the site)

    Pass:
    - >= 30% of reviews mention at least one service keyword OR
      one location keyword
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    # Build keyword lexicon
    service_keywords: set[str] = set()
    # From page titles — services pattern (most pages on a services site
    # have a title like "X Services" or "X Development")
    for url, audit in site.page_audits.items():
        title = (audit.title or "").lower()
        # Pull noun phrases by stripping marketing suffixes
        title = re.sub(r"\s+\|\s+.*$", "", title).strip()
        title = re.sub(r"\s+services\s*$", " services", title)
        title = re.sub(r"\s+development\s*$", " development", title)
        if title and len(title) < 80:
            service_keywords.add(title)

    # Brand variants
    brand_variants: tuple[str, ...] = ()
    if site.brand:
        brand_variants = site.brand.all_variants

    # Location keywords from GBP if present
    location_keywords: set[str] = set()
    if site.gbp_info:
        for key in ("city", "locality", "region", "country_name", "address"):
            val = site.gbp_info.get(key)
            if isinstance(val, str) and val.strip():
                location_keywords.add(val.strip().lower())

    if not service_keywords and not brand_variants and not location_keywords:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-16",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": "no service / brand / location lexicon derivable from site",
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no lexicon"],
        )

    total = len(reviews)
    with_service = 0
    with_brand = 0
    with_location = 0
    rich_examples: list[dict[str, Any]] = []
    for r in reviews:
        text = (r.get("review_text") or r.get("text") or "").lower()
        if not text:
            continue
        s_hit = any(sk in text for sk in service_keywords)
        b_hit = any(bv.lower() in text for bv in brand_variants)
        l_hit = any(lk in text for lk in location_keywords)
        if s_hit:
            with_service += 1
        if b_hit:
            with_brand += 1
        if l_hit:
            with_location += 1
        if (s_hit or l_hit) and len(rich_examples) < 8:
            rating = r.get("rating") or {}
            rating_val = rating.get("value") if isinstance(rating, dict) else rating
            rich_examples.append(
                {
                    "rating": rating_val,
                    "snippet": text[:200],
                    "service_match": s_hit,
                    "location_match": l_hit,
                    "brand_match": b_hit,
                }
            )

    keyword_rich = sum(
        1
        for r in reviews
        if (
            any(sk in (r.get("review_text") or r.get("text") or "").lower()
                for sk in service_keywords)
            or any(lk in (r.get("review_text") or r.get("text") or "").lower()
                   for lk in location_keywords)
        )
    )
    keyword_rich_pct = round(keyword_rich / total * 100, 1) if total else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 30% of reviews mention at least one service or location keyword",
        passed=keyword_rich_pct >= 30.0,
        evidence={
            "keyword_rich_count": keyword_rich,
            "keyword_rich_pct": keyword_rich_pct,
            "total_reviews": total,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-16",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_reviews": total,
            "reviews_mentioning_service": with_service,
            "reviews_mentioning_brand": with_brand,
            "reviews_mentioning_location": with_location,
            "keyword_rich_reviews": keyword_rich,
            "keyword_rich_pct": keyword_rich_pct,
            "service_keywords_count": len(service_keywords),
            "location_keywords_count": len(location_keywords),
            "rich_examples": rich_examples,
            "note": (
                "Keyword-rich reviews pass topical signals to Google "
                "Maps' local-pack algorithm. Sparse keyword-rich rates "
                "are usually a process gap: the business doesn't ask "
                "reviewers to mention which service they used or where "
                "the work happened."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews", "composition.site_lexicon"],
    )


# ─── P5-17 — Review photos / videos ────────────────────────────────────────


@register_extractor("P5-17")
async def capture_p5_17(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-17 — Review photos / videos (Probable).

    Reviews with attached photos / videos carry more weight in
    Google's local-pack ranking and convert better at the decision
    stage. They also signal authentic real-customer reviews vs
    text-only batch-submitted reviews.

    Counts reviews where DataForSEO surfaces image / video metadata.
    Field names vary across DataForSEO snapshots; we check several
    common shapes.

    Pass: >= 10% of reviews have at least one media attachment.
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-17",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    def has_media(r: dict) -> tuple[bool, dict[str, Any]]:
        # DataForSEO surfaces media via photos_count (int) and images
        # (list). Both can be 0/None when no media is attached. Also
        # check fallback shapes in case payload changes.
        sig: dict[str, Any] = {}
        for key in ("photos_count", "images_count", "photo_count"):
            v = r.get(key)
            if isinstance(v, int) and v > 0:
                sig[key] = v
        for key in ("images", "photos"):
            v = r.get(key)
            if isinstance(v, list) and v:
                sig[key] = len(v)
        for key in ("videos_count", "video_count", "videos"):
            v = r.get(key)
            if isinstance(v, int) and v > 0:
                sig[key] = v
            elif isinstance(v, list) and v:
                sig[key] = len(v)
        return bool(sig), sig

    total = len(reviews)
    with_media = 0
    media_examples: list[dict[str, Any]] = []
    field_signatures: set[str] = set()
    for r in reviews:
        hit, sig = has_media(r)
        if hit:
            with_media += 1
            field_signatures.update(sig.keys())
            if len(media_examples) < 5:
                rating = r.get("rating") or {}
                rating_val = rating.get("value") if isinstance(rating, dict) else rating
                media_examples.append(
                    {
                        "rating": rating_val,
                        "media_fields": sig,
                        "snippet": (r.get("review_text") or r.get("text") or "")[:120],
                    }
                )

    media_pct = round(with_media / total * 100, 1) if total else 0.0

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 10% of reviews have at least one media attachment",
        passed=media_pct >= 10.0,
        evidence={
            "media_count": with_media,
            "media_pct": media_pct,
            "total_reviews": total,
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-17",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_reviews": total,
            "reviews_with_media": with_media,
            "media_pct": media_pct,
            "media_field_signatures_seen": sorted(field_signatures),
            "media_examples": media_examples,
            "note": (
                "Field names vary across DataForSEO snapshots — checked "
                "images_count / photo_count / images / photos and the "
                "video variants. If 'media_field_signatures_seen' is "
                "empty AND with_media is 0, this is likely a payload-"
                "shape mismatch rather than zero actual media; verify "
                "against the raw Google Maps listing before trusting "
                "a zero result."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews"],
    )


# ─── P5-20 — Fake review detection / authenticity ──────────────────────────


@register_extractor("P5-20")
async def capture_p5_20(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-20 — Fake review detection / authenticity (Probable).

    Google's anti-fake-review policies devalue listings caught with
    coordinated/bot/competitor-attack reviews. Detection heuristics:

    1. **Suspicious clustering**: many reviews on the same day or
       within a tight window relative to overall review velocity
    2. **Generic ultra-short positive reviews**: text length < 30
       chars with only positive sentiment and no specifics
    3. **Repeated text patterns**: many reviews using the same exact
       phrasing (template review-farm signature)
    4. **5-star bias outlier**: nearly-perfect 5-star streaks with
       no 4 / 3-star organic variance

    Pass: <= 2 distinct suspicious patterns triggered. 0 = healthy,
    3+ = investigate.
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-20",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    flags: list[dict[str, Any]] = []
    timestamps: list[datetime] = []
    texts: list[str] = []
    ratings: list[int] = []
    for r in reviews:
        ts = _parse_review_timestamp(r)
        if ts is not None:
            timestamps.append(ts)
        text = (r.get("review_text") or r.get("text") or "").strip()
        texts.append(text)
        rating = r.get("rating") or {}
        rating_val = rating.get("value") if isinstance(rating, dict) else rating
        try:
            ratings.append(int(rating_val) if rating_val is not None else 0)
        except (TypeError, ValueError):
            ratings.append(0)

    # Heuristic 1: clustering on the same day
    from collections import Counter
    day_counts = Counter(ts.date() for ts in timestamps)
    same_day_clusters = [
        (str(d), n) for d, n in day_counts.items() if n >= 3
    ]
    if same_day_clusters:
        flags.append(
            {
                "pattern": "same_day_clusters",
                "detail": same_day_clusters,
                "explanation": "3+ reviews posted on the same day",
            }
        )

    # Heuristic 2: ultra-short positive reviews
    ultra_short_positive = sum(
        1
        for t, rt in zip(texts, ratings)
        if 0 < len(t) <= 30 and rt >= 4
    )
    ultra_short_pct = (
        round(ultra_short_positive / len(reviews) * 100, 1)
        if reviews
        else 0.0
    )
    if ultra_short_pct >= 20.0:
        flags.append(
            {
                "pattern": "ultra_short_positive",
                "count": ultra_short_positive,
                "pct_of_total": ultra_short_pct,
                "explanation": ">=20% of reviews are <=30 chars with 4/5 stars",
            }
        )

    # Heuristic 3: repeated text patterns
    text_normalised = [
        re.sub(r"\s+", " ", t.lower()).strip() for t in texts if t
    ]
    dup_counts = Counter(text_normalised)
    duplicates = [(t, n) for t, n in dup_counts.items() if n >= 2 and len(t) > 15]
    if duplicates:
        flags.append(
            {
                "pattern": "duplicate_text",
                "count": len(duplicates),
                "examples": duplicates[:5],
                "explanation": "identical review text repeated across distinct reviews",
            }
        )

    # Heuristic 4: 5-star bias outlier (no 4-star variance)
    if ratings:
        five_star = sum(1 for r in ratings if r == 5)
        five_star_pct = round(five_star / len(ratings) * 100, 1)
        four_star = sum(1 for r in ratings if r == 4)
        if five_star_pct >= 95.0 and len(ratings) >= 10 and four_star == 0:
            flags.append(
                {
                    "pattern": "five_star_bias",
                    "five_star_pct": five_star_pct,
                    "four_star_count": four_star,
                    "explanation": "95%+ 5-star with zero 4-stars (no organic variance)",
                }
            )

    flag_count = len(flags)

    rule_1 = RuleResult(
        rule_id=1,
        rule_text="<= 2 distinct authenticity-suspicion patterns triggered",
        passed=flag_count <= 2,
        evidence={
            "flag_count": flag_count,
            "patterns_triggered": [f["pattern"] for f in flags],
        },
    )

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-20",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if rule_1.passed else CaptureStatus.FAILED,
        value={
            "total_reviews": len(reviews),
            "flag_count": flag_count,
            "flags": flags,
            "rating_distribution": dict(Counter(ratings)),
            "ultra_short_positive_count": ultra_short_positive,
            "note": (
                "Pattern-based detection only — flags are signals, not "
                "verdicts. Google's own anti-fake-review system uses "
                "device fingerprints, behavioural patterns, and "
                "reviewer history that we cannot see. Use these as "
                "starting points for manual review of suspicious "
                "clusters."
            ),
        },
        rules=[rule_1],
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews", "composition.pattern_detection"],
    )


# ─── P5-18 — Reviewer credibility (history) ────────────────────────────────


@register_extractor("P5-18")
async def capture_p5_18(
    ctx: AdapterContext,
    site: SiteData,
) -> CaptureRecord:
    """P5-18 — Reviewer credibility / history (Probable).

    Reviews from Local Guides and high-history reviewers carry more
    weight in Google's local-pack algorithm than reviews from
    single-review accounts. DataForSEO's reviews payload exposes:

    - ``local_guide`` (bool) — whether the reviewer is a Local Guide
    - ``reviews_count`` (int) — total reviews this reviewer has left
      across all businesses on Google Maps
    - ``photos_count`` (int) — total photos contributed by this
      reviewer

    Pass:
    - At least 30% of reviews are from Local Guides OR from reviewers
      with >= 5 historical reviews (substantive history threshold)
    - <= 30% of reviews are from single-review accounts (likely
      one-off reviewers; high share = coordinated submission risk)
    """
    captured_at = _now()
    reviews = site.business_reviews
    if not reviews:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={"reason": "no review records returned"},
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviews"],
        )

    total = len(reviews)
    local_guides = 0
    substantive_history = 0  # >= 5 historical reviews
    single_review = 0
    no_history_data = 0
    reviewer_distribution: dict[str, int] = {
        "0": 0, "1": 0, "2-4": 0, "5-9": 0, "10-19": 0, "20+": 0,
    }
    credible_examples: list[dict[str, Any]] = []
    single_review_examples: list[dict[str, Any]] = []

    for r in reviews:
        is_lg = bool(r.get("local_guide"))
        rev_count_raw = r.get("reviews_count")
        try:
            rev_count = int(rev_count_raw) if rev_count_raw is not None else None
        except (TypeError, ValueError):
            rev_count = None

        if rev_count is None:
            no_history_data += 1
        elif rev_count == 0:
            reviewer_distribution["0"] += 1
            single_review += 1  # 0-history is effectively single-shot
        elif rev_count == 1:
            reviewer_distribution["1"] += 1
            single_review += 1
        elif rev_count < 5:
            reviewer_distribution["2-4"] += 1
        elif rev_count < 10:
            reviewer_distribution["5-9"] += 1
        elif rev_count < 20:
            reviewer_distribution["10-19"] += 1
        else:
            reviewer_distribution["20+"] += 1

        is_substantive = (rev_count is not None and rev_count >= 5) or is_lg
        if is_lg:
            local_guides += 1
        if is_substantive:
            substantive_history += 1
            if len(credible_examples) < 8:
                credible_examples.append(
                    {
                        "reviewer": r.get("profile_name", ""),
                        "reviews_count": rev_count,
                        "photos_count": r.get("photos_count"),
                        "local_guide": is_lg,
                        "profile_url": r.get("profile_url", ""),
                    }
                )
        else:
            if (rev_count is not None and rev_count <= 1) and len(single_review_examples) < 5:
                single_review_examples.append(
                    {
                        "reviewer": r.get("profile_name", ""),
                        "reviews_count": rev_count,
                        "rating": (r.get("rating") or {}).get("value"),
                        "profile_url": r.get("profile_url", ""),
                    }
                )

    substantive_pct = round(substantive_history / total * 100, 1) if total else 0.0
    single_review_pct = round(single_review / total * 100, 1) if total else 0.0
    local_guide_pct = round(local_guides / total * 100, 1) if total else 0.0

    if no_history_data == total:
        return _build_record(
            ctx=ctx,
            site=site,
            variable_id="P5-18",
            captured_at=captured_at,
            status=CaptureStatus.UNMEASURABLE,
            value={
                "reason": (
                    "no reviewers in the sample had a reviews_count field — "
                    "DataForSEO payload may have changed shape; verify "
                    "against the raw response."
                ),
                "total_reviews": total,
            },
            rules=None,
            evidence_weight=EvidenceWeight.PROBABLE,
            data_sources=["business_data.google.reviews"],
            errors=["no reviewer history data"],
        )

    rule_1 = RuleResult(
        rule_id=1,
        rule_text=">= 30% of reviews from Local Guides OR reviewers with 5+ historical reviews",
        passed=substantive_pct >= 30.0,
        evidence={
            "substantive_count": substantive_history,
            "substantive_pct": substantive_pct,
            "total_reviews": total,
        },
    )
    rule_2 = RuleResult(
        rule_id=2,
        rule_text="<= 30% of reviews from single-review / no-history accounts",
        passed=single_review_pct <= 30.0,
        evidence={
            "single_review_count": single_review,
            "single_review_pct": single_review_pct,
        },
    )

    rules = [rule_1, rule_2]
    overall = rule_1.passed and rule_2.passed

    return _build_record(
        ctx=ctx,
        site=site,
        variable_id="P5-18",
        captured_at=captured_at,
        status=CaptureStatus.PASSED if overall else CaptureStatus.FAILED,
        value={
            "total_reviews": total,
            "local_guides": local_guides,
            "local_guide_pct": local_guide_pct,
            "substantive_history_count": substantive_history,
            "substantive_history_pct": substantive_pct,
            "single_review_count": single_review,
            "single_review_pct": single_review_pct,
            "no_history_data_count": no_history_data,
            "reviewer_history_distribution": reviewer_distribution,
            "credible_reviewer_examples": credible_examples,
            "single_review_examples": single_review_examples,
            "note": (
                "Reviewer credibility uses DataForSEO's public fields: "
                "local_guide bool, reviews_count (total reviews this "
                "reviewer has left on Google), and photos_count. Local "
                "Guides carry Google's explicit weight; reviewers with "
                "long history are harder to fake. A profile dominated "
                "by single-review accounts is the classic review-farm "
                "fingerprint."
            ),
        },
        rules=rules,
        evidence_weight=EvidenceWeight.PROBABLE,
        data_sources=["business_data.google.reviews"],
    )
