"""Unit tests for the audit-brief exporter.

Builds a tiny in-memory Catalog (no taxonomy file, no network, no DB) and
checks the brief shape the Claude session relies on. Field names mirror
``seomate.taxonomy.schemas.Variable`` exactly.
"""
from __future__ import annotations

from pathlib import Path

from seomate.brief import build_brief, variable_brief
from seomate.data_contract import EvidenceWeight
from seomate.taxonomy.catalog import Catalog
from seomate.taxonomy.schemas import Dependency, Pillar, TaxonomyRule, Variable


def _catalog() -> Catalog:
    p1_20 = Variable(
        variable_id="P1-20",
        pillar="P1",
        name="Canonical present",
        evidence_weight=EvidenceWeight.CONSENSUS,
        definition="Canonical tag present on every indexable page.",
        rules=[
            TaxonomyRule(
                rule_id=1,
                title="Canonical present",
                text="Canonical tag is present on every indexable page",
            )
        ],
        data_sources=["page_html"],
        dependencies=[Dependency(target_id="P1-01", kind="depends_on")],
    )
    p1_01 = Variable(
        variable_id="P1-01",
        pillar="P1",
        name="Unique titles",
        evidence_weight=EvidenceWeight.CONSENSUS,
        definition="No two indexable pages share the same title.",
        rules=[TaxonomyRule(rule_id=1, title="No dupes", text="No duplicate titles")],
        data_sources=["page_html"],
    )
    removed = Variable(
        variable_id="P0-14",
        pillar="P0",
        name="Removed var",
        definition="Should not appear in the brief.",
        removed=True,
        removed_into="P0-13",
    )
    pillar1 = Pillar(pillar_id="P1", name="On-page", variables=[p1_20, p1_01])
    pillar0 = Pillar(pillar_id="P0", name="Strategic", variables=[removed])
    return Catalog(pillars=[pillar0, pillar1], version="test-v1", source_path=Path("x"))


def test_brief_excludes_removed_and_sorts() -> None:
    entries = variable_brief(_catalog())
    ids = [e["variable_id"] for e in entries]
    assert ids == ["P1-01", "P1-20"]  # sorted, removed P0-14 excluded


def test_brief_entry_shape() -> None:
    entries = {e["variable_id"]: e for e in variable_brief(_catalog())}
    p20 = entries["P1-20"]
    assert p20["pillar"] == "P1"
    assert p20["name"] == "Canonical present"
    assert p20["definition"].startswith("Canonical tag")
    assert p20["evidence_weight"] == "Consensus"
    assert p20["data_sources"] == ["page_html"]
    assert p20["rules"] == [
        {
            "rule_id": 1,
            "title": "Canonical present",
            "text": "Canonical tag is present on every indexable page",
        }
    ]
    assert p20["hard_dependencies"] == ["P1-01"]


def test_build_brief_top_level() -> None:
    brief = build_brief(_catalog())
    assert brief["taxonomy_version"] == "test-v1"
    assert brief["variable_count"] == 2
    assert brief["pillars"] == {"P1": 2}
    assert brief["data_sources"] == ["page_html"]
    assert len(brief["variables"]) == 2
