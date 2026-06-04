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
    required_inputs=["template + content edit access", "the orphan list from the capture (value.orphans)"],
    verify="re-audit P2-28: 0 orphan pages (every page >=1 inbound internal link)",
    automatable=True, risk="medium", depends_on=[],
    notes="Highest-impact on-site structural fix when orphans exist; act on the capture's orphan list.",
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


# --- P1 on-page + P2 technical (session: repo / CMS / config edits) ---
_add(RemediationSpec(
    "P1-03", FixClass.SESSION, FixType.METADATA,
    target="per-page <title>",
    concrete_change="Ensure each page's title contains its target keyword (naturally, near the front), per the keyword-to-page map.",
    required_inputs=["target keyword per page (P0-13)", "title-field access"],
    verify="re-audit P1-03: titles include the target keyword",
    automatable=False, risk="low", depends_on=["P0-13"],
))
_add(RemediationSpec(
    "P1-09", FixClass.SESSION, FixType.METADATA,
    target="per-page meta description",
    concrete_change="Include the target keyword in each meta description while keeping it readable and compelling.",
    required_inputs=["target keyword per page", "meta-field access"],
    verify="re-audit P1-09: meta descriptions include the target keyword",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-12", FixClass.SESSION, FixType.TEMPLATE,
    target="page templates",
    concrete_change="Ensure exactly one H1 per page; demote extra H1s to H2 where they are really subheadings.",
    required_inputs=["template access"],
    verify="re-audit P1-12: every page has a single H1",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-13", FixClass.SESSION, FixType.CONTENT,
    target="page H1",
    concrete_change="Include the target keyword in the H1 naturally (not stuffed).",
    required_inputs=["target keyword per page", "content access"],
    verify="re-audit P1-13: H1 includes the target keyword",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-15", FixClass.SESSION, FixType.TEMPLATE,
    target="page headings",
    concrete_change="Fix heading hierarchy: no skipped levels (H1 -> H2 -> H3), headings used for structure not styling.",
    required_inputs=["template/content access"],
    verify="re-audit P1-15: heading hierarchy is well-formed",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-17", FixClass.SESSION, FixType.CONFIG,
    target="URL slugs + redirects",
    concrete_change="Include the target keyword in slugs for new pages; rename existing URLs only where worthwhile, always with a 301 from the old URL.",
    required_inputs=["routing/slug access", "redirect capability"],
    verify="re-audit P1-17: target keyword present in slug",
    automatable=False, risk="medium",
    notes="Renaming live URLs needs 301s to avoid breaking links; prefer applying to new pages.",
))
_add(RemediationSpec(
    "P1-18", FixClass.SESSION, FixType.CONFIG,
    target="URL slugs + redirects",
    concrete_change="Make slugs readable: lowercase, hyphenated, no query-string IDs or stop-word noise. Add 301s when changing existing URLs.",
    required_inputs=["routing/slug access", "redirect capability"],
    verify="re-audit P1-18: slugs are clean and readable",
    automatable=False, risk="medium",
))
_add(RemediationSpec(
    "P1-22", FixClass.SESSION, FixType.SCHEMA,
    target="JSON-LD blocks",
    concrete_change="Make existing schema complete + valid: required properties present, correct schema.org types (no invented types), zero validator errors.",
    required_inputs=["template access"],
    verify="re-audit P1-22: schema validates with required properties",
    automatable=True, risk="low", depends_on=["P1-21"],
))
_add(RemediationSpec(
    "P1-23", FixClass.SESSION, FixType.INTERNAL_LINKS,
    target="under-linked pages",
    concrete_change="Add contextual inbound internal links to pages with too few, from relevant higher-authority pages.",
    required_inputs=["content/template access", "the low-inbound list from the audit"],
    verify="re-audit P1-23: inbound internal link count above threshold",
    automatable=False, risk="low", depends_on=["P2-28"],
))
_add(RemediationSpec(
    "P1-26", FixClass.SESSION, FixType.CONTENT,
    target="outbound links",
    concrete_change="Add a few relevant, authoritative outbound links on thin pages; replace or remove low-quality ones.",
    required_inputs=["content access"],
    verify="re-audit P1-26: outbound links are relevant + authoritative",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-28", FixClass.SESSION, FixType.MEDIA,
    target="<img> alt attributes",
    concrete_change="Add descriptive, accurate alt text to images missing it (decorative images get empty alt). Draft from image context for review.",
    required_inputs=["media/template access"],
    verify="re-audit P1-28: alt-text coverage above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-31", FixClass.SESSION, FixType.METADATA,
    target="<head> Open Graph tags",
    concrete_change="Add Open Graph tags (og:title, og:description, og:image, og:url, og:type) site-wide via the template.",
    required_inputs=["template access", "a default share image"],
    verify="re-audit P1-31: Open Graph tags present",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-37", FixClass.SESSION, FixType.CONTENT,
    target="pages weak on topic entities",
    concrete_change="Ensure each page substantively covers the key entities for its target topic (what a strong page on that topic mentions). Draft additions for review.",
    required_inputs=["content access", "target topic per page"],
    verify="re-audit P1-37: entity match above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-38", FixClass.SESSION, FixType.CONTENT,
    target="duplicative / low-originality pages",
    concrete_change="Rewrite duplicated or boilerplate content to be original and specific to the page. Draft rewrites for review.",
    required_inputs=["content access"],
    verify="re-audit P1-38: originality score above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P1-41", FixClass.SESSION, FixType.TEMPLATE,
    target="article template",
    concrete_change="Expose a visible published + updated date on articles, and keep updated dates honest (bump only when content actually changes).",
    required_inputs=["template access"],
    verify="re-audit P1-41: byline date present",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P1-47", FixClass.SESSION, FixType.SCHEMA,
    target="page templates (breadcrumb nav + JSON-LD)",
    concrete_change="Add breadcrumb navigation UI plus matching BreadcrumbList JSON-LD reflecting each page's place in the hierarchy.",
    required_inputs=["template access", "site hierarchy"],
    verify="re-audit P1-47: breadcrumb nav + BreadcrumbList schema present",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P2-04", FixClass.SESSION, FixType.CONFIG,
    target="non-indexed pages that should rank",
    concrete_change="Remove the indexation blocker (stray noindex, wrong canonical, robots disallow, soft-404) and request indexing. Leave intentionally-excluded pages alone.",
    required_inputs=["template/robots access", "the non-indexed list (GSC)"],
    verify="re-audit P2-04: target pages indexed",
    automatable=False, risk="medium",
))
_add(RemediationSpec(
    "P2-08", FixClass.SESSION, FixType.MEDIA,
    target="LCP element + critical path",
    concrete_change="Improve LCP: preload/optimise the LCP image (modern format, right dimensions), cut render-blocking CSS/JS, prioritise above-fold content. Re-test with PSI.",
    required_inputs=["template/asset access"],
    verify="re-audit P2-08: LCP within the 'good' threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P2-12", FixClass.SESSION, FixType.CONFIG,
    target="render-blocking resources",
    concrete_change="Improve FCP: inline critical CSS, defer non-critical JS, reduce blocking requests. Re-test with PSI.",
    required_inputs=["build/template access"],
    verify="re-audit P2-12: FCP within the 'good' threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P2-14", FixClass.SESSION, FixType.CONFIG,
    target="server response + HTML payload",
    concrete_change="Cut HTML-level load time: reduce server response (caching/CDN), shrink the HTML payload, enable compression.",
    required_inputs=["hosting/build access"],
    verify="re-audit P2-14: HTML load speed improved",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P2-17", FixClass.SESSION, FixType.TEMPLATE,
    target="mobile layout",
    concrete_change="Fix mobile usability: correct viewport meta, adequate tap-target sizes/spacing, legible fonts, no horizontal scroll.",
    required_inputs=["template/CSS access"],
    verify="re-audit P2-17: mobile usability above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P2-23", FixClass.SESSION, FixType.INTERNAL_LINKS,
    target="deep pages + navigation",
    concrete_change="Flatten crawl depth: add links so important pages sit within ~3 clicks of the homepage (nav, hubs, related links).",
    required_inputs=["template/content access"],
    verify="re-audit P2-23: important pages within target crawl depth",
    automatable=False, risk="low", depends_on=["P0-12"],
))
_add(RemediationSpec(
    "P2-27", FixClass.SESSION, FixType.CONTENT,
    target="broken outbound links",
    concrete_change="Fix or remove external links returning 4xx/5xx; update to the current URL or an equivalent source.",
    required_inputs=["content access", "the broken-link list from the audit"],
    verify="re-audit P2-27: no broken external links",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P2-30", FixClass.SESSION, FixType.MEDIA,
    target="heavy pages (images dominate the payload)",
    concrete_change="Reduce page weight: compress + correctly size images, serve modern formats, minify CSS/JS, defer non-critical assets (images usually dominate the payload; see the capture for the per-page weights).",
    required_inputs=["asset/build access"],
    verify="re-audit P2-30: page weight within threshold",
    automatable=False, risk="low", depends_on=["P2-31"],
))
_add(RemediationSpec(
    "P2-32", FixClass.SESSION, FixType.TEMPLATE,
    target="below-fold images/iframes",
    concrete_change="Add loading='lazy' to below-the-fold images and iframes; keep above-fold/LCP images eager.",
    required_inputs=["template access"],
    verify="re-audit P2-32: lazy loading applied below the fold",
    automatable=True, risk="low",
))

