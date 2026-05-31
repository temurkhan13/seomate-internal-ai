"""Search-intent classification — rule-based pattern matching.

Two consumers today:
- P0-01 (per-keyword intent classification) and P0-06 (buyer journey
  stage) call ``classify_intent`` directly.
- The orchestrator's SERP-overlap competitor discovery filters seed
  keywords to commercial / transactional intent only, so the SERPs
  it queries surface direct service competitors rather than
  informational authority sites.

Lives here (not in p0_strategic) so the orchestrator can import the
classifier without a circular dependency on the pillar module.
"""
from __future__ import annotations

import re

INTENT_PATTERNS_TRANSACTIONAL = (
    re.compile(r"\b(buy|order|purchase|hire|book|reserve|rent|subscribe)\b", re.I),
    re.compile(r"\b(price|pricing|cost|fee|fees|cheap|discount|deal|sale|coupon|quote)\b", re.I),
    re.compile(r"\b(near\s+me|near\s+by|in\s+[a-z]{4,}\s+area)\b", re.I),
    re.compile(r"\b(download|signup|sign\s*up|register)\b", re.I),
)

INTENT_PATTERNS_COMMERCIAL = (
    re.compile(r"\b(best|top|review|reviews|comparison|compare|alternative|alternatives)\b", re.I),
    re.compile(r"\bvs\.?\b", re.I),
    re.compile(r"\b(pros\s+and\s+cons|advantages|disadvantages)\b", re.I),
    re.compile(r"\b(which|recommended|recommendation)\b", re.I),
)

# "Service-commercial" — phrases that indicate a buyer evaluating service
# providers (agencies, consultancies, dev shops) without a head verb like
# "best" or "review". These are commercial-intent on agency SERPs even
# though they don't match the broader INTENT_PATTERNS_COMMERCIAL list.
INTENT_PATTERNS_SERVICE_COMMERCIAL = (
    re.compile(r"\b(agency|agencies|consultancy|consultancies|firm|firms|studio|studios|company|companies)\b", re.I),
    re.compile(r"\b(services?|solutions?)\s+(?:provider|company|firm|agency)\b", re.I),
    re.compile(r"\bdevelopment\s+(?:company|companies|agency|agencies|services?)\b", re.I),
    re.compile(r"\b(outsourcing|offshoring|contractors?|freelancers?)\b", re.I),
)

INTENT_PATTERNS_NAVIGATIONAL = (
    re.compile(r"\b(login|sign\s*in|log\s*in|dashboard|account|portal)\b", re.I),
    re.compile(r"\b(contact|support|help\s+center|customer\s+service)\b", re.I),
)

INTENT_PATTERNS_INFORMATIONAL = (
    re.compile(r"\bhow\s+(?:to|do|does|can|should)\b", re.I),
    re.compile(r"\bwhat\s+(?:is|are|does)\b", re.I),
    re.compile(r"\bwhy\s+(?:is|does|do|should)\b", re.I),
    re.compile(r"\bwhen\s+(?:to|should|did)\b", re.I),
    re.compile(r"\b(guide|tutorial|definition|examples?|meaning|explained?)\b", re.I),
)


def classify_intent(keyword: str, brand_variants: tuple[str, ...] = ()) -> dict:
    """Rule-based intent classification for a single keyword.

    Returns ``{"intent": one_of_4, "confidence": 0..1,
    "matched_patterns": [...], "all_matches": {...}, "method": str}``.
    """
    kw_lower = keyword.lower().strip()
    matched: dict[str, list[str]] = {
        "transactional": [],
        "commercial": [],
        "navigational": [],
        "informational": [],
    }

    for variant in brand_variants:
        if variant and variant.lower() in kw_lower:
            matched["navigational"].append(f"brand:{variant}")
            break

    for pat in INTENT_PATTERNS_TRANSACTIONAL:
        m = pat.search(keyword)
        if m:
            matched["transactional"].append(m.group(0))
    for pat in INTENT_PATTERNS_COMMERCIAL:
        m = pat.search(keyword)
        if m:
            matched["commercial"].append(m.group(0))
    for pat in INTENT_PATTERNS_SERVICE_COMMERCIAL:
        m = pat.search(keyword)
        if m:
            matched["commercial"].append(m.group(0))
    for pat in INTENT_PATTERNS_NAVIGATIONAL:
        m = pat.search(keyword)
        if m:
            matched["navigational"].append(m.group(0))
    for pat in INTENT_PATTERNS_INFORMATIONAL:
        m = pat.search(keyword)
        if m:
            matched["informational"].append(m.group(0))

    counts = {k: len(v) for k, v in matched.items()}
    total_matches = sum(counts.values())

    if total_matches == 0:
        return {
            "intent": "informational",
            "confidence": 0.3,
            "matched_patterns": [],
            "all_matches": matched,
            "method": "default_fallback",
        }

    priority_order = ("transactional", "commercial", "navigational", "informational")
    best = max(priority_order, key=lambda k: (counts[k], -priority_order.index(k)))
    confidence = min(1.0, 0.5 + 0.2 * counts[best])
    return {
        "intent": best,
        "confidence": round(confidence, 2),
        "matched_patterns": matched[best],
        "all_matches": matched,
        "method": "rule_based",
    }


def is_commercial_intent(keyword: str, brand_variants: tuple[str, ...] = ()) -> bool:
    """Convenience: True iff classify_intent labels the keyword as
    transactional or commercial. Used to filter SERP-discovery seeds so
    they surface direct service competitors rather than Wikipedia-tier
    authority sites that dominate informational SERPs.
    """
    label = classify_intent(keyword, brand_variants)["intent"]
    return label in ("transactional", "commercial")
