"""Tests for Model B evidence-weight gating in the fix planner.

The planner read ``evidence_weight`` off each capture and then dropped it, so
every failing Speculative variable was presented as actionable work the evidence
does not support. The taxonomy's Operational Mapping is explicit that weight
gates what the system may DO with a variable:

    Consensus   trusted scoring input, standard approval ladder
    Probable    same ladder, flagged for outcome tracking
    Contested   surfaced as recommendations, never auto-approved without human
                sign-off
    Speculative watchlist hypothesis, does not drive recommendation generation

Contested is deliberately NOT treated like Speculative: it stays actionable.
These tests pin both halves down, plus the fail-open behaviour for unknown
weights (hiding real work is the worse error).
"""
from __future__ import annotations

from seomate.agent.plan import (
    is_watchlist_only,
    partition_by_evidence_weight,
    requires_human_signoff,
)
from seomate.data_contract import EvidenceWeight

CONSENSUS = EvidenceWeight.CONSENSUS.value
PROBABLE = EvidenceWeight.PROBABLE.value
CONTESTED = EvidenceWeight.CONTESTED.value
SPECULATIVE = EvidenceWeight.SPECULATIVE.value


def _order(vid: str, weight: str | None, automatable: bool = False) -> dict:
    return {
        "variable_id": vid,
        "evidence_weight": weight,
        "requires_human_signoff": requires_human_signoff(weight),
        "remediation": {"automatable": automatable},
    }


# ── Speculative: watchlist, not work ──────────────────────────────────────────


def test_speculative_is_watchlist_only() -> None:
    assert is_watchlist_only(SPECULATIVE) is True


def test_non_speculative_weights_stay_actionable() -> None:
    for w in (CONSENSUS, PROBABLE, CONTESTED):
        assert is_watchlist_only(w) is False, f"{w} must remain actionable"


def test_unknown_or_missing_weight_fails_open_to_actionable() -> None:
    """Hiding real work is worse than surfacing an unweighted finding."""
    assert is_watchlist_only(None) is False
    assert is_watchlist_only("") is False
    assert is_watchlist_only("Nonsense") is False


def test_partition_moves_speculative_out_of_actionable() -> None:
    orders = [
        _order("P1-01", CONSENSUS),
        _order("P1-04", SPECULATIVE),   # the real case: failing + Speculative
        _order("P4-13", SPECULATIVE),   # the other currently-failing one
        _order("P1-05", PROBABLE),
    ]
    actionable, watchlist = partition_by_evidence_weight(orders)
    assert [w["variable_id"] for w in actionable] == ["P1-01", "P1-05"]
    assert [w["variable_id"] for w in watchlist] == ["P1-04", "P4-13"]


def test_partition_loses_nothing() -> None:
    """Speculative findings are segregated, never dropped."""
    orders = [
        _order("P1-04", SPECULATIVE),
        _order("P2-42", SPECULATIVE),
        _order("P6-18", SPECULATIVE),
        _order("P1-03", CONSENSUS),
        _order("P1-02", CONTESTED),
    ]
    actionable, watchlist = partition_by_evidence_weight(orders)
    assert len(actionable) + len(watchlist) == len(orders)
    recovered = {w["variable_id"] for w in actionable} | {w["variable_id"] for w in watchlist}
    assert recovered == {"P1-04", "P2-42", "P6-18", "P1-03", "P1-02"}


def test_partition_preserves_sort_order() -> None:
    orders = [_order(v, CONSENSUS) for v in ("A", "B", "C")]
    orders.insert(2, _order("SPEC", SPECULATIVE))
    actionable, _ = partition_by_evidence_weight(orders)
    assert [w["variable_id"] for w in actionable] == ["A", "B", "C"]


# ── Contested: actionable, but never auto-approved ────────────────────────────


def test_contested_requires_signoff() -> None:
    assert requires_human_signoff(CONTESTED) is True


def test_contested_is_not_treated_like_speculative() -> None:
    """The taxonomy gives them different treatment; the code must too.

    Contested is "surfaced as recommendations ... never auto-approved", so it
    must stay in the actionable set rather than moving to the watchlist.
    """
    actionable, watchlist = partition_by_evidence_weight([_order("P1-02", CONTESTED)])
    assert [w["variable_id"] for w in actionable] == ["P1-02"]
    assert watchlist == []


def test_other_weights_do_not_require_signoff() -> None:
    for w in (CONSENSUS, PROBABLE, SPECULATIVE, None, "Nonsense"):
        assert requires_human_signoff(w) is False


def test_contested_is_held_out_of_the_auto_ship_list() -> None:
    """An automatable Contested spec must not land in session_automatable.

    P1-02 (title length) is Contested and its spec is marked automatable, so
    without this the planner would auto-ship a change the taxonomy says needs a
    human to approve.
    """
    orders = [
        _order("P1-01", CONSENSUS, automatable=True),
        _order("P1-02", CONTESTED, automatable=True),
    ]
    actionable, _ = partition_by_evidence_weight(orders)
    auto = [
        w["variable_id"]
        for w in actionable
        if w["remediation"]["automatable"] and not w["requires_human_signoff"]
    ]
    assert auto == ["P1-01"]
    assert "P1-02" not in auto


# ── the concrete audit cases ──────────────────────────────────────────────────


def test_the_two_failing_speculative_variables_are_not_work() -> None:
    """P1-04 and P4-13 were both presented as actionable work in audit 400a5d4a.

    P1-04 additionally showed up as one of the six 07-20 -> 07-22 'regressions',
    which was doubly meaningless: noise on a variable that should not be scored.
    """
    for vid in ("P1-04", "P4-13"):
        actionable, watchlist = partition_by_evidence_weight([_order(vid, SPECULATIVE)])
        assert actionable == []
        assert [w["variable_id"] for w in watchlist] == [vid]


def test_all_seven_contested_variables_remain_actionable() -> None:
    contested = ["P1-02", "P1-08", "P1-09", "P1-12", "P1-16", "P1-27", "P3-06"]
    actionable, watchlist = partition_by_evidence_weight(
        [_order(v, CONTESTED) for v in contested]
    )
    assert [w["variable_id"] for w in actionable] == contested
    assert watchlist == []
    assert all(w["requires_human_signoff"] for w in actionable)