# --- P0 strategic foundation (analysis/strategy a session produces) ---
# (P0-01 intent + P0-06 journey moved to Strategy/Competitive, June 2026.)
_add(RemediationSpec(
    "P0-10", FixClass.SESSION, FixType.CONTENT,
    target="pages weak on query-content alignment",
    concrete_change="For each page whose content drifts from its target query, tighten the copy (title, headings, body) to match the query topic so the page aligns semantically.",
    required_inputs=["target query per page", "content edit access"],
    verify="re-audit P0-10: page-to-query similarity above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P0-11", FixClass.SESSION, FixType.CONTENT,
    target="content strategy",
    concrete_change="Group the site's pages + target keywords into explicit topic clusters; surface gaps and overlaps. Output the cluster map.",
    required_inputs=["page inventory", "keyword list"],
    verify="re-audit P0-11: topic clusters defined for the site",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P0-12", FixClass.SESSION, FixType.INTERNAL_LINKS,
    target="site architecture (pillar pages + cluster links)",
    concrete_change="Create a pillar page per core topic and wire hub-and-spoke internal links between each pillar and its cluster posts. Draft any missing pillar pages.",
    required_inputs=["topic clusters (P0-11)", "template + content access"],
    verify="re-audit P0-12: pillar pages exist with hub-and-spoke linking",
    automatable=False, risk="medium", depends_on=["P0-11"],
))
_add(RemediationSpec(
    "P0-13", FixClass.SESSION, FixType.CONTENT,
    target="keyword strategy",
    concrete_change="Map each target keyword to exactly one canonical page; flag cannibalisation (two pages, one keyword) and uncovered keywords (no page).",
    required_inputs=["keyword list", "page inventory"],
    verify="re-audit P0-13: 1:1 keyword-to-page map, no unresolved cannibalisation",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P0-16", FixClass.OFFSITE, FixType.OFFSITE,
    target="brand entity (on-page + off-site)",
    concrete_change="Earn a Knowledge Graph entry: session ships consistent Organization schema + sameAs to official profiles (on-page); off-site, create a Wikidata item and build consistent authoritative mentions. KG recognition follows the off-site signals.",
    required_inputs=["brand NAP + official profile URLs", "off-site entity-building effort"],
    verify="re-audit P0-16: brand resolves as a Knowledge Graph entity",
    automatable=False, risk="low", effort="campaign",
    notes="On-page part is session (schema/sameAs); KG recognition itself is off-site + time.",
))

