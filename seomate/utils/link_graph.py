"""Internal link graph extraction.

Builds a directed graph of internal links from already-cached HTML.
Used by H1b composition extractors that need site-wide reachability,
inbound-link counts, and click-depth-from-homepage measurements.

Constitutional principle: never re-fetch. Operates entirely on the
HTML already cached in ``SiteData.html_pages``. The graph is built
once at audit start and consumed by every link-graph-aware extractor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

# Element types whose ``href`` / ``src`` we treat as a navigation link.
_LINK_SELECTORS = ("a[href]",)


@dataclass(frozen=True)
class LinkRef:
    """One outbound link found in a page's HTML."""

    source_url: str
    target_url: str          # canonicalised: scheme://host/path?query (no fragment)
    anchor_text: str
    rel: str                 # raw rel attribute (e.g. 'nofollow noopener')
    is_internal: bool
    is_self: bool


@dataclass
class LinkGraph:
    """Directed internal-link graph for the audited site.

    Stores both directions (outbound from each page, inbound to each
    page) so callers can answer ``who links to X?`` and ``what does X
    link to?`` in O(1).
    """

    site_host: str
    pages: set[str] = field(default_factory=set)
    outbound: dict[str, list[LinkRef]] = field(default_factory=dict)
    inbound: dict[str, list[LinkRef]] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def outbound_internal(self, url: str) -> list[LinkRef]:
        return [r for r in self.outbound.get(url, []) if r.is_internal and not r.is_self]

    def inbound_internal(self, url: str) -> list[LinkRef]:
        return [r for r in self.inbound.get(url, []) if r.is_internal and not r.is_self]

    def inbound_count(self, url: str) -> int:
        return len(self.inbound_internal(url))

    def outbound_count(self, url: str) -> int:
        return len(self.outbound_internal(url))

    def click_depth_from(self, root: str) -> dict[str, int]:
        """BFS from ``root``. Returns ``{url: hop_count}`` for reachable pages.

        Pages not reachable from ``root`` are absent from the result.
        Use the absence to identify orphans relative to the homepage.
        """
        root = _canonicalise(root)
        if root not in self.pages:
            # Try matching by path (strip 'www.', trailing slash) so a config
            # primary_url of https://www.example.com still matches a page
            # canonicalised as https://example.com/.
            candidate = _match_root(root, self.pages)
            if candidate is None:
                return {}
            root = candidate
        depths: dict[str, int] = {root: 0}
        queue: deque[str] = deque([root])
        while queue:
            current = queue.popleft()
            d = depths[current]
            for ref in self.outbound_internal(current):
                target = ref.target_url
                if target not in self.pages:
                    continue
                if target in depths:
                    continue
                depths[target] = d + 1
                queue.append(target)
        return depths

    def orphans(self, root: str) -> list[str]:
        """Pages with zero inbound internal links AND not reachable from ``root``.

        We use the dual definition (no inbound + unreachable) to be
        conservative: a page that's only reachable via redirect chain
        won't show in either map.
        """
        depths = self.click_depth_from(root)
        out: list[str] = []
        for url in sorted(self.pages):
            if self.inbound_count(url) > 0:
                continue
            if url in depths:
                continue
            out.append(url)
        return out


# ─── Build helpers ──────────────────────────────────────────────────────────


def build_link_graph(
    html_pages: dict[str, str],   # {requested_url: html_text}
    *,
    site_host: str,
) -> LinkGraph:
    """Build a LinkGraph from the cached HTML map.

    ``site_host`` is the lower-cased ``netloc`` (e.g. ``pixelettetech.com``)
    used to classify each link as internal or external. We treat both
    ``site_host`` and its ``www.``-stripped form as internal so links that
    cross the apex / www boundary aren't mistakenly classified as external.
    """
    host_l = site_host.lower().removeprefix("www.")
    graph = LinkGraph(site_host=site_host)

    # First pass: register canonical URLs as nodes so the link extraction
    # below can look up internal targets without falsely classifying them
    # as off-site (e.g. a link to https://example.com/foo when the audit
    # registered the page as https://www.example.com/foo).
    for url in html_pages:
        graph.pages.add(_canonicalise(url))

    for source_url, html in html_pages.items():
        canonical_source = _canonicalise(source_url)
        if not html:
            continue
        refs = _extract_links(html, source_url, host_l, known_pages=graph.pages)
        graph.outbound.setdefault(canonical_source, []).extend(refs)
        for ref in refs:
            graph.inbound.setdefault(ref.target_url, []).append(ref)

    return graph


