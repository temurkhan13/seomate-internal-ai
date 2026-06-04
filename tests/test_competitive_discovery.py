"""Tests for content-based competitor discovery , service-query extraction
from the target's own homepage (title + headings)."""
from __future__ import annotations

from seomate.competitive import _service_queries_from_html


def test_extracts_service_queries_from_headings():
    html = """<html><head>
      <title>Pixelette Technologies | Software Development</title></head>
      <body>
        <h1>Pixelette Technologies</h1>
        <h2>Blockchain Development</h2>
        <h2>Mobile App Development</h2>
        <h2>Custom Software Development Company</h2>
        <h2>Digital Marketing</h2>
        <h3>About Us</h3><h3>Why Choose Us</h3><h3>Contact</h3>
      </body></html>"""
    qs = _service_queries_from_html(html, "pixelettetech.com")

    # bare service phrases get "company" appended (SERP returns competitors, not tutorials)
    assert "blockchain development company" in qs
    assert "mobile app development company" in qs
    assert "digital marketing company" in qs
    # a phrase that already names a business entity is not doubled
    assert "custom software development company" in qs
    assert not any(q.endswith("company company") for q in qs)
    # generic section labels are dropped (neither bare nor "+ company")
    for g in ("about us", "why choose us", "contact"):
        assert all(q not in (g, f"{g} company") for q in qs)


def test_empty_html_returns_nothing():
    assert _service_queries_from_html("", "x.com") == []


def test_generic_or_brand_only_filtered():
    html = (
        "<html><body><h2>Home</h2><h2>Our Services</h2>"
        "<h2>Contact Us</h2><h2>Portfolio</h2></body></html>"
    )
    assert _service_queries_from_html(html, "x.com") == []


def test_overlong_and_too_short_phrases_skipped():
    html = (
        "<html><body>"
        "<h2>AI</h2>"  # one word, too short
        "<h2>We design build and maintain enterprise grade software platforms end to end</h2>"  # too long
        "<h2>Web Development</h2>"  # just right
        "</body></html>"
    )
    qs = _service_queries_from_html(html, "x.com")
    assert qs == ["web development company"]
