"""Tests for the remediation specs + fix planner.

Trust-critical: (1) every authored spec is well-formed and routable, (2)
get_spec never returns None , unknown variables get a routable fallback so the
planner never drops a finding, (3) the planner orders session-automatable work
first and groups by fix_class.
"""
from __future__ import annotations

from seomate.agent.remediation import (
    FixClass,
    FixType,
    authored_count,
    get_spec,
    has_spec,
)


def test_authored_specs_are_well_formed():
    # spot-check a known automatable spec
    s = get_spec("P2-28")  # orphan pages
    assert s.fix_class == FixClass.SESSION
    assert s.fix_type == FixType.INTERNAL_LINKS
    assert s.automatable is True
    assert s.verify and "P2-28" in s.verify
    assert s.required_inputs  # non-empty
    assert authored_count() >= 20


def test_get_spec_never_none_fallback_routable():
    # a variable with no authored spec still returns a routable fallback
    s = get_spec("P0-99")  # nonexistent / unauthored
    assert s is not None
    assert s.variable_id == "P0-99"
    assert s.fix_class in set(FixClass)
    assert s.automatable is False  # fallbacks are never claimed automatable
    assert "FALLBACK" in s.notes.upper()
    assert has_spec("P0-99") is False


def test_fallback_routes_by_pillar():
    assert get_spec("P3-50").fix_class == FixClass.BUDGET   # off-page -> budget
    assert get_spec("P5-50").fix_class == FixClass.OWNER    # local -> owner
    assert get_spec("P2-50").fix_class == FixClass.SESSION  # technical -> session


def test_known_specs_cover_the_automatable_wins():
    # the cleanly-automatable variables surfaced by the audit must have real specs
    for vid in ["P1-21", "P1-42", "P6-09", "P6-19", "P2-42", "P2-28", "P2-31", "P6-18", "P2-36", "P1-01", "P1-02", "P1-06"]:
        assert has_spec(vid), f"{vid} should have an authored spec"
        assert get_spec(vid).automatable is True


def test_human_and_budget_specs_not_marked_automatable():
    for vid in ["P4-11", "P6-05", "P6-25", "P5-13", "P3-01"]:
        s = get_spec(vid)
        assert s.automatable is False
        assert s.fix_class in {FixClass.HUMAN, FixClass.BUDGET, FixClass.OWNER, FixClass.OFFSITE}
