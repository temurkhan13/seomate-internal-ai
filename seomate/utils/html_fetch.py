"""Direct HTML fetch utility.

Used for variables that need the literal HTML the server serves —
robots.txt-anchored crawl behaviour is one example, but the bigger
consumer is the schema markup family, which has to parse JSON-LD,
microdata, and RDFa from the page itself rather than relying on
DataForSEO's pre-parsed view (which loses fidelity on `@graph`
linkage and exotic block layouts).

Constitutional principle: this never authenticates. We send a clearly
identified user agent so site owners can opt out via robots.txt, and
we honour redirects so we follow apex-to-www and www-to-apex moves.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "SEOMATE-Auditor/0.1 (+https://pixelettetech.com)"


@dataclass(frozen=True)
class FetchedHtml:
    """One page's literal HTML response."""

    url: str                          # final URL after redirects
    requested_url: str                # the URL we asked for
    status_code: int
    html: str                         # decoded body
    content_type: str | None
    final_redirect_chain: tuple[str, ...]  # all hops, including the final URL
    http_version: str | None = None   # e.g. 'HTTP/1.1', 'HTTP/2'
    headers: tuple[tuple[str, str], ...] = ()  # response headers
    fetch_error: str | None = None


async def fetch_html_pages(
    urls: list[str],
    *,
    concurrency: int = 8,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, FetchedHtml]:
    """Fetch every URL in ``urls`` in parallel, bounded by ``concurrency``.

    The result is keyed by the *requested* URL (not the final redirect
    target) so callers can join the result back onto the URL list they
    sent in. Failures populate ``fetch_error`` instead of raising — we
    treat a fetch failure as data, not as an audit-fatal exception.
    """
    if not urls:
        return {}

    sem = asyncio.Semaphore(concurrency)
    out: dict[str, FetchedHtml] = {}

    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=True,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    ) as client:

        async def _one(url: str) -> None:
            async with sem:
                try:
                    resp = await client.get(url)
                except Exception as exc:  # noqa: BLE001 - failure is data
                    out[url] = FetchedHtml(
                        url=url,
                        requested_url=url,
                        status_code=0,
                        html="",
                        content_type=None,
                        final_redirect_chain=(),
                        fetch_error=f"{type(exc).__name__}: {exc}",
                    )
                    return
            chain = tuple(str(h.url) for h in resp.history) + (str(resp.url),)
            out[url] = FetchedHtml(
                url=str(resp.url),
                requested_url=url,
                status_code=resp.status_code,
                html=resp.text if resp.status_code < 400 else "",
                content_type=resp.headers.get("content-type"),
                final_redirect_chain=chain,
                http_version=resp.http_version,
                headers=tuple((k.lower(), v) for k, v in resp.headers.items()),
                fetch_error=None,
            )

        await asyncio.gather(*[_one(u) for u in urls])

    return out