# --- P4 content operations / E-E-A-T (session drafts; human confirms facts) ---
_add(RemediationSpec(
    "P4-01", FixClass.HUMAN, FixType.CONTENT,
    target="editorial calendar",
    concrete_change="Establish and hold a regular publishing cadence. A session can draft posts to a calendar; a human approves and publishes on schedule.",
    required_inputs=["editorial owner", "topic pipeline"],
    verify="re-audit P4-01: consistent publishing cadence over the trailing window",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P4-03", FixClass.SESSION, FixType.TEMPLATE,
    target="blog/article template + posts",
    concrete_change="Add a visible author byline to every article (template field + assign an author per post).",
    required_inputs=["author name(s) per post", "template access"],
    verify="re-audit P4-03: every article shows a byline",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-04", FixClass.SESSION, FixType.CONTENT,
    target="author bio block + bio/team pages",
    concrete_change="Build an author-bio block (name, role, expertise, link) and add it to articles/team pages. Draft copy from verifiable on-site facts; insert TODO placeholders for credentials the human must confirm. Do NOT invent credentials.",
    required_inputs=["real author credentials (human-confirmed)", "template access"],
    verify="re-audit P4-04: bylined authors link to a bio with credentials",
    automatable=False, risk="low", depends_on=["P4-03"],
    notes="Session drafts structure + verifiable copy; human supplies real credentials.",
))
_add(RemediationSpec(
    "P4-05", FixClass.OFFSITE, FixType.OFFSITE,
    target="author entity (off-site)",
    concrete_change="Make key authors recognisable entities: session adds Person schema + sameAs (on-page); off-site, build the author's presence (Wikidata, authoritative profiles, bylined external work) so KG/LLMs disambiguate them.",
    required_inputs=["author profile URLs", "off-site authoring effort"],
    verify="re-audit P4-05: author resolves as a recognised entity",
    automatable=False, risk="low", effort="campaign", depends_on=["P4-04"],
))
_add(RemediationSpec(
    "P4-06", FixClass.SESSION, FixType.CONTENT,
    target="E-E-A-T signal cluster",
    concrete_change="Lift the aggregate E-E-A-T score by resolving its inputs: byline (P4-03), author bio (P4-04), Person/Org schema (P6-20), citations (P6-03/P4-10). The score rises as those pass.",
    required_inputs=["the component fixes"],
    verify="re-audit P4-06: E-E-A-T aggregate above threshold",
    automatable=False, risk="low", depends_on=["P4-03", "P4-04", "P6-20"],
))
_add(RemediationSpec(
    "P4-07", FixClass.SESSION, FixType.CONTENT,
    target="thin / derivative pages",
    concrete_change="Rewrite thin or derivative pages to add original substance: specific examples, first-hand detail, depth the SERP lacks. Draft the rewrites for review.",
    required_inputs=["content edit access", "subject context (human confirms specifics)"],
    verify="re-audit P4-07: flagged pages meet originality/substance threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-09", FixClass.SESSION, FixType.CONTENT,
    target="surface-level pages",
    concrete_change="Add genuine analysis (the 'so what', trade-offs, implications) beyond surface description on flagged pages. Draft for review.",
    required_inputs=["content access"],
    verify="re-audit P4-09: analysis depth above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-10", FixClass.SESSION, FixType.CONTENT,
    target="claims lacking sources",
    concrete_change="Add outbound citations to authoritative sources for the factual claims on substantive pages. Draft the citations for review.",
    required_inputs=["content access"],
    verify="re-audit P4-10: sourcing/evidence density meets threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-12", FixClass.SESSION, FixType.TEMPLATE,
    target="content taxonomy (categories + tags)",
    concrete_change="Implement a clean category + tag structure, apply it to posts, and expose category/tag archive pages.",
    required_inputs=["CMS taxonomy access"],
    verify="re-audit P4-12: posts carry coherent categories/tags",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P4-13", FixClass.SESSION, FixType.CONTENT,
    target="long article templates/content",
    concrete_change="Restructure flagged long pages into the three-layer pattern: a ~50-word direct answer up top (containing the primary keyword), a 100-150 word 'why it matters', then 1000+ words of detail (1200+ total). Draft the restructure.",
    required_inputs=["content access"],
    verify="re-audit P4-13: flagged pages follow the three-layer structure",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-15", FixClass.SESSION, FixType.CONTENT,
    target="research / data-backed pages",
    concrete_change="Add a methodology disclosure (how the data/claims were produced) wherever research or statistics are presented. Draft it from the page's own content.",
    required_inputs=["content access"],
    verify="re-audit P4-15: methodology disclosed where research is presented",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P4-17", FixClass.HUMAN, FixType.CONTENT,
    target="YMYL pages",
    concrete_change="Raise rigour on any money/health/safety pages: qualified-reviewer sign-off, credentials, citations, last-reviewed date. Session adds the structural signals; a qualified human must review the substance.",
    required_inputs=["qualified reviewer"],
    verify="re-audit P4-17: YMYL pages carry elevated E-E-A-T signals + review",
    automatable=False, risk="medium", effort="ongoing",
))
_add(RemediationSpec(
    "P4-21", FixClass.SESSION, FixType.CONTENT,
    target="pages flagged mass-produced/low-effort",
    concrete_change="Rewrite or consolidate templated/low-effort pages to add real value, or remove them. Draft the rewrite/prune list for review.",
    required_inputs=["content access"],
    verify="re-audit P4-21: flagged pages no longer read as mass-produced",
    automatable=False, risk="medium",
))
_add(RemediationSpec(
    "P4-22", FixClass.SESSION, FixType.CONTENT,
    target="site-wide content quality",
    concrete_change="Lift site-wide quality: identify the thin/duplicate/low-value pages dragging the average and improve or prune them. Draft the action list.",
    required_inputs=["content access", "analytics (to spot low-value pages)"],
    verify="re-audit P4-22: site-wide quality above threshold",
    automatable=False, risk="medium", effort="ongoing",
))
_add(RemediationSpec(
    "P4-23", FixClass.SESSION, FixType.CONTENT,
    target="page headlines/titles vs body",
    concrete_change="Rewrite clickbait or exaggerated headlines so they accurately reflect the page content. Draft for review.",
    required_inputs=["content access"],
    verify="re-audit P4-23: headlines match content (no clickbait)",
    automatable=False, risk="low",
))

