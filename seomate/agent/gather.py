"""Deterministic data gathering for an agent-driven audit.

``gather(domain, out_dir)`` collects every reachable data source into
``out_dir`` as JSON cache files plus a ``manifest.json`` that records, per
source, whether it was available and what it produced. A Claude session reads
this cache and applies per-variable judgment; it does not re-implement fetching.

Design rules (these are why the output is trustworthy):
- **Honest availability.** Every source reports ``available: true/false`` with a
  ``reason`` when false. A source that is unconfigured or errors is NOT a
  silent pass - the session marks dependent variables ``unmeasurable``.
- **No fabrication.** Only real API/HTTP responses are written. Nothing is
  invented to fill a gap.
- **Auto-derive the unknowns.** Keyword seeds come from the site's own pages
  (slug/title/H1); market/location defaults from the domain TLD; competitors
  from SERP overlap. The session can override, but a bare ``--domain`` works.
- **Cost-aware.** Paid (DataForSEO) calls are bounded and logged; free sources
  (crawl, PSI, KG, CrUX, Wayback, robots) run unconditionally.

This module intentionally uses only ``httpx`` (already a dependency) and the
existing adapters where present; it does not pull in the heavy orchestrator.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

# ─── market defaults by TLD (location_code = DataForSEO, gl = Google country) ──
_TLD_MARKET = {
    "uk": {"location_code": 2826, "country": "GB", "label": "United Kingdom"},
    "com": {"location_code": 2840, "country": "US", "label": "United States"},
    "us": {"location_code": 2840, "country": "US", "label": "United States"},
    "ca": {"location_code": 2124, "country": "CA", "label": "Canada"},
    "au": {"location_code": 2036, "country": "AU", "label": "Australia"},
    "ie": {"location_code": 2372, "country": "IE", "label": "Ireland"},
    "in": {"location_code": 2356, "country": "IN", "label": "India"},
    "de": {"location_code": 2276, "country": "DE", "label": "Germany"},
}
_DEFAULT_MARKET = {"location_code": 2840, "country": "US", "label": "United States (default)"}

_UA = "Mozilla/5.0 (compatible; SEOMate-agent-audit/1.0)"


@dataclass
class SourceResult:
    """One data source's outcome."""

    name: str
    available: bool
    reason: str | None = None
    cost_gbp: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class GatherResult:
    domain: str
    out_dir: Path
    market: dict[str, Any]
    sources: list[SourceResult]
    total_cost_gbp: float

    @property
    def available_sources(self) -> list[str]:
        return [s.name for s in self.sources if s.available]

    @property
    def unavailable_sources(self) -> dict[str, str]:
        return {s.name: (s.reason or "unavailable") for s in self.sources if not s.available}


def _market_for(domain: str) -> dict[str, Any]:
    host = domain.lower().split("/")[0]
    parts = host.split(".")
    # co.uk -> uk ; example.com -> com
    tld = parts[-1] if parts[-1] != "uk" else "uk"
    if len(parts) >= 2 and parts[-2] == "co" and parts[-1] == "uk":
        tld = "uk"
    return {**_TLD_MARKET.get(tld, _DEFAULT_MARKET), "tld": tld}


def _norm_domain(domain: str) -> str:
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d).rstrip("/")
    d = re.sub(r"^www\.", "", d)
    return d


