"""Tests for content-based competitor discovery , service-query extraction
from the target's own homepage (title + headings), brand/intent classification,
keyword-gap hygiene, and Knowledge-Graph entity matching."""
from __future__ import annotations

from types import SimpleNamespace

from seomate.competitive import (
    _brand_info,
    _clean_gaps,
    _commercial,
    _focus_terms,
    _is_brand_kw,
    _kw_fits_focus,
    _match_entity,
    _self_audit,
    _service_queries_from_html,
)


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


# ─── intent-based money-keyword classification ──────────────────────────────
def test_commercial_uses_intent_not_cpc():
    # An informational term WITH a CPC is not a money keyword (the opentext /
    # methodologies noise that CPC>0 used to wave through).
    assert _commercial({"intent": "informational", "cpc": 8.47}) is False
    assert _commercial({"intent": "navigational", "cpc": 23.51}) is False
    assert _commercial({"intent": "commercial", "cpc": 0.0}) is True
    assert _commercial({"intent": "transactional", "cpc": 1.0}) is True
    # CPC is only a fallback when intent is missing.
    assert _commercial({"intent": None, "cpc": 2.0}) is True
    assert _commercial({"intent": None, "cpc": 0.0}) is False


# ─── brand detection ────────────────────────────────────────────────────────
def test_brand_info_drops_short_joined_form():
    # "n-ix" must not synthesise the 3-char joined token "nix" (collides with the
    # Nix package manager); the parts {n, ix} remain for brand-keyword stripping.
    b = _brand_info("n-ix.com")
    assert "nix" not in b["tokens"]
    assert {"n", "ix"} <= b["tokens"]
    # a long single-part brand keeps its joined form
    assert "itransition" in _brand_info("itransition.com")["tokens"]


def test_brand_keyword_detection_prefix():
    brand = _brand_info("pixelettetech.com")
    # brand-adjacent term registers as branded even though the domain root is the
    # longer "pixelettetech" (the "<brand> photography" case)
    assert _is_brand_kw("pixelette photography", brand) is True
    assert _is_brand_kw("software development company", brand) is False


# ─── keyword-gap hygiene ────────────────────────────────────────────────────
def test_clean_gaps_strips_noise_keeps_money_keywords():
    their = {
        "it consulting": {"volume": 2400, "cpc": 19.0, "difficulty": 0,
                           "intent": "commercial", "position": 17, "url": "/x"},
        "opentext": {"volume": 3600, "cpc": 8.47, "difficulty": 9,
                     "intent": "informational", "position": 12, "url": "/y"},
        "methodologies": {"volume": 9900, "cpc": 1.94, "difficulty": 19,
                          "intent": "informational", "position": 14, "url": "/z"},
        "ai development company": {"volume": 480, "cpc": 71.5, "difficulty": 37,
                                   "intent": "commercial", "position": 4, "url": "/a"},
        "deep commercial": {"volume": 5000, "cpc": 10.0, "difficulty": 20,
                            "intent": "commercial", "position": 55, "url": "/b"},
    }
    comp_brand = _brand_info("competitor.com")
    target_brand = _brand_info("pixelettetech.com")
    gaps = _clean_gaps(their, set(), comp_brand, target_brand, top=10)
    kws = {g["keyword"] for g in gaps}
    assert "it consulting" in kws
    assert "ai development company" in kws
    assert "opentext" not in kws          # informational brand noise
    assert "methodologies" not in kws     # informational
    assert "deep commercial" not in kws   # commercial but position 55 (page 6)


def test_self_audit_page1_is_the_real_money_count():
    our = {
        "customizable solutions": {"volume": 210, "cpc": 0.0, "difficulty": 10,
                                   "intent": "commercial", "position": 81, "url": "/x"},
        "pixelette photography": {"volume": 90, "cpc": 0.0, "difficulty": 1,
                                  "intent": "informational", "position": 74, "url": "/contact"},
    }
    sa = _self_audit("pixelettetech.com", our, _brand_info("pixelettetech.com"), [])
    # a commercial term at position 81 is not "owned" , 0 page-1 money keywords
    assert sa["money_keywords_owned"] == 0
    assert sa["page1_keywords"] == 0
    assert sa["total_ranked"] == 2


