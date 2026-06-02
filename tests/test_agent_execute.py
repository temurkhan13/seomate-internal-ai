"""Tests for the Phase 2 executor (propose-mode artifact generation).

Trust-critical: (1) generators build real artifacts from a cache, (2) the
executor never writes to a target (propose mode only), (3) unknown variables
route to manual, not a fabricated fix, (4) the two bugs caught on real data stay
fixed , no orphan self-links, and llms.txt uses a real description.
"""
from __future__ import annotations

import json
from pathlib import Path

from seomate.agent.execute import (
    _clean_label,
    _is_key_page,
    _valid_pages,
    addresses_a_failing_rule,
    build_apply_manifest,
    can_generate,
    execute_work_order,
)

CRAWL = {
    "base": "https://abcd.com",
    "page_count": 4,
    "pages": [
        {"url": "https://abcd.com/", "title": "ABCD | Home", "meta_description": "ABCD builds AI things.", "h1": ["ABCD"], "jsonld_types": [], "internal_links": ["https://abcd.com/services"]},
        {"url": "https://abcd.com/services", "title": "Services", "h1": ["Services"], "jsonld_types": [], "internal_links": ["https://abcd.com/"]},
        {"url": "https://abcd.com/blog", "title": "Blog", "h1": ["Blog"], "jsonld_types": [], "internal_links": []},
        {"url": "https://abcd.com/blog/post-one", "title": "Post One", "h1": ["Post One"], "jsonld_types": [], "internal_links": []},
    ],
}
ENTITY = {"brand": "ABCD", "kg": {"itemListElement": [{"result": {"name": "ABCD Ltd", "description": "Co"}}]}}
DFS = {"my_business_info": {"tasks": [{"result": [{"items": [{"title": "ABCD", "address": "1 St, London", "phone": "+44123"}]}]}]}}


def _cache(tmp_path: Path) -> Path:
    (tmp_path / "crawl.json").write_text(json.dumps(CRAWL))
    (tmp_path / "entity.json").write_text(json.dumps(ENTITY))
    (tmp_path / "dataforseo.json").write_text(json.dumps(DFS))
    return tmp_path


def test_can_generate_covers_automatable():
    for vid in ["P6-18", "P2-42", "P6-19", "P1-42", "P1-21", "P2-28", "P1-24"]:
        assert can_generate(vid)
    assert not can_generate("P4-11")  # human content, no generator


def test_llms_txt_uses_real_description(tmp_path: Path):
    res = execute_work_order("P6-18", _cache(tmp_path), "abcd.com")
    assert res["generated"] is True
    assert res["mode"] == "propose"
    # uses the homepage meta description, not the weak KG "Co"
    assert "ABCD builds AI things." in res["content"]
    assert "Co\n" not in res["content"]


def test_org_schema_has_real_nap(tmp_path: Path):
    res = execute_work_order("P6-19", _cache(tmp_path), "abcd.com")
    assert res["generated"] is True
    assert "ABCD Ltd" in res["content"]
    assert "1 St, London" in res["content"]
    assert "application/ld+json" in res["content"]


def test_orphan_plan_no_self_links(tmp_path: Path):
    res = execute_work_order("P2-28", _cache(tmp_path), "abcd.com")
    assert res["generated"] is True
    plan = res["content"]["link_plan"]
    # /blog and /blog/post-one are orphaned (0 inbound); none may link from itself
    for entry in plan:
        assert entry["orphan"] not in entry["add_links_from"], f"self-link for {entry['orphan']}"


def test_valid_pages_drops_errors_and_non_200():
    crawl = {"pages": [
        {"url": "https://x.com/a", "http_status": 200},
        {"url": "https://x.com/b", "http_status": 404},
        {"url": "https://x.com/c", "error": "timeout"},
        {"url": "https://x.com/d"},  # no status -> kept (crawl didn't record one)
        {"http_status": 200},        # no url -> dropped
    ]}
    urls = [p["url"] for p in _valid_pages(crawl)]
    assert urls == ["https://x.com/a", "https://x.com/d"]


def test_is_key_page_excludes_blog_and_vanity():
    assert _is_key_page({"url": "https://x.com/ai-development-services"}) is True
    assert _is_key_page({"url": "https://x.com/blog/some-post"}) is False
    assert _is_key_page({"url": "https://x.com/clutch"}) is False        # vanity
    assert _is_key_page({"url": "https://x.com/privacy-policy"}) is False


def test_clean_label_strips_marketing_never_returns_raw_path():
    # marketing-stuffed title -> humanized slug, NOT the raw path
    out = _clean_label("Top AI Development Company 2024 \U0001F947 on Clutch", "https://x.com/ai-development-services")
    assert out == "Ai Development Services"
    assert not out.startswith("/")
    # clean title passes through
    assert _clean_label("Custom Software Development", "https://x.com/c") == "Custom Software Development"
    # empty title -> humanized slug
    assert _clean_label("", "https://x.com/web-development-services") == "Web Development Services"