# --- P5 local SEO (mostly GBP-owner; one on-page schema fix) ---
_add(RemediationSpec(
    "P5-26", FixClass.SESSION, FixType.SCHEMA,
    target="global template <head> / contact page",
    concrete_change="Add LocalBusiness JSON-LD (name, address, geo, hours, phone, url) site-wide or on the contact/location page.",
    required_inputs=["template access", "verified NAP + hours"],
    verify="re-audit P5-26: valid LocalBusiness schema present",
    automatable=True, risk="low",
))
_add(RemediationSpec(
    "P5-01", FixClass.OWNER, FixType.OFFSITE,
    target="Google Business Profile",
    concrete_change="Proximity is a function of a verified GBP at a real address in the target area; it is not tunable by content. Ensure a correctly-located verified GBP exists.",
    required_inputs=["GBP owner access", "real local address"],
    verify="re-audit P5-01: verified GBP in the target area",
    automatable=False, risk="low",
    notes="Inherent ranking factor; only addressable via a real verified local presence.",
))
_add(RemediationSpec(
    "P5-06", FixClass.OFFSITE, FixType.OFFSITE,
    target="local citation sources (directories)",
    concrete_change="Build consistent NAP citations across the major local directories. Session can draft the listing copy + the submission list; submitting needs directory accounts.",
    required_inputs=["consistent NAP", "directory accounts"],
    verify="re-audit P5-06: citation count + consistency improved",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P5-12", FixClass.HUMAN, FixType.OFFSITE,
    target="review acquisition",
    concrete_change="Run a review-request flow so recent reviews keep arriving (recency decays). Session can draft the request templates; sending needs the customer process.",
    required_inputs=["customer contact process"],
    verify="re-audit P5-12: recent reviews present",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-15", FixClass.OWNER, FixType.OFFSITE,
    target="Google Business Profile",
    concrete_change="Respond to reviews promptly and set a standing process. Needs GBP access to post responses.",
    required_inputs=["GBP access (Manager+)"],
    verify="re-audit P5-15: review response speed improved",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-16", FixClass.HUMAN, FixType.OFFSITE,
    target="review-request prompts",
    concrete_change="Encourage reviewers to mention specific services/locations via the review-request wording. Review text itself can't be authored, only nudged.",
    required_inputs=["review-request process"],
    verify="re-audit P5-16: service keywords appear in review text",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-18", FixClass.HUMAN, FixType.OFFSITE,
    target="reviewer mix",
    concrete_change="Solicit reviews from real customers (including Local Guides) to lift reviewer credibility. Not directly settable.",
    required_inputs=["customer base"],
    verify="re-audit P5-18: reviewer credibility improved",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-21", FixClass.OWNER, FixType.MEDIA,
    target="Google Business Profile",
    concrete_change="Upload fresh, geotagged photos to the GBP and keep adding them. Needs GBP access.",
    required_inputs=["GBP access", "real photos"],
    verify="re-audit P5-21: GBP photo count + freshness improved",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-23", FixClass.OWNER, FixType.OFFSITE,
    target="Google Business Profile Q&A",
    concrete_change="Seed and answer GBP Q&A with the real common questions. Needs GBP access.",
    required_inputs=["GBP access"],
    verify="re-audit P5-23: GBP Q&A activity present",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P5-24", FixClass.OWNER, FixType.OFFSITE,
    target="Google Business Profile attributes",
    concrete_change="Set the applicable GBP attributes (accessibility, ownership, amenities, etc.). Needs GBP access.",
    required_inputs=["GBP access", "which attributes are true"],
    verify="re-audit P5-24: GBP attributes populated",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P5-25", FixClass.OWNER, FixType.OFFSITE,
    target="Google Business Profile",
    concrete_change="Complete the service area and full opening hours (incl. special hours) on the GBP. Needs GBP access.",
    required_inputs=["GBP access", "real hours + service area"],
    verify="re-audit P5-25: service area + hours complete",
    automatable=False, risk="low",
))

