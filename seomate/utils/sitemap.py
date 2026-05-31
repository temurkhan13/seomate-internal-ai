"""Sitemap discovery for the audited site.

Used by site-level extractors to know which URLs to audit. We try the
two conventional sitemap paths and recurse into a sitemap index if one
is encountered. Falls back gracefully to ``[]`` so callers can decide
whether to audit only the primary URL or skip the variable as
unmeasurable.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# Sitemap protocol XML namespace.
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Conventional locations tried in order.
DEFAULT_SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
)


async def discover_urls(
    primary_url: str,
    *,
    timeout: float = 30.0,
    max_urls: int = 500,
    max_depth: int = 3,
) -> list[str]:
    """Return a deduplicated list of URLs discovered via sitemap(s).

    Parameters
    ----------
    primary_url:
        The site's canonical homepage, e.g. ``https://www.pixelettetech.com``.
    timeout:
        Per-request HTTP timeout in seconds.
    max_urls:
        Hard cap on the URL set to avoid runaway audits on large sites.
    max_depth:
        Maximum recursion depth into nested sitemap indexes.

    Returns
    -------
    list[str]
        URLs found in the sitemap(s). Empty list if no sitemap is reachable.
    """
    parsed = urlparse(primary_url)
    if not parsed.scheme or not parsed.netloc:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"

    seen: set[str] = set()
    out: list[str] = []
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"},
    ) as client:
        for path in DEFAULT_SITEMAP_PATHS:
            url = urljoin(base, path)
            urls = await _collect(client, url, depth=0, max_depth=max_depth)
            for u in urls:
                if u in seen:
                    continue
                seen.add(u)
                out.append(u)
                if len(out) >= max_urls:
                    return out
            if out:
                # Found a working sitemap; don't fall back to the next path.
                break
    return out


async def _collect(
    client: httpx.AsyncClient,
    sitemap_url: str,
    *,
    depth: int,
    max_depth: int,
) -> list[str]:
    if depth > max_depth:
        return []
    try:
        resp = await client.get(sitemap_url)
    except httpx.RequestError as exc:
        logger.debug("sitemap fetch failed for %s: %s", sitemap_url, exc)
        return []
    if resp.status_code >= 400:
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return []

    tag = _strip_ns(root.tag)
    if tag == "sitemapindex":
        nested: list[str] = []
        for sm in root.findall(f"{{{SITEMAP_NS}}}sitemap"):
            loc_el = sm.find(f"{{{SITEMAP_NS}}}loc")
            if loc_el is not None and loc_el.text:
                nested.extend(
                    await _collect(
                        client,
                        loc_el.text.strip(),
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                )
        return nested
    if tag == "urlset":
        urls: list[str] = []
        for u in root.findall(f"{{{SITEMAP_NS}}}url"):
            loc_el = u.find(f"{{{SITEMAP_NS}}}loc")
            if loc_el is not None and loc_el.text:
                urls.append(loc_el.text.strip())
        return urls
    return []


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