def _extract_links(
    html: str,
    source_url: str,
    site_host_lower: str,
    *,
    known_pages: set[str],
) -> list[LinkRef]:
    soup = BeautifulSoup(html, "html.parser")
    refs: list[LinkRef] = []
    canonical_source = _canonicalise(source_url)
    for selector in _LINK_SELECTORS:
        for el in soup.select(selector):
            href = el.get("href") or ""
            href = href.strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            absolute = urljoin(source_url, href)
            target = _canonicalise(absolute)
            target_host = (urlsplit(target).netloc or "").lower().removeprefix("www.")
            is_internal = target_host == site_host_lower
            anchor_text = (el.get_text() or "").strip()
            rel = " ".join(el.get("rel") or []) if isinstance(el.get("rel"), list) else (
                el.get("rel") or ""
            )
            refs.append(
                LinkRef(
                    source_url=canonical_source,
                    target_url=target,
                    anchor_text=anchor_text[:300],
                    rel=rel,
                    is_internal=is_internal,
                    is_self=target == canonical_source,
                )
            )
    return refs


def _canonicalise(url: str) -> str:
    """Strip fragment, normalise scheme + host casing, drop trailing slash."""
    if not url:
        return ""
    no_frag, _ = urldefrag(url)
    parts = urlsplit(no_frag)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    # Drop a single trailing slash from the path so /foo and /foo/ collapse.
    path = parts.path
    if path and path != "/" and path.endswith("/"):
        path = path[:-1]
    canonical = f"{scheme}://{netloc}{path}"
    if parts.query:
        canonical = f"{canonical}?{parts.query}"
    return canonical


def _match_root(root: str, pages: Iterable[str]) -> str | None:
    """Find the first page that matches ``root`` ignoring www/trailing-slash."""
    target = _canonicalise(root)
    target_norm = _norm_for_match(target)
    for p in pages:
        if _norm_for_match(p) == target_norm:
            return p
    # Fall back: find anything pointing to the bare host root path.
    parts = urlsplit(target)
    bare_host = (parts.netloc or "").lower().removeprefix("www.")
    for p in pages:
        p_parts = urlsplit(p)
        if (
            (p_parts.netloc or "").lower().removeprefix("www.") == bare_host
            and (p_parts.path or "/") in ("", "/")
        ):
            return p
    return None


def _norm_for_match(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.netloc or "").lower().removeprefix("www.")
    path = (parts.path or "/").rstrip("/") or "/"
    return f"{host}{path}"


def compute_pagerank(
    graph: LinkGraph,
    *,
    damping: float = 0.85,
    iterations: int = 50,
) -> dict[str, float]:
    """Simple PageRank-style authority score over the internal link graph.

    Returns ``{url: score}`` with scores summing to roughly N (i.e.
    average score ~1.0). Not the literal Google ``PageRankNS`` leak
    feature (we don't have Google's signals), but a defensible
    composition that gives every page a relative authority weight.
    Used by P1-24 to weight inbound link quality.
    """
    urls = list(graph.pages)
    if not urls:
        return {}
    n = len(urls)
    base = (1.0 - damping)
    scores: dict[str, float] = {u: 1.0 for u in urls}

    # Pre-compute outgoing-internal degree per page (excluding self-loops).
    outgoing: dict[str, list[str]] = {
        u: [r.target_url for r in graph.outbound_internal(u) if r.target_url in graph.pages]
        for u in urls
    }
    out_degree: dict[str, int] = {u: len(outgoing[u]) for u in urls}

    for _ in range(iterations):
        new_scores: dict[str, float] = {u: base for u in urls}
        # Contribution from sink pages (no outbound links): distribute evenly.
        sink_mass = sum(scores[u] for u in urls if out_degree[u] == 0)
        for u in urls:
            new_scores[u] += damping * (sink_mass / n)
        # Contribution from each page's outbound links.
        for u in urls:
            degree = out_degree[u]
            if degree == 0:
                continue
            share = damping * scores[u] / degree
            for target in outgoing[u]:
                new_scores[target] += share
        scores = new_scores
    return scores