# --- P6 GEO / AI search ---
_add(RemediationSpec(
    "P6-01", FixClass.SESSION, FixType.TEMPLATE,
    target="page templates + content",
    concrete_change="Fix heading hierarchy and use semantic HTML (one H1, ordered H2/H3, lists, tables) so LLMs can parse the structure cleanly.",
    required_inputs=["template/content access"],
    verify="re-audit P6-01: clean semantic structure / heading hierarchy",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-04", FixClass.SESSION, FixType.CONTENT,
    target="vague commercial copy",
    concrete_change="Replace vague phrasing with specific figures (counts, %, timeframes) where the brand has real numbers. Draft using verifiable facts only; flag any figure needing confirmation. Do NOT fabricate.",
    required_inputs=["real figures (human-confirmed where unknown)"],
    verify="re-audit P6-04: numerical specificity above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-06", FixClass.SESSION, FixType.CONTENT,
    target="article/service copy",
    concrete_change="Add grounded first-person experience framing ('we built', 'in our work') where genuine, signalling first-hand experience. Draft for review.",
    required_inputs=["content access"],
    verify="re-audit P6-06: first-person authority markers present + grounded",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-07", FixClass.HUMAN, FixType.CONTENT,
    target="content / editorial",
    concrete_change="Publish original research or primary data (survey, benchmark, internal dataset). Needs real data; a session can structure + write it up once the data exists.",
    required_inputs=["subject-matter author", "real data"],
    verify="re-audit P6-07: original research / primary data present",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P6-10", FixClass.SESSION, FixType.CONTENT,
    target="service/topic pages",
    concrete_change="Add a clear one-line definition ('X is Y') near the top of each key entity/concept page, plus a short glossary where useful. Draft for review.",
    required_inputs=["content access"],
    verify="re-audit P6-10: definitional clarity present on key pages",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-11", FixClass.OFFSITE, FixType.OFFSITE,
    target="Wikidata / Wikipedia",
    concrete_change="Create a Wikidata item for the brand (achievable now); a Wikipedia article requires meeting notability (off-site, not guaranteed). Session can prep the structured facts.",
    required_inputs=["notable sources/coverage (for Wikipedia)"],
    verify="re-audit P6-11: brand present in Wikidata (and Wikipedia if notable)",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P6-12", FixClass.OFFSITE, FixType.OFFSITE,
    target="off-site brand presence",
    concrete_change="Increase brand mentions across the open web (the corpus LLMs train on): guest content, PR, community presence, consistent naming. Compounds over time.",
    required_inputs=["content distribution + PR effort"],
    verify="re-audit P6-12: brand-mention footprint grown",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P6-16", FixClass.OFFSITE, FixType.OFFSITE,
    target="press / tier-1 coverage",
    concrete_change="Earn news + tier-1 publication coverage via digital PR (newsworthy angles, data stories, expert sourcing). Session can draft pitches + press assets.",
    required_inputs=["PR effort / outreach"],
    verify="re-audit P6-16: tier-1 coverage present",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P6-20", FixClass.SESSION, FixType.SCHEMA,
    target="article + global templates",
    concrete_change="Add Person schema for authors and Organization schema for the brand, linked via sameAs, so the author/org are machine-readable.",
    required_inputs=["template access", "author + brand profile URLs"],
    verify="re-audit P6-20: Person + Organization schema present",
    automatable=True, risk="low", depends_on=["P4-03"],
))
_add(RemediationSpec(
    "P6-22", FixClass.SESSION, FixType.CONTENT,
    target="shallow topic pages",
    concrete_change="Expand flagged pages to cover the topic exhaustively (sub-questions, related concepts, edge cases the SERP/PAA shows). Draft the additions for review.",
    required_inputs=["content access", "(optional) PAA/related-question data"],
    verify="re-audit P6-22: topic depth above threshold",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-23", FixClass.SESSION, FixType.CONTENT,
    target="time-sensitive / year-stamped pages",
    concrete_change="Refresh stale content: update year stamps (e.g. 2024 -> current), refresh figures/claims, and surface a visible last-updated date. Draft for review.",
    required_inputs=["content access"],
    verify="re-audit P6-23: time-sensitive pages current + dated",
    automatable=False, risk="low",
))
_add(RemediationSpec(
    "P6-27", FixClass.OFFSITE, FixType.CONTENT,
    target="GEO outcome metric",
    concrete_change="Being cited by ChatGPT/Claude/Gemini is an outcome of citation-worthy content (P6-10/P6-22) + entity authority (P6-11/P6-16/P0-16). Drive those; this follows.",
    required_inputs=["the upstream content + authority work"],
    verify="re-audit P6-27: brand cited by >=1 major LLM for a target query",
    automatable=False, risk="low", effort="campaign", depends_on=["P6-10", "P6-22", "P6-11"],
))
_add(RemediationSpec(
    "P6-29", FixClass.OFFSITE, FixType.OFFSITE,
    target="Knowledge Graph entity",
    concrete_change="Complete the brand's KG entity: session ships Organization schema + full sameAs (on-page); off-site, complete the Wikidata item and keep attributes consistent across the web.",
    required_inputs=["brand profile URLs", "Wikidata edit"],
    verify="re-audit P6-29: KG entity attributes complete",
    automatable=False, risk="low", effort="campaign", depends_on=["P0-16"],
))
_add(RemediationSpec(
    "P6-32", FixClass.SESSION, FixType.CONTENT,
    target="page content + any UGC/templates",
    concrete_change="Remove prompt-injection vectors: hidden/invisible text (display:none, white-on-white, off-screen), fake [SYSTEM]/[ASSISTANT] syntax, 'ignore previous instructions' patterns, instruction-like HTML comments, keyword-stuffed alt/aria, and any HTML-vs-rendered bait-and-switch.",
    required_inputs=["content/template access"],
    verify="re-audit P6-32: no prompt-injection/adversarial content",
    automatable=False, risk="low",
))

