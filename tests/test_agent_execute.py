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
