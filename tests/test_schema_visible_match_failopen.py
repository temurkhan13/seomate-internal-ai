"""Regression guard: the LLM-backed schema-visible-match rule must never
manufacture a PASS out of missing evidence.

P1-22 rule 7 and P6-19 rule 8 are the only two rules in the platform whose
verdict comes from a live LLM call (``anthropic_llm_per_page_evaluation``).
Both used to return ``passed=True`` whenever the LLM layer produced nothing,
which meant an Anthropic outage, a zero credit balance, or a per-page evaluator
error made the site score BETTER. That is a fail-open, and it is the same class
of defect as the May-2026 PSI incident where a failing mobile leg produced
fake ``passed`` verdicts.

Observed in production: ``/custom-software-development-services`` was judged
FAILING on 2026-07-20 and merely ERRORED on 2026-07-22. The errored page was
silently dropped, ``pages_failed`` went 1 -> 0, and both variables flipped to
passed with no site change at all.

The invariant these tests defend:
  * a failure is provable from partial data      -> FAILED is allowed
  * the ABSENCE of failures is NOT provable from partial data
                                                 -> never PASSED, use PARTIAL
"""
from __future__ import annotations

from dataclasses import dataclass

from seomate.data_contract import CaptureStatus
from seomate.pillars.p1_schema import _schema_visible_match_rule
from seomate.pillars.p6_geo import _p6_19_schema_visible_match_rule


@dataclass
class _Eval:
    """Minimal stand-in for utils.llm_evaluation.LlmEvaluation."""

    passed: bool | None = True
    error: str | None = None
    confidence: float = 0.9
    issues: tuple[str, ...] = ()
    rationale: str = ""


class _Site:
    """Only ``llm_evaluations`` is read by the two rules under test."""

    def __init__(self, evals: dict | None) -> None:
        self.llm_evaluations = {"schema_visible_match": evals} if evals is not None else {}


_RULES = (_schema_visible_match_rule, _p6_19_schema_visible_match_rule)


# ─── the fail-open itself ───────────────────────────────────────────────────
def test_missing_llm_layer_is_not_conclusive():
    """No LLM evaluations at all must not count as a pass."""
    for rule_fn in _RULES:
        rule = rule_fn(_Site(None))
        assert rule.evidence["conclusive"] is False, (
            f"{rule_fn.__name__}: an absent LLM layer must be inconclusive, "
            "otherwise an outage silently scores the site as passing"
        )
        assert rule.evidence["method"] == "deferred_until_anthropic_key_set"


def test_clean_sheet_with_errored_pages_is_not_conclusive():
    """The exact production flip: zero failures but a page returned no verdict.

    An errored page might have been the failing one, so 'no failures' is
    unproven and must not be reported as a conclusive pass.
    """
    evals = {
        "https://ex.com/a": _Eval(passed=True),
        "https://ex.com/b": _Eval(passed=None, error="evaluator returned no row"),
    }
    for rule_fn in _RULES:
        rule = rule_fn(_Site(evals))
        assert rule.passed is True, "no failing page was found, so the rule itself passes"
        assert rule.evidence["conclusive"] is False, (
            f"{rule_fn.__name__}: a clean sheet with an errored page must be "
            "inconclusive; this is the 2026-07-22 false 'schema improvement'"
        )
        assert rule.evidence["pages_errored"] == 1


# ─── the cases that must keep working ───────────────────────────────────────
def test_full_clean_sheet_is_conclusive_pass():
    evals = {
        "https://ex.com/a": _Eval(passed=True),
        "https://ex.com/b": _Eval(passed=True),
    }
    for rule_fn in _RULES:
        rule = rule_fn(_Site(evals))
        assert rule.passed is True
        assert rule.evidence["conclusive"] is True
        assert rule.evidence["coverage_pct"] == 100.0


def test_failure_is_conclusive_even_with_gaps():
    """A proven failure stands regardless of coverage. Do not soften it."""
    evals = {
        "https://ex.com/a": _Eval(passed=False, issues=("schema claims X, page lacks X",)),
        "https://ex.com/b": _Eval(passed=None, error="evaluator returned no row"),
    }
    for rule_fn in _RULES:
        rule = rule_fn(_Site(evals))
        assert rule.passed is False
        assert rule.evidence["conclusive"] is True, (
            f"{rule_fn.__name__}: a failure is provable from partial data and "
            "must not be downgraded to inconclusive"
        )


# ─── end-to-end: the capture status, which is what the audit records ────────
def _p1_22_status(evals):
    from seomate.pillars import p1_schema

    rule = p1_schema._schema_visible_match_rule(_Site(evals))
    conclusive = bool(rule.evidence.get("conclusive", True))
    # Mirror the extractor's verdict logic: deterministic rules all pass here.
    overall_pass = True and (rule.passed if conclusive else True)
    return (
        (CaptureStatus.PASSED if conclusive else CaptureStatus.PARTIAL)
        if overall_pass
        else CaptureStatus.FAILED
    )


def test_capture_degrades_to_partial_not_passed():
    """With every deterministic rule passing, an unevaluated LLM rule must
    yield PARTIAL. PASSED here is the bug."""
    assert _p1_22_status(None) is CaptureStatus.PARTIAL
    assert (
        _p1_22_status(
            {
                "https://ex.com/a": _Eval(passed=True),
                "https://ex.com/b": _Eval(passed=None, error="no row"),
            }
        )
        is CaptureStatus.PARTIAL
    )
    # ...and a genuinely complete clean sheet still passes.
    assert (
        _p1_22_status({"https://ex.com/a": _Eval(passed=True)}) is CaptureStatus.PASSED
    )
