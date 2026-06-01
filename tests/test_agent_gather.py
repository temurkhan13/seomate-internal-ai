"""Tests for the agent gather layer.

The trust-critical behaviours: (1) market + keyword auto-derivation, (2) honest
availability - an unconfigured source is recorded ``unavailable`` with a reason,
never a silent pass, (3) the crawl HTML analyser extracts the on-page signals
the session relies on, (4) a manifest is always written. No real network: respx
mocks httpx, and paid/keyed sources are unconfigured (no env) so they report
unavailable - which is itself the behaviour under test.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from seomate.agent.gather import (
    _analyze_html,
    _derive_keywords,
    _market_for,
    _norm_domain,
    gather,
)

SITEMAP = """<?xml version="1.0"?>
<urlset><url><loc>https://abcd.com/</loc></url>
<url><loc>https://abcd.com/ai-services</loc></url>
<url><loc>https://abcd.com/blog/post-one</loc></url></urlset>"""

PAGE_HTML = """<!doctype html><html lang="en"><head>
<title>ABCD - AI Services</title>
<meta name="description" content="We build AI.">
<link rel="canonical" href="https://abcd.com/ai-services">
<meta name="viewport" content="width=device-width">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{"@type":"Organization"}</script>
</head><body><h1>AI Services</h1><h2>Why us</h2>
<img src="/a.webp" alt="x"><img src="/b.png" loading="lazy">
<a href="https://abcd.com/contact-us">contact</a>
<a href="https://external.com/ref">ref</a>
<p>Some real body text about artificial intelligence services.</p>
</body></html>"""


def test_norm_domain():
    assert _norm_domain("https://www.ABCD.com/") == "abcd.com"
    assert _norm_domain("abcd.com") == "abcd.com"


def test_market_by_tld():
    assert _market_for("abcd.co.uk")["country"] == "GB"
    assert _market_for("abcd.com")["country"] == "US"
    assert _market_for("abcd.de")["country"] == "DE"


def test_analyze_html_extracts_signals():
    resp = httpx.Response(200, text=PAGE_HTML, request=httpx.Request("GET", "https://abcd.com/ai-services"))
    a = _analyze_html("https://abcd.com/ai-services", resp)
    assert a["title"] == "ABCD - AI Services"
    assert a["canonical_is_self"] is True
    assert a["has_org_schema"] is True
    assert a["has_viewport"] is True
    assert a["has_twitter_card"] is True
    assert a["images_total"] == 2
    assert a["images_modern_fmt"] == 1  # the .webp
    assert a["images_legacy_fmt"] == 1  # the .png
    assert a["images_lazy"] == 1
    assert "https://abcd.com/contact-us" in a["internal_links"]
    assert "external.com" in a["external_domains"]
    assert a["word_count"] > 0


def test_derive_keywords_from_pages():
    pages = [
        {"url": "https://abcd.com/", "h1": ["Home"]},
        {"url": "https://abcd.com/ai-services", "h1": ["AI"]},
        {"url": "https://abcd.com/blog/post-one", "h1": ["Post"]},
    ]
    kws = _derive_keywords(pages)
    by_url = {k["target_url"]: k for k in kws}
    assert by_url["https://abcd.com/ai-services"]["keyword"] == "ai services"
    assert by_url["https://abcd.com/ai-services"]["intent"] == "commercial"
    assert by_url["https://abcd.com/blog/post-one"]["intent"] == "informational"
    assert by_url["https://abcd.com/"]["intent"] == "navigational"


@respx.mock
@pytest.mark.asyncio
async def test_gather_honest_availability(tmp_path: Path, monkeypatch):
    """With no API keys set, keyed sources must be 'unavailable' with a reason,
    while free crawl/robots/wayback still run. A manifest is always written."""
    # ensure keyed sources are unconfigured
    for k in ["GOOGLE_PSI_API_KEY", "GOOGLE_KG_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN"]:
        monkeypatch.delenv(k, raising=False)

    respx.get("https://abcd.com/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://abcd.com/").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    respx.get("https://abcd.com/ai-services").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    respx.get("https://abcd.com/blog/post-one").mock(return_value=httpx.Response(200, text=PAGE_HTML))
    respx.get("https://abcd.com/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nAllow: /\nSitemap: https://abcd.com/sitemap.xml"))
    respx.get("https://abcd.com/llms.txt").mock(return_value=httpx.Response(404))
    respx.get(url__startswith="https://web.archive.org/cdx").mock(return_value=httpx.Response(200, text=json.dumps([["timestamp", "statuscode"], ["20210101000000", "200"], ["20260101000000", "200"]])))

    result = await gather("abcd.com", tmp_path)

    # free sources available
    assert "crawl" in result.available_sources
    assert "robots" in result.available_sources
    assert "wayback" in result.available_sources
    # keyed sources unavailable WITH a reason (the anti-guess contract)
    assert "psi" in result.unavailable_sources
    assert "GOOGLE_PSI_API_KEY" in result.unavailable_sources["psi"]
    assert "gsc" in result.unavailable_sources
    assert "knowledge_graph" in result.unavailable_sources
    # dataforseo unconfigured -> reported, not silently passed
    assert any("dataforseo" in name for name in result.unavailable_sources)

    # manifest always written + well-formed
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["domain"] == "abcd.com"
    assert manifest["keyword_seeds"] >= 1
    assert "note" in manifest and "unmeasurable" in manifest["note"]
    # crawl cache written with real pages
    crawl = json.loads((tmp_path / "crawl.json").read_text())
    assert crawl["page_count"] >= 1