def test_llms_txt_curated_no_vanity_no_broken(tmp_path: Path):
    crawl = {"base": "https://abcd.com", "pages": [
        {"url": "https://abcd.com/", "title": "ABCD | Home", "meta_description": "We build AI.", "http_status": 200},
        {"url": "https://abcd.com/ai-services", "title": "Top AI Company 2024 \U0001F947 on Clutch", "http_status": 200},
        {"url": "https://abcd.com/clutch", "title": "Clutch", "http_status": 200},   # vanity -> excluded
        {"url": "https://abcd.com/blog/post", "title": "Post", "http_status": 200},  # blog -> excluded
        {"url": "https://abcd.com/dead", "title": "Dead", "http_status": 404},        # non-200 -> excluded
    ]}
    (tmp_path / "crawl.json").write_text(json.dumps(crawl))
    (tmp_path / "entity.json").write_text(json.dumps({"kg": {"itemListElement": []}}))
    res = execute_work_order("P6-18", tmp_path, "abcd.com")
    body = res["content"]
    assert "/clutch" not in body          # vanity filtered
    assert "/blog/post" not in body       # blog filtered
    assert "/dead" not in body            # non-200 filtered
    assert "on Clutch" not in body        # marketing label cleaned
    assert "[Ai Services]" in body        # humanized fallback label
    assert "We build AI." in body         # real description


def test_unknown_variable_routes_to_manual_not_fabricated(tmp_path: Path):
    res = execute_work_order("P4-11", _cache(tmp_path), "abcd.com")  # human content
    assert res["generated"] is False
    assert res["mode"] == "propose"
    assert "concrete_change" in res  # still routed with the spec, not a fake artifact


def test_build_apply_manifest_is_propose_only(tmp_path: Path):
    plan = {
        "site_domain": "abcd.com",
        "audit_id": "x",
        "work_orders": [
            {"variable_id": "P6-18", "remediation": {"automatable": True, "fix_class": "session", "concrete_change": "...", "required_inputs": [], "verify": "..."}},
            {"variable_id": "P4-11", "remediation": {"automatable": False, "fix_class": "human", "concrete_change": "...", "required_inputs": [], "verify": "..."}},
        ],
    }
    manifest = build_apply_manifest(plan, _cache(tmp_path))
    assert manifest["mode"] == "propose"
    assert manifest["artifacts_generated"] == 1   # P6-18 generated
    assert manifest["manual_work_orders"] == 1     # P4-11 routed manual
    assert "NOT written to the target site" in manifest["note"]


def test_addresses_a_failing_rule_gates_by_keyword():
    # P6-19's generator makes Organization schema; it must NOT fire when the only
    # failing rule is BreadcrumbList (the real-data remediation-spec mismatch).
    assert addresses_a_failing_rule("P6-19", ["BreadcrumbList present on every non-homepage URL"]) is False
    assert addresses_a_failing_rule("P6-19", ["Organization (or Person) schema present on every page"]) is True
    # P1-42's Article generator must not fire on a date-only failure.
    assert addresses_a_failing_rule("P1-42", ["Site provides syntactic date on at least 50% of pages"]) is False
    # Back-compat: no keyword map, or no per-rule detail -> never blocks.
    assert addresses_a_failing_rule("P9-99", ["anything"]) is True
    assert addresses_a_failing_rule("P6-19", []) is True


def test_build_apply_manifest_skips_artifact_that_misses_failing_rule(tmp_path: Path):
    # The core platform fix: a generator keyed by variable_id must not emit an
    # artifact for a rule that already passes.
    plan = {
        "site_domain": "abcd.com",
        "audit_id": "x",
        "work_orders": [
            # P6-19 fails ONLY on BreadcrumbList -> Organization artifact suppressed
            {"variable_id": "P6-19",
             "failing_rules": ["BreadcrumbList present on every non-homepage URL"],
             "remediation": {"automatable": True, "fix_class": "session", "concrete_change": "...", "required_inputs": [], "verify": "re-audit P6-19"}},
            # P2-28 fails on orphan/inbound -> orphan-link plan DOES address it
            {"variable_id": "P2-28",
             "failing_rules": ["No page in the audited URL set has zero inbound internal links"],
             "remediation": {"automatable": True, "fix_class": "session", "concrete_change": "...", "required_inputs": [], "verify": "re-audit P2-28"}},
        ],
    }
    manifest = build_apply_manifest(plan, _cache(tmp_path))
    gen_ids = {a["variable_id"] for a in manifest["generated"]}
    man_ids = {a["variable_id"] for a in manifest["manual"]}
    assert "P2-28" in gen_ids                 # matches a failing rule -> generated
    assert "P6-19" not in gen_ids             # mismatch -> NOT generated
    assert "P6-19" in man_ids                 # routed to manual instead
    p619 = next(a for a in manifest["manual"] if a["variable_id"] == "P6-19")
    assert "BreadcrumbList" in p619["failing_rules"][0]
    assert "does not address" in p619.get("reason", "")
