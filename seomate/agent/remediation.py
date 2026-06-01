"""Remediation specs: how to FIX each variable, the execution-side counterpart
to the diagnostic taxonomy.

The o1 taxonomy says what a variable measures and how to judge pass/fail. It
deliberately carries no "how to fix" prose. This module is that missing half:
per variable, a structured spec the execution side (a fixing session, or a
human) consumes to turn a failed/partial capture into an actionable, verifiable
work order.

Kept separate from the taxonomy (which is parsed from markdown with
``extra=forbid``) so the diagnostic spec stays clean and remediation can evolve
independently. ``seomate plan-fixes`` joins captures with these specs.

Authoring status: this is a STARTING set covering the cleanly-automatable
variables surfaced by the pixelettetech.com audit plus the common human/budget
cases. Variables without a spec fall back to a generic spec derived from their
``fix_class`` so the planner never silently drops a finding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FixClass(str, Enum):
    """Who/what can action the fix , the single most important routing field."""

    SESSION = "session"       # a Claude session can do it alone (repo/CMS/config access)
    HUMAN = "human"           # needs a person: editorial, ops, design judgment
    BUDGET = "budget"         # needs spend: a subscription, ads, paid placement
    OWNER = "owner"           # needs an account owner's access (e.g. GBP owner)
    OFFSITE = "offsite"       # off the site: PR, outreach, third-party platforms


class FixType(str, Enum):
    SCHEMA = "schema"             # JSON-LD / structured data
    TEMPLATE = "template"         # change a page template / theme
    CONTENT = "content"           # write / rewrite copy
    INTERNAL_LINKS = "internal_links"
    CONFIG = "config"             # sitemap, robots, headers, build config
    MEDIA = "media"               # images, video
    METADATA = "metadata"         # titles, meta descriptions
    OFFSITE = "offsite"           # backlinks, citations, reviews, PR


@dataclass
class RemediationSpec:
    """How to fix one variable."""

    variable_id: str
    fix_class: FixClass
    fix_type: FixType
    target: str                    # where the change is made
    concrete_change: str           # what to do, specifically
    required_inputs: list[str]     # access/assets the fix needs
    verify: str                    # the re-check that proves it worked
    automatable: bool              # can a session do it end-to-end unattended
    risk: str = "low"              # low | medium | high (blast radius / reversibility)
    depends_on: list[str] = field(default_factory=list)
    effort: str = "one-shot"       # one-shot | ongoing | campaign
    notes: str = ""


# ── authored specs (starting set) ─────────────────────────────────────────────
_SPECS: dict[str, RemediationSpec] = {}


def _add(spec: RemediationSpec) -> None:
    _SPECS[spec.variable_id] = spec


# --- cleanly session-automatable (schema / config / links / metadata) ---
_add(RemediationSpec(
    "P1-21", FixClass.SESSION, FixType.SCHEMA,
    target="page templates (blog + service), <head> JSON-LD block",
    concrete_change="Add appropriate schema.org JSON-LD per page type: Article on blog posts, Service/Organization on service pages, WebPage as the baseline.",
    required_inputs=["site repo or CMS template access"],
    verify="re-audit P1-21: every indexable page has >=1 JSON-LD type",
    automatable=True, risk="low", effort="one-shot",
    notes="Highest schema-coverage win; pairs with P1-42, P6-09, P6-19.",
))
_add(RemediationSpec(
    "P1-42", FixClass.SESSION, FixType.SCHEMA,
    target="blog post template",
    concrete_change="Add Article + author Person schema (name, optional sameAs) and a visible byline to blog posts.",
    required_inputs=["blog template access", "author name(s)"],
    verify="re-audit P1-42: blog pages carry Person schema / visible byline",
    automatable=True, risk="low", depends_on=["P1-21"],
))
_add(RemediationSpec(
    "P6-09", FixClass.SESSION, FixType.SCHEMA,
    target="pages with Q&A content + their template",
    concrete_change="Mark up existing question-answer content as FAQPage JSON-LD; add a short FAQ block to key service pages where natural.",
    required_inputs=["template access", "(optional) a few Q&A pairs per page"],
    verify="re-audit P6-09: FAQPage schema present where Q&A exists",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P6-19", FixClass.SESSION, FixType.SCHEMA,
    target="global template <head>",
    concrete_change="Emit Organization (or LocalBusiness) schema site-wide with name, logo, url, sameAs, contactPoint.",
    required_inputs=["global template access", "brand NAP + social URLs"],
    verify="re-audit P6-19: Organization schema on all pages",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P2-42", FixClass.SESSION, FixType.CONFIG,
    target="sitemap generator / sitemap.xml",
    concrete_change="Differentiate <priority>: homepage 1.0, core service pages 0.8, blog 0.5-0.6, utility 0.3; set <changefreq> sensibly.",
    required_inputs=["sitemap build config access"],
    verify="re-audit P2-42: sitemap shows >1 distinct priority value",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P2-28", FixClass.SESSION, FixType.INTERNAL_LINKS,
    target="core pages (home, services, relevant hubs) + blog index",
    concrete_change="Add contextual internal links from core/hub pages to the orphaned blog posts; add a related-posts/hub module so no post has 0 inbound links.",
    required_inputs=["template + content edit access", "the orphan list from the audit (value.sample)"],
    verify="re-audit P2-28: 0 orphan pages (every page >=1 inbound internal link)",
    automatable=True, risk="medium", depends_on=[],
    notes="Audit found 37/58 orphaned. Highest-impact on-site structural fix.",
))
_add(RemediationSpec(
    "P1-24", FixClass.SESSION, FixType.INTERNAL_LINKS,
    target="core pages",
    concrete_change="Route internal links from high-authority core pages (not just blog-to-blog) so inbound links carry weight.",
    required_inputs=["template/content access"],
    verify="re-audit P1-24: pages receive links from core pages",
    automatable=True, risk="medium", depends_on=["P2-28"],
))
_add(RemediationSpec(
    "P2-31", FixClass.SESSION, FixType.MEDIA,
    target="image assets + <img>/<picture> markup",
    concrete_change="Convert/serve images as WebP/AVIF (with fallback); target >=50% modern-format coverage.",
    required_inputs=["asset pipeline or CMS media access"],
    verify="re-audit P2-31: >=50% images in modern formats",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P6-18", FixClass.SESSION, FixType.CONFIG,
    target="site root",
    concrete_change="Publish /llms.txt describing the site for LLM crawlers (key pages, what the brand does).",
    required_inputs=["root file write access"],
    verify="re-audit P6-18: /llms.txt returns 2xx",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P2-36", FixClass.SESSION, FixType.CONFIG,
    target="robots.txt + publishing pipeline",
    concrete_change="Add IndexNow: generate a key, reference it, ping IndexNow on publish/update.",
    required_inputs=["robots/root access", "publish hook access"],
    verify="re-audit P2-36: IndexNow reference present",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-01", FixClass.SESSION, FixType.METADATA,
    target="per-page <title>",
    concrete_change="Make every indexable page's title unique (dedupe the collisions the audit lists).",
    required_inputs=["CMS/template title-field access", "the duplicate set from the audit"],
    verify="re-audit P1-01: no two indexable pages share a title",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-02", FixClass.SESSION, FixType.METADATA,
    target="per-page <title>",
    concrete_change="Bring over-length titles into ~50-60 chars without dropping the primary keyword.",
    required_inputs=["title-field access"],
    verify="re-audit P1-02: titles within display limits",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-06", FixClass.SESSION, FixType.METADATA,
    target="per-page meta description",
    concrete_change="Write a unique, non-empty meta description for each page missing/duplicating one.",
    required_inputs=["meta-field access"],
    verify="re-audit P1-06: every indexable page has a unique meta description",
    automatable=True, risk="low",
))

# --- needs a human (editorial / judgment) ---
_add(RemediationSpec(
    "P4-11", FixClass.HUMAN, FixType.CONTENT,
    target="content / editorial",
    concrete_change="Produce original research or proprietary data (a survey, benchmark, internal dataset) and publish it.",
    required_inputs=["subject-matter author", "data to analyse"],
    verify="re-audit P4-11: original research present",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P6-05", FixClass.HUMAN, FixType.CONTENT,
    target="content",
    concrete_change="Add named-expert quotes to article-like pages (interview internal experts or cite attributable ones).",
    required_inputs=["access to named experts / quotes"],
    verify="re-audit P6-05: >=30% of article pages carry a named-expert quote",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P6-02", FixClass.HUMAN, FixType.CONTENT,
    target="commercial page copy",
    concrete_change="Replace marketing puffery in quotable positions with specific, verifiable claims.",
    required_inputs=["copywriter"],
    verify="re-audit P6-02: puffery below threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-03", FixClass.HUMAN, FixType.CONTENT,
    target="content",
    concrete_change="Add citations to authoritative sources to lift citation density to >=1 per 500 words on substantive pages.",
    required_inputs=["editorial time"],
    verify="re-audit P6-03: citation density meets threshold",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P6-25", FixClass.HUMAN, FixType.CONTENT,
    target="content + GEO strategy",
    concrete_change="Win AI-Overview citations: build genuinely citation-worthy, well-structured answer content for the category queries where AIO shows but the brand is absent; pursue authority signals (mentions, entity strength).",
    required_inputs=["content strategy", "subject-matter authoring", "time"],
    verify="re-audit P6-25: brand cited in AI Overview for >=1 target query",
    automatable=False, risk="low", effort="campaign",
    notes="Strategic, not a one-shot fix. The audit's standout GEO gap (0/8 AIO citations).",
))

# --- ops (reviews) ---
_add(RemediationSpec(
    "P5-13", FixClass.HUMAN, FixType.OFFSITE,
    target="Google Business Profile",
    concrete_change="Respond to existing reviews (personalised), and set an ongoing process to respond promptly.",
    required_inputs=["GBP access (Manager is enough to respond)"],
    verify="re-audit P5-13: response rate >=80%",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-11", FixClass.HUMAN, FixType.OFFSITE,
    target="review acquisition process",
    concrete_change="Run a review-request flow (post-project asks) to lift velocity above ~1/month.",
    required_inputs=["customer contact process"],
    verify="re-audit P5-11: review velocity >=1/month",
    automatable=False, risk="low", effort="ongoing",
))

# --- budget ---
_add(RemediationSpec(
    "P3-01", FixClass.BUDGET, FixType.OFFSITE,
    target="off-site link profile",
    concrete_change="P3 backlink variables are diagnosed only when the DataForSEO Backlinks subscription is active; improving them is a link-acquisition campaign (digital PR, guest content, directories).",
    required_inputs=["DataForSEO Backlinks subscription (to measure)", "link-building budget/effort (to improve)"],
    verify="re-audit the P3 set after the subscription is active + links acquired",
    automatable=False, risk="low", effort="campaign",
    notes="Represents the P3-* family; backlinks were deferred this project.",
))


# ── generic fallbacks by pillar (so the planner never drops a finding) ─────────
_PILLAR_FALLBACK_CLASS = {
    "P0": FixClass.HUMAN,    # relevance/keyword strategy
    "P1": FixClass.SESSION,  # mostly on-page
    "P2": FixClass.SESSION,  # mostly technical/config
    "P3": FixClass.BUDGET,   # off-page/backlinks
    "P4": FixClass.HUMAN,    # content/E-E-A-T
    "P5": FixClass.OWNER,    # local/GBP
    "P6": FixClass.HUMAN,    # GEO/content
}


def get_spec(variable_id: str) -> RemediationSpec:
    """Return the authored spec, or a generic pillar-derived fallback.

    The fallback guarantees every failed/partial variable gets a routable spec
    (at least a fix_class + a 'needs manual triage' note), so ``plan-fixes``
    never silently omits a finding.
    """
    if variable_id in _SPECS:
        return _SPECS[variable_id]
    pillar = variable_id[:2]
    return RemediationSpec(
        variable_id=variable_id,
        fix_class=_PILLAR_FALLBACK_CLASS.get(pillar, FixClass.HUMAN),
        fix_type=FixType.CONTENT,
        target="(needs manual triage , no authored remediation spec yet)",
        concrete_change="No specific remediation authored for this variable yet. Triage from the capture evidence + the variable definition.",
        required_inputs=["manual triage"],
        verify=f"re-audit {variable_id} after the fix",
        automatable=False,
        notes="GENERIC FALLBACK , author a real spec for this variable to improve the plan.",
    )


def has_spec(variable_id: str) -> bool:
    return variable_id in _SPECS


def authored_count() -> int:
    return len(_SPECS)