# --- P3 off-page authority (measure needs the Backlinks sub; improve needs a campaign) ---
_add(RemediationSpec(
    "P3-09", FixClass.BUDGET, FixType.OFFSITE,
    target="off-site link profile",
    concrete_change="Site-wide authority rises with quality backlinks. Measuring it needs the DataForSEO Backlinks subscription; improving it is a link-acquisition campaign (digital PR, guest content, partnerships).",
    required_inputs=["DataForSEO Backlinks subscription (to measure)", "link-building effort (to improve)"],
    verify="re-audit P3-09 after the subscription is active + links acquired",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-28", FixClass.OFFSITE, FixType.OFFSITE,
    target="Wikipedia source links",
    concrete_change="Earn citations from Wikipedia articles (be the authoritative source a relevant article cites). Requires genuinely citation-worthy, notable content; not directly placeable.",
    required_inputs=["citation-worthy content", "relevant Wikipedia articles"],
    verify="re-audit P3-28: linked as a Wikipedia source",
    automatable=False, risk="low", effort="campaign",
))
# P3 backlink quality variables (measurable now the Backlinks sub is live;
# improving them is off-site link-acquisition work, not an on-site edit).
_add(RemediationSpec(
    "P3-02", FixClass.OFFSITE, FixType.OFFSITE,
    target="off-site link profile (referring-domain authority mix)",
    concrete_change="Lift the share of high-authority referring domains: run digital PR + guest content aimed at DR-50+ industry sites so at least 5 referring domains sit at rank>=600 and the 'very low' bucket shrinks. The authority of the linker, not raw count, is the lever.",
    required_inputs=["link-building effort (digital PR, guest content)", "list of target authority sites in the niche"],
    verify="re-audit P3-02: >=5 referring domains at rank>=600, very-low bucket <70%",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-03", FixClass.OFFSITE, FixType.OFFSITE,
    target="off-site link-acquisition pace",
    concrete_change="Acquire links at a steady, organic pace rather than in bulk: a sudden spike of newly-discovered referring domains reads as paid-link activity. Profile age accrues over time; the actionable part is avoiding acquisition spikes and keeping earned links live.",
    required_inputs=["sustained link-building cadence"],
    verify="re-audit P3-03: median referring-domain age >=365d, <30% first-seen in last 90d",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P3-06", FixClass.OFFSITE, FixType.OFFSITE,
    target=".edu / .gov / .ac / .mil referring domains",
    concrete_change="Earn at least one gated-TLD link via targeted outreach: scholarship listings and resource pages on .edu sites, local-government supplier/partner directories, academic or industry-body partner pages. These TLDs are gated and rarely spam.",
    required_inputs=["outreach effort", "a linkable asset (scholarship, resource, data)"],
    verify="re-audit P3-06: >=1 backlink from an authoritative TLD",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-07", FixClass.OFFSITE, FixType.OFFSITE,
    target="authority of individual linking pages",
    concrete_change="Earn links from strong individual pages, not just strong domains: industry roundups, high-traffic articles, and resource pages that themselves carry authority. Pitch contributions/citations to pages at rank>=600.",
    required_inputs=["digital PR / outreach effort"],
    verify="re-audit P3-07: >=5 anchors from rank>=600 pages, <=60% from rank<150",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-10", FixClass.OFFSITE, FixType.OFFSITE,
    target="link equity beyond the homepage",
    concrete_change="Spread page-level authority off the homepage: earn deep backlinks to service/blog pages (most links default to the homepage), and internally link from high-equity pages to deeper ones so equity flows inward. The internal-linking half is session-doable; the deep-link half needs outreach.",
    required_inputs=["deep-link outreach", "internal-link edit access (for the session-doable half)"],
    verify="re-audit P3-10: homepage rank>=200 and >=25% of audited pages at rank>=100",
    automatable=False, risk="low", effort="campaign",
    depends_on=["P1-23", "P1-24"],
))
_add(RemediationSpec(
    "P3-12", FixClass.OFFSITE, FixType.OFFSITE,
    target="inbound anchor-text mix",
    concrete_change="Shape the anchor profile through your own link-building: favour branded, naked-URL, and natural-phrase anchors so branded share is >=25%; never request exact-match commercial anchors (over-optimisation risk). You can only influence anchors on links you earn or request.",
    required_inputs=["control of outreach/guest-post anchor choices"],
    verify="re-audit P3-12: branded anchor share >=25% of sampled backlinks",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P3-15", FixClass.OFFSITE, FixType.OFFSITE,
    target="spam-phrase / money-keyword anchors",
    concrete_change="Keep money-keyword and spam-phrase anchors out of your own link-building, and do not buy links. Spam-phrase anchors that arrive from scraper/PBN spam are auto-discounted by Google; monitor them via P3-29 rather than chasing each one.",
    required_inputs=["anchor discipline in outreach"],
    verify="re-audit P3-15: zero spam-phrase anchors among earned links; no single anchor >5%",
    automatable=False, risk="low", effort="ongoing",
    depends_on=["P3-29"],
))
_add(RemediationSpec(
    "P3-19", FixClass.OFFSITE, FixType.OFFSITE,
    target="in-content (editorial) link placement",
    concrete_change="Prioritise editorial in-content placements over boilerplate: guest articles and 'mentioned in' citations inside the body of a page pass more weight than footer/sidebar/directory links. Aim for >=60% of links inside article/section/main.",
    required_inputs=["editorial outreach / guest content effort"],
    verify="re-audit P3-19: >=60% of backlinks in main-content semantic elements",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-25", FixClass.OFFSITE, FixType.OFFSITE,
    target="referring-domain retention (link loss)",
    concrete_change="Stem link loss: monitor lost referring domains, reclaim them via outreach (broken-link rebuilds, ask for a re-link after a removal), and keep linkable assets live at stable URLs (301 anything you move). A shrinking profile signals decay.",
    required_inputs=["lost-link monitoring", "outreach for reclamation"],
    verify="re-audit P3-25: window-wide net referring-domain change >= -10%",
    automatable=False, risk="low", effort="ongoing",
))
_add(RemediationSpec(
    "P3-29", FixClass.OFFSITE, FixType.OFFSITE,
    target="toxic backlink share (monitor, usually no action)",
    concrete_change="Most low-quality spam (e.g. the seo-cartel-*.xyz scraper cluster) is auto-discounted by Google, so for a clean profile no action is needed. Do NOT disavow without a GSC manual action (see P3-30). Monitor toxic_pct over time; act only on a real manual action or clear negative-SEO harm.",
    required_inputs=["periodic monitoring", "(only if a manual action) a disavow file"],
    verify="re-audit P3-29: <=10% of sampled referring domains at spam_score>=60",
    automatable=False, risk="low", effort="ongoing",
    depends_on=["P3-30"],
))
_add(RemediationSpec(
    "P3-32", FixClass.OFFSITE, FixType.OFFSITE,
    target="linked brand mentions",
    concrete_change="Grow linked brand mentions through digital PR and brand-building, and reclaim unlinked mentions (find brand mentions with no link, ask the author to link). A healthy share of branded, linked mentions signals genuine brand authority.",
    required_inputs=["digital PR effort", "unlinked-mention monitoring"],
    verify="re-audit P3-32: >=20% of sampled backlinks use branded anchors",
    automatable=False, risk="low", effort="campaign",
    depends_on=["P6-12"],
))
_add(RemediationSpec(
    "P3-35", FixClass.OFFSITE, FixType.OFFSITE,
    target="links from recognised authority sites",
    concrete_change="Land links on recognised authority sites (~DR 50+): major industry publications, well-known resource hubs, and trade bodies, via digital PR, data stories, and expert contributions. Quality over quantity.",
    required_inputs=["digital PR effort", "newsworthy assets (data, expert commentary)"],
    verify="re-audit P3-35: >=3 referring domains at rank>=600",
    automatable=False, risk="low", effort="campaign",
    depends_on=["P6-16"],
))
_add(RemediationSpec(
    "P3-36", FixClass.OFFSITE, FixType.OFFSITE,
    target="guest-post-network reliance",
    concrete_change="Reduce dependence on guest-post networks: diversify into editorial mentions, digital PR, and resource/citation links so guest-post-network links stay <=25% of the profile. Over-reliance on guest-post networks is a recognised manipulation pattern.",
    required_inputs=["diversified link-building mix"],
    verify="re-audit P3-36: <=25% of referring domains classified as guest-post networks",
    automatable=False, risk="low", effort="campaign",
))
_add(RemediationSpec(
    "P3-38", FixClass.OFFSITE, FixType.OFFSITE,
    target="press-release-wire / article-directory links",
    concrete_change="Stop using press-release wires and article-directory submissions for links (low-value and pattern-flagged). Pursue genuine earned coverage instead (real news pickups, editorial features), which P6-16 tracks.",
    required_inputs=["shift PR strategy to earned coverage"],
    verify="re-audit P3-38: zero referring domains matching press-release-wire patterns",
    automatable=False, risk="low", effort="ongoing",
    depends_on=["P6-16"],
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