def _write(out_dir: Path, name: str, data: Any) -> None:
    (out_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── env access (read at call time; never logged) ─────────────────────────────
def _env(name: str) -> str | None:
    import os

    v = os.environ.get(name)
    return v.strip() if v else None


# ════════════════════════════════════════════════════════════════════════════
# Source gatherers. Each returns (SourceResult, payload-or-None).
# ════════════════════════════════════════════════════════════════════════════
async def _gather_crawl(client: httpx.AsyncClient, domain: str, out_dir: Path) -> tuple[SourceResult, list[dict]]:
    """Fetch sitemap + every page's HTML; extract on-page signals + link graph.

    This is the backbone source: titles, meta, headings, canonical, schema,
    og/twitter, images (alt/format/lazy), internal/external links, body text,
    dates, byline. Free. Always runs.
    """
    base = f"https://{domain}"
    pages: list[str] = []
    # 1. sitemap
    sitemap_urls: list[str] = []
    try:
        r = await client.get(f"{base}/sitemap.xml", timeout=25)
        if r.status_code == 200:
            # handle sitemap index + flat sitemap
            locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", r.text)
            child_sitemaps = [u for u in locs if u.endswith(".xml")]
            if child_sitemaps:
                for sm in child_sitemaps[:10]:
                    try:
                        rc = await client.get(sm, timeout=25)
                        sitemap_urls += re.findall(r"<loc>\s*([^<]+?)\s*</loc>", rc.text)
                    except Exception:
                        pass
            else:
                sitemap_urls = locs
    except Exception:
        pass
    pages = [u for u in dict.fromkeys(sitemap_urls) if domain in u][:200] or [base]

    fetched: list[dict] = []
    sem = asyncio.Semaphore(8)

    async def one(url: str) -> dict:
        async with sem:
            try:
                r = await client.get(url, timeout=25, headers={"User-Agent": _UA}, follow_redirects=True)
                return _analyze_html(url, r)
            except Exception as e:  # noqa: BLE001
                return {"url": url, "error": str(e)[:80]}

    fetched = await asyncio.gather(*(one(u) for u in pages))
    _write(out_dir, "crawl.json", {"base": base, "page_count": len(fetched), "pages": fetched})
    ok = [p for p in fetched if not p.get("error")]
    return (
        SourceResult("crawl", True, summary={"pages_fetched": len(ok), "pages_total": len(fetched)}),
        ok,
    )


def _analyze_html(url: str, r: httpx.Response) -> dict:
    h = r.text
    head = dict(r.headers)
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", h, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z#0-9]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    title = (re.search(r"<title[^>]*>([^<]*)</title>", h, re.I) or [None, ""])[1].strip()
    meta_desc = (re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', h, re.I) or [None, ""])[1]
    canonical = (re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', h, re.I) or [None, None])[1]
    h1 = re.findall(r"<h1[^>]*>([\s\S]*?)</h1>", h, re.I)
    h2 = re.findall(r"<h2[^>]*>([\s\S]*?)</h2>", h, re.I)
    jsonld_types = re.findall(r'"@type"\s*:\s*"([^"]+)"', h)
    imgs = re.findall(r"<img[^>]+>", h, re.I)
    img_srcs = [(re.search(r'src=["\']([^"\']+)', t, re.I) or [None, ""])[1] for t in imgs]
    internal = re.findall(rf'href=["\'](https?://(?:www\.)?{re.escape(urlparse(url).netloc.replace("www.", ""))}[^"\'#?]*)', h, re.I)
    external = re.findall(r'href=["\'](https?://[^"\']+)', h, re.I)
    ext_domains = sorted({urlparse(u).netloc.replace("www.", "") for u in external if urlparse(url).netloc.replace("www.", "") not in u})
    return {
        "url": url,
        "http_status": r.status_code,
        "title": _clean(title),
        "title_length": len(_clean(title)),
        "meta_description": _clean(meta_desc),
        "meta_description_length": len(_clean(meta_desc)),
        "canonical": canonical,
        "canonical_is_self": canonical is not None and canonical.rstrip("/") == url.rstrip("/"),
        "h1": [_clean(x) for x in h1],
        "h2": [_clean(x) for x in h2][:20],
        "jsonld_types": sorted(set(jsonld_types)),
        "has_org_schema": "Organization" in jsonld_types or "LocalBusiness" in jsonld_types,
        "has_breadcrumb_schema": "BreadcrumbList" in jsonld_types,
        "has_faq_schema": "FAQPage" in jsonld_types,
        "has_person_schema": "Person" in jsonld_types,
        "has_viewport": bool(re.search(r'name=["\']viewport["\']', h, re.I)),
        "has_twitter_card": bool(re.search(r'name=["\']twitter:card["\']', h, re.I)),
        "lang": (re.search(r'<html[^>]+lang=["\']([^"\']+)', h, re.I) or [None, None])[1],
        "hsts": "strict-transport-security" in {k.lower() for k in head},
        "images_total": len(imgs),
        "images_missing_alt": sum(1 for t in imgs if not re.search(r"alt=", t, re.I)),
        "images_lazy": sum(1 for t in imgs if re.search(r'loading=["\']lazy', t, re.I)),
        "images_modern_fmt": sum(1 for s in img_srcs if re.search(r"\.(webp|avif)(\?|$)", s or "", re.I)),
        "images_legacy_fmt": sum(1 for s in img_srcs if re.search(r"\.(jpg|jpeg|png|gif)(\?|$)", s or "", re.I)),
        "internal_links": sorted(set(u.rstrip("/") for u in internal)),
        "external_domains": ext_domains,
        "ul_count": len(re.findall(r"<ul[\s>]", h, re.I)),
        "ol_count": len(re.findall(r"<ol[\s>]", h, re.I)),
        "iframes": len(re.findall(r"<iframe[\s>]", h, re.I)),
        "published": (re.search(r'(?:article:published_time|datePublished)["\'][^>]*content=["\']([^"\']+)', h, re.I) or re.search(r'"datePublished"\s*:\s*"([^"]+)"', h) or [None, None])[1],
        "author_meta": (re.search(r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)', h, re.I) or [None, None])[1],
        "has_ad_scripts": bool(re.search(r"googlesyndication|doubleclick|adsbygoogle", h, re.I)),
        "word_count": len(text.split()),
        "body_text": text[:6000],
    }


def _clean(s: str | None) -> str:
    if not s:
        return ""
    return (
        s.replace("&#x27;", "'").replace("&#39;", "'").replace("&amp;", "&")
        .replace("&quot;", '"').replace("&nbsp;", " ").strip()
    )


def _derive_keywords(pages: list[dict]) -> list[dict]:
    """Keyword seeds from the site's own targeting (slug + title + H1)."""
    seeds = []
    for p in pages:
        path = urlparse(p["url"]).path.strip("/")
        slug = path.split("/")[-1] if path else "home"
        kw = slug.replace("-", " ").replace("_", " ").strip()
        if not kw or len(kw) > 60:
            # fall back to H1
            kw = (p.get("h1") or [""])[0][:60]
        intent = "navigational" if path in ("", "about-us", "contact-us", "about", "contact") else (
            "informational" if "/blog/" in p["url"] else "commercial")
        if kw:
            seeds.append({"keyword": kw, "target_url": p["url"], "intent": intent})
    return seeds


async def _gather_robots(client: httpx.AsyncClient, domain: str, out_dir: Path) -> SourceResult:
    base = f"https://{domain}"
    out: dict[str, Any] = {}
    try:
        r = await client.get(f"{base}/robots.txt", timeout=20)
        out["robots_txt"] = r.text[:4000] if r.status_code == 200 else None
        out["disallows"] = re.findall(r"Disallow:\s*(\S+)", r.text or "")
        out["sitemaps"] = re.findall(r"Sitemap:\s*(\S+)", r.text or "")
        llm_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"]
        out["llm_bots_blocked"] = [b for b in llm_bots if re.search(rf"User-agent:\s*{b}[\s\S]*?Disallow:\s*/", r.text or "", re.I)]
    except Exception as e:  # noqa: BLE001
        _write(out_dir, "robots.json", {"error": str(e)[:80]})
        return SourceResult("robots", False, reason=str(e)[:80])
    try:
        lr = await client.get(f"{base}/llms.txt", timeout=15)
        out["has_llms_txt"] = lr.status_code == 200
    except Exception:
        out["has_llms_txt"] = False
    _write(out_dir, "robots.json", out)
    return SourceResult("robots", True, summary={"has_llms_txt": out.get("has_llms_txt"), "llm_bots_blocked": len(out.get("llm_bots_blocked", []))})


async def _gather_psi(client: httpx.AsyncClient, domain: str, pages: list[dict], out_dir: Path) -> SourceResult:
    key = _env("GOOGLE_PSI_API_KEY")
    if not key:
        return SourceResult("psi", False, reason="GOOGLE_PSI_API_KEY not set")
    targets = [p["url"] for p in pages[:7]] or [f"https://{domain}"]
    out: dict[str, Any] = {}
    for url in targets:
        entry: dict[str, Any] = {}
        for strat in ("mobile", "desktop"):
            try:
                r = await client.get(
                    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                    params={"url": url, "key": key, "strategy": strat, "category": "performance"},
                    timeout=60,
                )
                j = r.json()
                lh = j.get("lighthouseResult", {})
                audits = lh.get("audits", {})
                entry[strat] = {
                    "performance": round((lh.get("categories", {}).get("performance", {}).get("score") or 0) * 100),
                    "lcp": audits.get("largest-contentful-paint", {}).get("numericValue"),
                    "fcp": audits.get("first-contentful-paint", {}).get("numericValue"),
                    "tbt": audits.get("total-blocking-time", {}).get("numericValue"),
                    "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                }
            except Exception as e:  # noqa: BLE001
                entry[strat] = {"error": str(e)[:60]}
        out[url] = entry
    _write(out_dir, "psi.json", out)
    return SourceResult("psi", True, summary={"pages": len(out)})


async def _gather_crux(client: httpx.AsyncClient, domain: str, out_dir: Path) -> SourceResult:
    key = _env("GOOGLE_PSI_API_KEY")  # CrUX uses the same Google API key
    if not key:
        return SourceResult("crux", False, reason="GOOGLE_PSI_API_KEY not set (CrUX shares it)")
    try:
        r = await client.post(
            f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={key}",
            json={"origin": f"https://{domain}", "metrics": ["interaction_to_next_paint", "largest_contentful_paint", "cumulative_layout_shift", "first_contentful_paint"]},
            timeout=40,
        )
        j = r.json()
        if "record" not in j:
            return SourceResult("crux", False, reason=(j.get("error", {}).get("status") or "no field data") + " (API may be disabled on the GCP project)")
        m = j["record"]["metrics"]
        p75 = {k: v.get("percentiles", {}).get("p75") for k, v in m.items()}
        _write(out_dir, "crux.json", {"origin": f"https://{domain}", "p75": p75, "raw": j})
        return SourceResult("crux", True, summary=p75)
    except Exception as e:  # noqa: BLE001
        return SourceResult("crux", False, reason=str(e)[:80])


async def _gather_wayback(client: httpx.AsyncClient, domain: str, out_dir: Path) -> SourceResult:
    try:
        r = await client.get(
            "https://web.archive.org/cdx/search/cdx",
            params={"url": domain, "output": "json", "fl": "timestamp,statuscode", "filter": "statuscode:200", "collapse": "timestamp:6", "limit": 300},
            timeout=40,
        )
        rows = r.json()[1:] if r.text.strip().startswith("[") else []
        months = sorted({row[0][:6] for row in rows})
        _write(out_dir, "wayback.json", {"snapshots": len(rows), "distinct_months": len(months), "first": months[0] if months else None, "last": months[-1] if months else None, "rows": rows})
        return SourceResult("wayback", True, summary={"snapshots": len(rows), "first": months[0] if months else None, "last": months[-1] if months else None})
    except Exception as e:  # noqa: BLE001
        return SourceResult("wayback", False, reason=str(e)[:80])


async def _gather_kg(client: httpx.AsyncClient, domain: str, brand: str, out_dir: Path) -> SourceResult:
    key = _env("GOOGLE_KG_API_KEY")
    if not key:
        return SourceResult("knowledge_graph", False, reason="GOOGLE_KG_API_KEY not set")
    try:
        r = await client.get("https://kgsearch.googleapis.com/v1/entities:search", params={"query": brand, "key": key, "limit": 5}, timeout=30)
        j = r.json()
        items = j.get("itemListElement", [])
        _write(out_dir, "entity.json", {"brand": brand, "kg": j})
        top = items[0]["result"] if items else None
        return SourceResult("knowledge_graph", True, summary={"found": bool(top), "name": top.get("name") if top else None, "has_detailed": bool(top.get("detailedDescription")) if top else False})
    except Exception as e:  # noqa: BLE001
        return SourceResult("knowledge_graph", False, reason=str(e)[:80])


# ─── DataForSEO (paid; bounded) ────────────────────────────────────────────────
def _dfs_auth() -> str | None:
    login, pw = _env("DATAFORSEO_LOGIN"), _env("DATAFORSEO_PASSWORD")
    if not login or not pw:
        return None
    return "Basic " + base64.b64encode(f"{login}:{pw}".encode()).decode()


async def _gather_dataforseo(client: httpx.AsyncClient, domain: str, brand: str, market: dict, keywords: list[dict], out_dir: Path) -> list[SourceResult]:
    auth = _dfs_auth()
    if not auth:
        return [SourceResult("dataforseo", False, reason="DATAFORSEO_LOGIN/PASSWORD not set (SERP/Labs/Keywords/Business/reviews/LLM all skipped)")]
    H = {"Authorization": auth, "Content-Type": "application/json"}
    loc = market["location_code"]
    results: list[SourceResult] = []
    out: dict[str, Any] = {}
    cost = 0.0

    async def post(path: str, body: list) -> dict:
        nonlocal cost
        r = await client.post(f"https://api.dataforseo.com{path}", headers=H, json=body, timeout=120)
        j = r.json()
        cost += float(j.get("cost") or 0)
        return j

    # SERP for top commercial/brand queries (bounded to ~10)
    serp_qs = [brand] + [k["keyword"] for k in keywords if k.get("intent") == "commercial"][:9]
    serp: dict[str, Any] = {}
    try:
        for q in serp_qs:
            j = await post("/v3/serp/google/organic/live/advanced", [{"keyword": q, "location_code": loc, "language_code": "en", "depth": 20}])
            serp[q] = j
        out["serp"] = serp
        results.append(SourceResult("dataforseo.serp", True, summary={"queries": len(serp)}))
    except Exception as e:  # noqa: BLE001
        results.append(SourceResult("dataforseo.serp", False, reason=str(e)[:80]))

    # Labs: ranked keywords + domain rank overview
    try:
        rk = await post("/v3/dataforseo_labs/google/ranked_keywords/live", [{"target": domain, "location_code": loc, "language_code": "en", "limit": 200, "order_by": ["keyword_data.keyword_info.search_volume,desc"]}])
        dr = await post("/v3/dataforseo_labs/google/domain_rank_overview/live", [{"target": domain, "location_code": loc, "language_code": "en"}])
        out["ranked_keywords"], out["domain_rank_overview"] = rk, dr
        results.append(SourceResult("dataforseo.labs", True))
    except Exception as e:  # noqa: BLE001
        results.append(SourceResult("dataforseo.labs", False, reason=str(e)[:80]))

    # Business Data: GBP profile (no owner access needed)
    try:
        bi = await post("/v3/business_data/google/my_business_info/live", [{"keyword": brand, "location_code": loc, "language_code": "en"}])
        out["my_business_info"] = bi
        results.append(SourceResult("dataforseo.business", True))
    except Exception as e:  # noqa: BLE001
        results.append(SourceResult("dataforseo.business", False, reason=str(e)[:80]))

    # Backlinks: try; record deferred/denied honestly
    try:
        bl = await post("/v3/backlinks/summary/live", [{"target": domain, "backlinks_status_type": "live"}])
        task = (bl.get("tasks") or [{}])[0]
        if task.get("status_code") == 20000:
            out["backlinks"] = bl
            results.append(SourceResult("dataforseo.backlinks", True))
        else:
            results.append(SourceResult("dataforseo.backlinks", False, reason=f"{task.get('status_message', 'unavailable')} (subscription)"))
    except Exception as e:  # noqa: BLE001
        results.append(SourceResult("dataforseo.backlinks", False, reason=str(e)[:80]))

    out["_cost_gbp"] = round(cost, 4)
    _write(out_dir, "dataforseo.json", out)
    for r in results:
        r.cost_gbp = round(cost / max(len([x for x in results if x.available]), 1), 4) if r.available else 0.0
    return results


async def _gather_gsc(client: httpx.AsyncClient, domain: str, out_dir: Path) -> SourceResult:
    cid, secret, refresh = _env("GOOGLE_OAUTH_CLIENT_ID"), _env("GOOGLE_OAUTH_CLIENT_SECRET"), _env("GOOGLE_OAUTH_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        return SourceResult("gsc", False, reason="GOOGLE_OAUTH_* not set (Search Console data skipped; dependent vars unmeasurable)")
    try:
        tr = await client.post("https://oauth2.googleapis.com/token", data={"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
        tok = tr.json().get("access_token")
        if not tok:
            return SourceResult("gsc", False, reason="token refresh failed")
        H = {"Authorization": f"Bearer {tok}"}
        sites = (await client.get("https://searchconsole.googleapis.com/webmasters/v3/sites", headers=H, timeout=30)).json()
        cand = [s["siteUrl"] for s in sites.get("siteEntry", [])]
        prop = next((u for u in cand if u == f"sc-domain:{domain}"), None) or next((u for u in cand if domain in u), None)
        if not prop:
            return SourceResult("gsc", False, reason=f"account has no access to a property for {domain} (owner must add the auditing email)")
        enc = httpx.URL(f"https://searchconsole.googleapis.com/webmasters/v3/sites/{prop.replace('/', '%2F').replace(':', '%3A')}/searchAnalytics/query")
        end = datetime.now(timezone.utc).date().isoformat()
        body = {"startDate": "2020-01-01", "endDate": end, "dimensions": ["query", "page"], "rowLimit": 5000}
        # date window: last ~90d handled by caller's choice; keep wide-but-capped
        sa = (await client.post(str(enc), headers=H, json={**body, "startDate": _days_ago(93), "endDate": _days_ago(3)}, timeout=60)).json()
        _write(out_dir, "gsc.json", {"property": prop, "search_analytics": sa})
        return SourceResult("gsc", True, summary={"property": prop, "rows": len(sa.get("rows", []))})
    except Exception as e:  # noqa: BLE001
        return SourceResult("gsc", False, reason=str(e)[:80])


def _days_ago(n: int) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


# ════════════════════════════════════════════════════════════════════════════
async def gather(domain: str, out_dir: str | Path, *, market_override: dict | None = None) -> GatherResult:
    """Gather all reachable sources for ``domain`` into ``out_dir``.

    Returns a GatherResult; writes one JSON file per source plus
    ``manifest.json`` listing availability + the derived keyword map + market.
    """
    domain = _norm_domain(domain)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    market = market_override or _market_for(domain)
    brand = domain.split(".")[0].replace("-", " ").title()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        crawl_res, pages = await _gather_crawl(client, domain, out_dir)
        keywords = _derive_keywords(pages)
        _write(out_dir, "keywords.json", keywords)

        # run the independent sources concurrently
        robots, psi, crux, wayback, kg = await asyncio.gather(
            _gather_robots(client, domain, out_dir),
            _gather_psi(client, domain, pages, out_dir),
            _gather_crux(client, domain, out_dir),
            _gather_wayback(client, domain, out_dir),
            _gather_kg(client, domain, brand, out_dir),
        )
        dfs = await _gather_dataforseo(client, domain, brand, market, keywords, out_dir)
        gsc = await _gather_gsc(client, domain, out_dir)

    sources = [crawl_res, robots, psi, crux, wayback, kg, *dfs, gsc]
    total_cost = round(sum(s.cost_gbp for s in sources), 4)
    manifest = {
        "domain": domain,
        "brand": brand,
        "market": market,
        "gathered_at_utc": datetime.now(timezone.utc).isoformat(),
        "keyword_seeds": len(keywords),
        "total_cost_gbp": total_cost,
        "sources": [
            {"name": s.name, "available": s.available, "reason": s.reason, "summary": s.summary, "cost_gbp": s.cost_gbp}
            for s in sources
        ],
        "available": [s.name for s in sources if s.available],
        "unavailable": {s.name: s.reason for s in sources if not s.available},
        "note": (
            "Each source reports availability honestly. For any source marked "
            "unavailable, the session MUST mark variables that depend on it "
            "'unmeasurable' with that reason - never guess a pass/fail."
        ),
    }
    _write(out_dir, "manifest.json", manifest)
    return GatherResult(domain=domain, out_dir=out_dir, market=market, sources=sources, total_cost_gbp=total_cost)
