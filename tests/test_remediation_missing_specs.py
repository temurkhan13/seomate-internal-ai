"""Tests for the 8 previously-unspecced variables in the remediation module.

Before this batch, P1-04 / P1-14 / P1-35 / P2-13 / P4-02 / P6-14 / P6-21 / P6-24
had no authored spec, so ``get_spec`` fell through to the generic pillar
fallback. That fallback is not merely vague: it types every variable CONTENT and
routes by pillar alone, which mis-routed three of these eight. The fix plan was
therefore weaker than its finding count implied.

These tests pin down (1) that all eight are now authored, (2) that each carries a
verify condition keyed to the variable, (3) the three routing corrections against
what the fallback would have said, and (4) that the run-to-run caution required
for source-dependent variables is actually recorded on the specs that need it.
"""
from __future__ import annotations

import pytest

from seomate.agent.remediation import (
    FixClass,
    FixType,
    authored_count,
    get_spec,
    has_spec,
)

# The 8 variables this batch authored.
NEWLY_SPECCED = [
    "P1-04", "P1-14", "P1-35", "P2-13", "P4-02", "P6-14", "P6-21", "P6-24",
]

# Variables whose pass depends on DataForSEO / CrUX / PSI-lab / SERP-proxy data.
# These move run-to-run on their own, so a single re-audit flip is not proof.
SOURCE_DEPENDENT = ["P1-04", "P1-14", "P1-35", "P2-13", "P6-14", "P6-24"]

# The two that are deterministic: a clean re-audit is sufficient evidence.
DETERMINISTIC = ["P4-02", "P6-21"]


@pytest.mark.parametrize("vid", NEWLY_SPECCED)
def test_all_eight_are_authored_not_fallback(vid: str) -> None:
    """Each of the 8 has a real spec, not the generic 'manual triage' fallback."""
    assert has_spec(vid), f"{vid} should have an authored spec"
    s = get_spec(vid)
    # Match the marker the generic fallback actually emits, not any mention of
    # the word: three of these specs legitimately explain that the pillar
    # fallback mis-routed them.
    assert "GENERIC FALLBACK" not in s.notes.upper()
    assert "manual triage" not in s.target
    assert "manual triage" not in s.required_inputs


@pytest.mark.parametrize("vid", NEWLY_SPECCED)
def test_specs_are_well_formed(vid: str) -> None:
    """Every spec is routable and carries an actionable, verifiable work order."""
    s = get_spec(vid)
    assert s.variable_id == vid
    assert s.fix_class in set(FixClass)
    assert s.fix_type in set(FixType)
    assert s.target.strip()
    assert vid in s.verify, "verify must name the variable it re-checks"
    assert len(s.concrete_change) > 200, "concrete_change must be specific, not hand-waving"
    assert s.required_inputs, "a spec with no required inputs is not actionable"
    assert s.risk in {"low", "medium", "high"}
    assert s.effort in {"one-shot", "ongoing", "campaign"}
    assert s.notes.strip()


@pytest.mark.parametrize("vid", NEWLY_SPECCED)
def test_none_claim_unattended_automation(vid: str) -> None:
    """None of these 8 is automatable end-to-end unattended.

    Each needs either editorial sign-off, a business owner's approval, real
    recorded media, or third-party placements. Claiming otherwise would put
    unreviewed content on a commercial site.
    """
    assert get_spec(vid).automatable is False


def test_automatable_implies_session_across_the_module() -> None:
    """Consistency invariant: only a SESSION fix can be unattended-automatable."""
    for vid in NEWLY_SPECCED:
        s = get_spec(vid)
        if s.automatable:
            assert s.fix_class == FixClass.SESSION


def test_routing_corrections_against_the_pillar_fallback() -> None:
    """The three variables the generic pillar fallback mis-routed.

    Fallback routes P1 -> SESSION, P4/P6 -> HUMAN. Authored from the actual rule
    implementations, these three land elsewhere.
    """
    # P1-35 needs real business substance a session cannot invent: not SESSION.
    assert get_spec("P1-35").fix_class == FixClass.HUMAN
    # P6-21 is mechanical section-length work on article pages: a session can do it.
    assert get_spec("P6-21").fix_class == FixClass.SESSION
    # P6-24 is third-party citation acquisition: neither session nor in-house human.
    assert get_spec("P6-24").fix_class == FixClass.OFFSITE


def test_fix_types_are_specific_not_the_content_default() -> None:
    """The fallback types everything CONTENT; real specs discriminate."""
    assert get_spec("P1-04").fix_type == FixType.METADATA
    assert get_spec("P2-13").fix_type == FixType.CONFIG
    assert get_spec("P6-14").fix_type == FixType.MEDIA
    assert get_spec("P6-24").fix_type == FixType.OFFSITE


@pytest.mark.parametrize("vid", SOURCE_DEPENDENT)
def test_source_dependent_specs_require_two_consistent_runs(vid: str) -> None:
    """Guardrail: never close a source-dependent finding on one re-audit flip.

    These variables move on their own between runs, so the spec must tell the
    fixing session to close on the evidence of the change plus >=2 consistent
    runs.
    """
    notes = get_spec(vid).notes
    assert ">=2 consistent runs" in notes, f"{vid} must carry the two-run caution"


@pytest.mark.parametrize("vid", DETERMINISTIC)
def test_deterministic_specs_say_so(vid: str) -> None:
    """The two non-source-dependent specs record that a clean run is enough."""
    notes = get_spec(vid).notes.lower()
    assert "deterministic" in notes
    assert ">=2 consistent runs" not in get_spec(vid).notes


def test_verify_strings_carry_the_real_thresholds() -> None:
    """verify must key off the rule implementation's actual numbers."""
    assert "coverage_pct >= 50" in get_spec("P1-04").verify
    assert "avg_overlap_tokens_per_page >= 1.0" in get_spec("P1-14").verify
    assert "dominated_pct <= 10" in get_spec("P1-35").verify
    assert "kw_prominence_pct >= 70" in get_spec("P1-35").verify
    assert "200 ms" in get_spec("P2-13").verify
    assert "median_age_days <= 365" in get_spec("P4-02").verify
    assert "100 and 800 words" in get_spec("P6-21").verify
    assert "15.0%" in get_spec("P6-24").verify


def test_p4_02_forbids_date_gaming() -> None:
    """P4-02 can be trivially faked by bumping dateModified with no content change.

    The spec must say not to, or it is an instruction to game the metric.
    """
    notes = get_spec("P4-02").notes.lower()
    assert "never bump" in notes or "date-gaming" in notes


@pytest.mark.parametrize("vid", NEWLY_SPECCED)
def test_depends_on_entries_are_well_formed(vid: str) -> None:
    """Dependencies must be real-looking variable ids so the planner can order work."""
    for dep in get_spec(vid).depends_on:
        assert len(dep) == 5 and dep[0] == "P" and dep[2] == "-", f"{vid}: bad dep {dep!r}"
        assert dep != vid, f"{vid} must not depend on itself"


def test_authored_count_grew_by_this_batch() -> None:
    """Guards against a spec being dropped in a future edit."""
    assert authored_count() >= 28
