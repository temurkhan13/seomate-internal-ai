"""Phase 2 executor: turn automatable work orders into real fix artifacts.

This is the action half of the execution loop. For each session-automatable
work order from ``plan_fixes``, an executor *generator* produces the concrete
fix artifact from the audit's gather cache , the actual llms.txt body, the
sitemap priority map, the JSON-LD blocks, the orphan internal-link plan, etc.
, plus the ``verify`` criterion that proves the fix landed.

**Safety model (deliberate).** This module does NOT write to the target
website. SEOMATE is the audit platform; the audited site is a separate property
whose repo/CMS this process does not own, and editing live production unattended
is a gated action. So the executor runs in ``propose`` mode: it emits an
**apply manifest** (artifacts + where each goes + how to verify) that a human or
an access-holding session reviews and applies. ``apply`` mode is reserved for a
caller that supplies a target adapter with write access + per-change approval;
it is intentionally not implemented here.

Generators are deterministic and read only the gather cache , no fabrication:
schema/NAP come from real KG + GBP + crawl data, the orphan plan from the real
link graph, etc.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from seomate.agent.remediation import RemediationSpec, get_spec


@dataclass
class FixArtifact:
    """One concrete, reviewable fix produced for a work order."""

    variable_id: str
    apply_to: str                  # where it goes (file path / template / config)
    artifact_kind: str             # "file" | "snippet" | "plan" | "map"
    content: Any                   # the actual artifact (text or structured)
    verify: str                    # the re-check that proves it worked
    apply_notes: str = ""          # how to apply it
    generated_from: list[str] = field(default_factory=list)  # cache files used


# ── cache access ───────────────────────────────────────────────────────────────
class _Cache:
    def __init__(self, cache_dir: Path):
        self.dir = cache_dir

    def load(self, name: str) -> Any:
        p = self.dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _rel(url: str) -> str:
    return urlparse(url).path or "/"


# ── generators (one per automatable fix) ────────────────────────────────────────
def _gen_llms_txt(cache: _Cache, domain: str) -> FixArtifact | None:
    crawl = cache.load("crawl.json")
    ent = cache.load("entity.json")
    if not crawl:
        return None
    kg = (((ent or {}).get("kg") or {}).get("itemListElement") or [{}])[0].get("result", {}) if ent else {}
    pages = crawl["pages"]
    # description: prefer the homepage meta description (richer than KG's one-word label),
    # fall back to KG description, then a generic.
    home = next((p for p in pages if urlparse(p["url"]).path.strip("/") in ("", "home")), None)
    desc = (
        (home or {}).get("meta_description")
        or kg.get("description")
        or "Technology company."
    ).strip()
    # key pages = non-blog, shallow
    key = [p for p in pages if "/blog/" not in p["url"]][:12]
    lines = [
        f"# {domain}",
        f"> {desc}",
        "",
        "## Key pages",
    ]
    for p in key:
        title = (p.get("title") or _rel(p["url"])).split("|")[0].strip()
        lines.append(f"- [{title}]({p['url']})")
    body = "\n".join(lines) + "\n"
    return FixArtifact(
        variable_id="P6-18", apply_to=f"https://{domain}/llms.txt", artifact_kind="file",
        content=body, verify="GET /llms.txt returns 2xx (re-audit P6-18)",
        apply_notes="Publish this file at the site root.", generated_from=["crawl.json", "entity.json"],
    )


def _gen_sitemap_priority(cache: _Cache, domain: str) -> FixArtifact | None:
    crawl = cache.load("crawl.json")
    if not crawl:
        return None
    def priority(url: str) -> float:
        path = urlparse(url).path.strip("/")
        if path == "":
            return 1.0
        if "/blog/" in url:
            return 0.5
        if path in ("about-us", "contact-us", "privacy-policy", "terms"):
            return 0.3
        return 0.8  # service/core pages
    mapping = [{"loc": p["url"], "priority": priority(p["url"])} for p in crawl["pages"]]
    return FixArtifact(
        variable_id="P2-42", apply_to="sitemap generator / sitemap.xml", artifact_kind="map",
        content={"priority_map": mapping, "rule": "home 1.0 / service 0.8 / blog 0.5 / utility 0.3"},
        verify="sitemap shows >1 distinct <priority> value (re-audit P2-42)",
        apply_notes="Feed this priority map into the sitemap build step.", generated_from=["crawl.json"],
    )


def _gen_org_schema(cache: _Cache, domain: str) -> FixArtifact | None:
    ent = cache.load("entity.json")
    dfs = cache.load("dataforseo.json")
    kg = (((ent or {}).get("kg") or {}).get("itemListElement") or [{}])[0].get("result", {}) if ent else {}
    gbp = None
    try:
        gbp = dfs["my_business_info"]["tasks"][0]["result"][0]["items"][0]
    except Exception:
        gbp = None
    org: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": kg.get("name") or domain,
        "url": f"https://{domain}",
    }
    if gbp:
        if gbp.get("address"):
            org["address"] = {"@type": "PostalAddress", "streetAddress": gbp["address"]}
        if gbp.get("phone"):
            org["telephone"] = gbp["phone"]
    return FixArtifact(
        variable_id="P6-19", apply_to="global template <head>", artifact_kind="snippet",
        content=f'<script type="application/ld+json">{json.dumps(org, indent=2)}</script>',
        verify="Organization schema present site-wide (re-audit P6-19)",
        apply_notes="Inject in the global <head>. Add sameAs (social URLs) + logo when available.",
        generated_from=["entity.json", "dataforseo.json"],
    )


def _gen_article_schema(cache: _Cache, domain: str) -> FixArtifact | None:
    crawl = cache.load("crawl.json")
    if not crawl:
        return None
    blog = [p for p in crawl["pages"] if "/blog/" in p["url"]]
    if not blog:
        return None
    # a parameterised template + the list of posts that need it
    template = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{{ page.h1 }}",
        "author": {"@type": "Person", "name": "{{ author_name }}"},
        "datePublished": "{{ page.published_date }}",
        "publisher": {"@type": "Organization", "name": "{{ brand }}"},
    }
    return FixArtifact(
        variable_id="P1-42", apply_to="blog post template <head>", artifact_kind="snippet",
        content={"jsonld_template": template, "applies_to_count": len(blog),
                 "posts": [_rel(p["url"]) for p in blog]},
        verify="blog pages carry Article + Person schema (re-audit P1-42 + P1-21)",
        apply_notes="Add to the blog template; bind {{ author_name }} and {{ page.published_date }}.",
        generated_from=["crawl.json"],
    )


def _gen_orphan_links(cache: _Cache, domain: str) -> FixArtifact | None:
    crawl = cache.load("crawl.json")
    if not crawl:
        return None
    norm = lambda u: u.rstrip("/")
    pages = crawl["pages"]
    allset = {norm(p["url"]) for p in pages}
    inbound = {norm(p["url"]): 0 for p in pages}
    for p in pages:
        for t in (p.get("internal_links") or []):
            tn = norm(t)
            if tn in inbound and tn != norm(p["url"]):
                inbound[tn] += 1
    orphans = [u for u, n in inbound.items() if n == 0]
    # propose links FROM core/hub pages TO each orphan, grouped by topical slug overlap
    hubs = [p["url"] for p in pages if "/blog/" not in p["url"]][:6]
    blog_index = next((p["url"] for p in pages if p["url"].rstrip("/").endswith("/blog")), None)
    plan = []
    for o in orphans:
        on = norm(o)
        # candidate sources must not be the orphan itself
        otoks = set(urlparse(o).path.strip("/").split("/")[-1].split("-"))
        cand_hubs = [h for h in hubs if norm(h) != on]
        best_hub = max(cand_hubs, key=lambda h: len(otoks & set(urlparse(h).path.strip("/").split("-"))), default=None) if cand_hubs else None
        srcs = [s for s in [blog_index, best_hub] if s and norm(s) != on]
        # de-dupe while preserving order
        seen_s: set[str] = set()
        srcs = [s for s in srcs if not (norm(s) in seen_s or seen_s.add(norm(s)))]
        plan.append({"orphan": _rel(o), "add_links_from": [_rel(s) for s in srcs] or ["(add from a topically-relevant core page)"]})
    return FixArtifact(
        variable_id="P2-28", apply_to="core/hub pages + blog index (contextual links)", artifact_kind="plan",
        content={"orphan_count": len(orphans), "link_plan": plan,
                 "note": "Add a related-posts/hub module so each orphan gets >=1 contextual inbound link from a core page."},
        verify="0 orphan pages (re-audit P2-28); inbound links from core pages (P1-24)",
        apply_notes="Implement as a hub/related-posts module + contextual links, not a footer dump.",
        generated_from=["crawl.json (link graph)"],
    )


_GENERATORS = {
    "P6-18": _gen_llms_txt,
    "P2-42": _gen_sitemap_priority,
    "P6-19": _gen_org_schema,
    "P1-42": _gen_article_schema,
    "P1-21": _gen_article_schema,   # article/org schema covers P1-21 page-type schema too
    "P2-28": _gen_orphan_links,
    "P1-24": _gen_orphan_links,
}


def can_generate(variable_id: str) -> bool:
    return variable_id in _GENERATORS


def execute_work_order(variable_id: str, cache_dir: str | Path, domain: str) -> dict[str, Any]:
    """Produce a fix artifact for one work order (propose mode).

    Returns a dict with the artifact when a generator exists, else a routed
    'manual' result carrying the remediation spec so the caller still knows what
    to do. Never writes to the target site.
    """
    spec: RemediationSpec = get_spec(variable_id)
    gen = _GENERATORS.get(variable_id)
    if gen is None:
        return {
            "variable_id": variable_id, "mode": "propose", "generated": False,
            "reason": "no artifact generator for this variable (manual fix per the remediation spec)",
            "fix_class": spec.fix_class.value, "concrete_change": spec.concrete_change,
            "required_inputs": spec.required_inputs, "verify": spec.verify,
        }
    artifact = gen(_Cache(Path(cache_dir)), domain)
    if artifact is None:
        return {"variable_id": variable_id, "mode": "propose", "generated": False,
                "reason": "generator could not build the artifact from this cache (missing source data)"}
    return {
        "variable_id": variable_id, "mode": "propose", "generated": True,
        "apply_to": artifact.apply_to, "artifact_kind": artifact.artifact_kind,
        "content": artifact.content, "verify": artifact.verify,
        "apply_notes": artifact.apply_notes, "generated_from": artifact.generated_from,
    }


def build_apply_manifest(plan: dict[str, Any], cache_dir: str | Path) -> dict[str, Any]:
    """Run every automatable work order in a plan through its generator.

    Produces an apply manifest: the concrete artifacts a human/access-holding
    session reviews and applies, plus the manual work orders routed onward.
    Writes nothing to the target site.
    """
    domain = plan["site_domain"]
    generated, manual = [], []
    for w in plan["work_orders"]:
        vid = w["variable_id"]
        if w["remediation"]["automatable"] and can_generate(vid):
            res = execute_work_order(vid, cache_dir, domain)
            (generated if res.get("generated") else manual).append(res)
        else:
            manual.append({
                "variable_id": vid, "generated": False,
                "fix_class": w["remediation"]["fix_class"],
                "concrete_change": w["remediation"]["concrete_change"],
                "required_inputs": w["remediation"]["required_inputs"],
                "verify": w["remediation"]["verify"],
            })
    return {
        "site_domain": domain, "audit_id": plan["audit_id"], "mode": "propose",
        "artifacts_generated": len(generated),
        "manual_work_orders": len(manual),
        "generated": generated,
        "manual": manual,
        "note": (
            "propose mode: artifacts are generated from the audit cache for review, "
            "NOT written to the target site. Applying them needs the site's repo/CMS "
            "access + per-change approval. After applying, re-audit each variable to "
            "confirm it flips to passed."
        ),
    }