# ─── strategic focus (fit-ranking, not volume-only) ─────────────────────────
def test_focus_terms_strips_generic_words():
    terms = _focus_terms(
        ["ai development services", "blockchain development company", "smart contract"]
    )
    assert {"ai", "blockchain", "smart", "contract"} <= terms
    for generic in ("development", "services", "company"):
        assert generic not in terms
    assert _focus_terms([]) == frozenset()
    assert _focus_terms(None) == frozenset()


def test_kw_fits_focus_whole_word_only():
    focus = _focus_terms(["ai development", "blockchain"])
    assert _kw_fits_focus("ai chatbot development", focus) is True
    assert _kw_fits_focus("blockchain consultant", focus) is True
    # the 2-char 'ai' must NOT match inside 'email' / 'retail'
    assert _kw_fits_focus("email marketing", focus) is False
    assert _kw_fits_focus("retail software", focus) is False
    # no focus terms -> nothing fits (volume-only fallback)
    assert _kw_fits_focus("ai development", frozenset()) is False


def test_clean_gaps_focus_ranks_on_strategy_above_high_volume_generic():
    their = {
        "web design firms": {"volume": 4400, "cpc": 15.0, "difficulty": 20,
                             "intent": "commercial", "position": 10, "url": "/w"},
        "ai development services": {"volume": 320, "cpc": 30.0, "difficulty": 9,
                                    "intent": "commercial", "position": 8, "url": "/a"},
        "smart contract development": {"volume": 70, "cpc": 5.0, "difficulty": 4,
                                       "intent": "commercial", "position": 6, "url": "/s"},
    }
    focus = _focus_terms(["ai development services", "blockchain development", "smart contract"])
    gaps = _clean_gaps(
        their, set(), _brand_info("rival.com"), _brand_info("pixelettetech.com"),
        focus_terms=focus, top=10,
    )
    # on-strategy gaps lead even though the generic term has ~14x the volume
    assert [g["keyword"] for g in gaps][:2] == [
        "ai development services", "smart contract development",
    ]
    assert gaps[-1]["keyword"] == "web design firms"
    assert gaps[0]["fit"] is True and gaps[-1]["fit"] is False


def test_clean_gaps_without_focus_is_volume_only_unchanged():
    their = {
        "web design firms": {"volume": 4400, "cpc": 15.0, "difficulty": 20,
                             "intent": "commercial", "position": 10, "url": "/w"},
        "ai development services": {"volume": 320, "cpc": 30.0, "difficulty": 9,
                                    "intent": "commercial", "position": 8, "url": "/a"},
    }
    gaps = _clean_gaps(their, set(), _brand_info("rival.com"), _brand_info("pixelettetech.com"), top=10)
    # no focus -> pure volume sort, and nothing is marked fit
    assert gaps[0]["keyword"] == "web design firms"
    assert all(g["fit"] is False for g in gaps)


# ─── Knowledge-Graph entity matching ────────────────────────────────────────
def _hit(name, url="", same_as=()):
    return SimpleNamespace(name=name, url=url, same_as=list(same_as))


def test_entity_matcher_rejects_short_brand_false_positives():
    # "n-ix" must NOT match Nix / Nixie / Louis IX of France
    assert _match_entity(
        [_hit("Nix"), _hit("Nixie"), _hit("Louis IX of France")],
        _brand_info("n-ix.com"), "n-ix.com",
    ) is None
    # ...but a real entity that links back to the domain is accepted
    got = _match_entity(
        [_hit("N-iX", same_as=["https://www.n-ix.com"])],
        _brand_info("n-ix.com"), "n-ix.com",
    )
    assert got is not None and got.name == "N-iX"


def test_entity_matcher_accepts_distinctive_long_brand():
    assert _match_entity(
        [_hit("Pixelette Technologies Ltd")],
        _brand_info("pixelettetech.com"), "pixelettetech.com",
    ).name == "Pixelette Technologies Ltd"
    assert _match_entity(
        [_hit("Itransition")], _brand_info("itransition.com"), "itransition.com"
    ).name == "Itransition"
    # a short brand with no domain link stays unmatched (hp != "HP Sauce")
    assert _match_entity(
        [_hit("HP Sauce"), _hit("Hewlett-Packard")], _brand_info("hp.com"), "hp.com"
    ) is None
