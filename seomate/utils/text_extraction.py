"""Main-content text extraction.

Wraps trafilatura's extractor to give every audit a stable per-page
"main content" view, free of nav / footer / cookie-banner / sidebar
boilerplate. Used as the input to embedding generation, schema-vs-text
diff checks, and any future LLM evaluation prompts.

Trafilatura is the de-facto Python standard for clean main-content
extraction (used by Common Crawl's text pipeline). We never call it
on the network — only on already-fetched HTML. Falls back to a plain
BeautifulSoup ``get_text()`` strip if trafilatura returns nothing,
so we never end up with an empty representation when the page is
real but trafilatura's heuristics misfire.
"""
from __future__ import annotations

from dataclasses import dataclass

import trafilatura
from bs4 import BeautifulSoup

# Element types we drop before fallback extraction.
_NOISE_TAGS = ("script", "style", "noscript", "template", "svg")
_BOILERPLATE_TAGS = ("nav", "header", "footer", "aside")


@dataclass(frozen=True)
class PageText:
    """One page's extracted main-content text + metadata."""

    url: str
    main_text: str
    word_count: int
    extractor_used: str          # 'trafilatura' or 'fallback_bs4'


def extract_main_text(html: str, *, url: str) -> PageText:
    """Extract main-content text from one page's HTML.

    Returns ``PageText`` with the cleanest text we can derive. ``main_text``
    is empty only when the input HTML is itself empty.
    """
    if not html:
        return PageText(url=url, main_text="", word_count=0, extractor_used="empty_input")

    main = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=False,
        no_fallback=False,
        url=url,
    )
    if main and main.strip():
        words = main.split()
        return PageText(
            url=url,
            main_text=main,
            word_count=len(words),
            extractor_used="trafilatura",
        )

    # Fallback: BeautifulSoup with boilerplate stripping.
    soup = BeautifulSoup(html, "html.parser")
    for tag in _NOISE_TAGS + _BOILERPLATE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = " ".join(text.split())
    return PageText(
        url=url,
        main_text=text,
        word_count=len(text.split()),
        extractor_used="fallback_bs4",
    )
