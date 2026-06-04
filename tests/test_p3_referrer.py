"""Tests for the referrer-crawl-backed P3 extractors: P3-20 (link position),
P3-27 (brand+topic co-occurrence), and P3-30 (disavow, owner-attested)."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from seomate.adapters import AdapterContext
from seomate.data_contract import CaptureStatus
from seomate.pillars import BrandIdentity, SiteData
from seomate.pillars.p3_backlinks import (
    _topic_terms,
    capture_p3_20,
    capture_p3_27,
    capture_p3_30,
)
from seomate.utils.cost_tracker import CostTracker
from seomate.utils.html_fetch import FetchedHtml


def _ctx() -> AdapterContext:
    return AdapterContext(
        audit_id=uuid4(),
        cost_tracker=CostTracker(cap_gbp=5.0, warn_fraction=0.8),
        taxonomy_version="test",
    )


def _page(url: str, body: str) -> FetchedHtml:
    html = (
        f"<html><body><article><h1>Industry insight</h1><p>{body}</p>"
        "<p>" + ("More background context follows here. " * 40) + "</p>"
        "</article></body></html>"
    )
    return FetchedHtml(
        url=url, requested_url=url, status_code=200, html=html,
        content_type="text/html", final_redirect_chain=(url,),
    )


def _site(**ov) -> SiteData:
    base = dict(
        domain="pixelettetech.com",
        primary_url="https://pixelettetech.com/",
        brand=BrandIdentity(name="Pixelette"),
        ranked_keywords=[
            {"keyword": "blockchain development company"},
            {"keyword": "enterprise software services"},
            {"keyword": "mobile app development"},
        ],
    )
    base.update(ov)
    return SiteData(**base)


# ─── _topic_terms ───────────────────────────────────────────────────────────

def test_topic_terms_extracts_significant_tokens():
    terms = _topic_terms(_site())
    assert "blockchain" in terms
    assert "development" in terms
    assert "enterprise" in terms
    assert "mobile" in terms
    # stopword-ish generic terms excluded
    assert "services" not in terms
    assert "company" not in terms


# ─── P3-27 co-occurrence ────────────────────────────────────────────────────

def test_p3_27_snippet_cooccurrence_measures():
    """Snippet-only path (no crawled pages) still yields a real measurement."""
    links = [
        {
            "url_from": "https://techblog.com/post",
            "anchor": "blockchain development",
            "text_pre": "Pixelette offers",
            "text_post": "for enterprise clients",
            "dofollow": True,
            "domain_from": "techblog.com",
        }
    ]
    rec = asyncio.run(capture_p3_27(_ctx(), _site(backlinks_links=links)))
    assert rec.status in (CaptureStatus.PASSED, CaptureStatus.FAILED)
    assert rec.value["contexts_analysed"] == 1
    assert rec.value["from_snippets"] == 1
    assert rec.value["cooccurrence_count"] == 1  # brand + topic both present
    assert rec.status == CaptureStatus.PASSED


def test_p3_27_uses_crawled_body_when_available():
    links = [{
        "url_from": "https://techblog.com/post",
        "anchor": "blockchain development",
        "text_pre": "", "text_post": "", "dofollow": True,
        "domain_from": "techblog.com",
    }]
    pages = {
        "https://techblog.com/post": _page(
            "https://techblog.com/post",
            "Pixelette is a leading blockchain development partner for enterprise teams.",
        )
    }
    rec = asyncio.run(
        capture_p3_27(_ctx(), _site(backlinks_links=links, referrer_pages=pages))
    )
    assert rec.value["from_crawled_pages"] == 1
    assert rec.value["cooccurrence_count"] == 1


def test_p3_27_unmeasurable_without_backlinks_links():
    rec = asyncio.run(capture_p3_27(_ctx(), _site()))
    assert rec.status == CaptureStatus.UNMEASURABLE


# ─── P3-20 link position ────────────────────────────────────────────────────

def test_p3_20_measures_position_from_crawled_pages():
    links, pages = [], {}
    for i in range(6):
        url = f"https://ref{i}.com/article"
        links.append({
            "url_from": url, "anchor": "blockchain development",
            "dofollow": True, "domain_from": f"ref{i}.com",
        })
        # anchor sits near the very top of the body -> low position
        pages[url] = _page(url, "Pixelette blockchain development is featured here.")
    rec = asyncio.run(
        capture_p3_20(_ctx(), _site(backlinks_links=links, referrer_pages=pages))
    )
    assert rec.status == CaptureStatus.PASSED  # >=5 located, all top-half
    assert rec.value["links_located"] == 6
    assert rec.value["top_half_pct"] == 100.0
    assert "distribution" in rec.value


def test_p3_20_partial_when_few_located():
    url = "https://ref.com/a"
    links = [{"url_from": url, "anchor": "blockchain development",
              "dofollow": True, "domain_from": "ref.com"}]
    pages = {url: _page(url, "Pixelette blockchain development feature.")}
    rec = asyncio.run(
        capture_p3_20(_ctx(), _site(backlinks_links=links, referrer_pages=pages))
    )
    assert rec.status == CaptureStatus.PARTIAL  # only 1 located
    assert rec.value["links_located"] == 1


def test_p3_20_unmeasurable_without_backlinks_links():
    rec = asyncio.run(capture_p3_20(_ctx(), _site()))
    assert rec.status == CaptureStatus.UNMEASURABLE


# ─── P3-30 disavow ──────────────────────────────────────────────────────────

def test_p3_30_not_applicable_without_owner_file():
    rec = asyncio.run(capture_p3_30(_ctx(), _site(backlinks_summary={"backlinks_spam_score": 11})))
    assert rec.status == CaptureStatus.NOT_APPLICABLE
    assert "owner_input_path" in rec.value


def test_p3_30_passes_when_disavow_covers_toxic():
    refs = [
        {"domain": "spam1.ru", "backlinks_spam_score": 80},
        {"domain": "clean.com", "backlinks_spam_score": 5},
    ]
    rec = asyncio.run(capture_p3_30(_ctx(), _site(
        owner_disavow_domains=["spam1.ru"], referring_domains=refs,
    )))
    assert rec.status == CaptureStatus.PASSED
    assert rec.value["toxic_uncovered_by_disavow"] == []


def test_p3_30_fails_when_toxic_uncovered():
    refs = [{"domain": "spam2.cn", "backlinks_spam_score": 75}]
    rec = asyncio.run(capture_p3_30(_ctx(), _site(
        owner_disavow_domains=["other.com"], referring_domains=refs,
    )))
    assert rec.status == CaptureStatus.FAILED
    assert "spam2.cn" in rec.value["toxic_uncovered_by_disavow"]
