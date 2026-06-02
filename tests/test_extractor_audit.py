"""Regression safety net over the 226 pillar extractors.

The per-extractor logic audit (June 2026) that found the 8 correctness bugs was
a one-time manual+agent pass. These tests make its guarantees permanent:

1. the systemic www-strip bug can never come back,
2. the registry stays fully wired (right count, no orphans, supplyable adapters),
3. every extractor still runs to a valid CaptureRecord on minimal input (catches
   crashes / invalid-status regressions across all 226).
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from uuid import uuid4

import pytest

import seomate
import seomate.pillars  # noqa: F401 - import populates EXTRACTOR_REGISTRY
from seomate.adapters import AdapterContext
from seomate.brief import LLM_JUDGMENT_VARIABLES, build_brief
from seomate.data_contract import CaptureRecord, CaptureStatus
from seomate.pillars import BrandIdentity, PageAudit, SiteData
from seomate.pillars._base import EXTRACTOR_REGISTRY
from seomate.taxonomy import Catalog
from seomate.utils.cost_tracker import CostTracker

ORCH_ADAPTERS = {"dataforseo", "kg", "wikipedia", "wikidata", "embeddings", "psi", "llm", "gsc"}
# Active catalog vars intentionally without an extractor (retired Google-leak /
# human-rated signals nobody can measure externally).
RETIRED_NO_EXTRACTOR = {"P2-06", "P3-11", "P3-13", "P3-16", "P4-18", "P6-15"}


# ── 1. Systemic-bug guard: the www-strip bug must never return ──────────────
def test_no_lstrip_www_anywhere():
    """`.lstrip("www.")` strips the char-SET {w,.}, not the prefix (wsj.com ->
    sj.com). It was fixed across 32 sites; this stops it ever reappearing."""
    root = Path(seomate.__file__).parent
    offenders = []
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if '.lstrip("www' in text or ".lstrip('www" in text:
            offenders.append(str(f.relative_to(root)))
    assert not offenders, (
        "lstrip('www.') is a character-set strip bug; use .removeprefix('www.'). "
        f"Offenders: {offenders}"
    )


# ── 2. Registry integrity (codifies the wiring audit) ───────────────────────
def test_registry_matches_active_catalog():
    cat = Catalog.from_file()
    active = {v.variable_id for v in cat.all_variables(include_removed=False)}
    reg = set(EXTRACTOR_REGISTRY)
    # Every active variable has an extractor, and no extractor is registered for a
    # non-active (removed) variable. The 6 retired Google-leak/human-rated signals
    # are flagged removed (PR #12), so they are not in `active`.
    assert not (reg - active), f"orphan extractors (non-active vars): {sorted(reg - active)}"
    assert not (active - reg), f"active vars missing an extractor: {sorted(active - reg)}"
    assert len(active) == 226
    assert len(reg) == 226
    removed = {v.variable_id for v in cat.removed_variables()}
    assert RETIRED_NO_EXTRACTOR <= removed, (
        f"retired vars not flagged removed: {sorted(RETIRED_NO_EXTRACTOR - removed)}"
    )


def test_every_extractor_adapter_param_is_supplyable():
    bad = {}
    for vid, fn in EXTRACTOR_REGISTRY.items():
        extra = set(inspect.signature(fn).parameters) - ORCH_ADAPTERS - {"ctx", "site"}
        if extra:
            bad[vid] = sorted(extra)
    assert not bad, f"extractors declare params the orchestrator can't supply: {bad}"


# ── 3. Smoke test: every extractor runs to a valid CaptureRecord ────────────
def _ctx() -> AdapterContext:
    return AdapterContext(
        audit_id=uuid4(),
        cost_tracker=CostTracker(cap_gbp=5.0, warn_fraction=0.8),
        taxonomy_version="test",
    )


def _page(url: str, **ov) -> PageAudit:
    base = dict(
        url=url, status_code=200, is_redirect=False, is_indexable=True,
        title="Title", title_length=40, has_multiple_titles=False,
        description="A description.", description_length=150,
        h1=("Heading",), h2=("Sub",), h3=(), h4=(), h5=(), h6=(),
        canonical=url, meta_robots=None,
    )
    base.update(ov)
    return PageAudit(**base)


def _site() -> SiteData:
    pages = {
        "https://ex.com/": _page("https://ex.com/"),
        "https://ex.com/a": _page("https://ex.com/a"),
    }
    return SiteData(
        domain="ex.com", primary_url="https://ex.com/", urls=list(pages),
        page_audits=pages, brand=BrandIdentity(name="Ex"),
    )


class _StubDFS:
    """DataForSEO: methods return the task/result envelope shape, empty."""

    is_configured = False

    def __getattr__(self, name):
        async def _call(*a, **k):
            return {"tasks": [{"result": []}]}
        return _call


class _StubList:
    """KG / Wikipedia / Wikidata: search-style methods return empty lists, so
    extractors see "no results" and degrade to unmeasurable (no network)."""

    is_configured = False

    def __getattr__(self, name):
        async def _call(*a, **k):
            return []
        return _call


class _StubOff:
    """Embeddings / PSI / LLM: extractors read the prefetched SiteData cache;
    the adapter is passed but unused, so just present an unconfigured stub."""

    is_configured = False

    def __getattr__(self, name):
        async def _call(*a, **k):
            return None
        return _call


class _StubGSC:
    """GSC: report unconfigured so the GSC-backed extractors (P2-03/P2-04)
    short-circuit to UNMEASURABLE without any network. Unlike the other stubs
    these extractors *call* ``is_configured()``, so it must be a method."""

    def is_configured(self):
        return False

    def __getattr__(self, name):
        async def _call(*a, **k):
            return {}
        return _call


_STUBS = {
    "dataforseo": _StubDFS, "kg": _StubList, "wikipedia": _StubList,
    "wikidata": _StubList, "embeddings": _StubOff, "psi": _StubOff, "llm": _StubOff,
    "gsc": _StubGSC,
}


# ── 4. Hybrid LLM-eval path (session evaluates the 19 judgment vars) ────────
def test_llm_judgment_vars_are_real_and_llm_dependent():
    """Every var in LLM_JUDGMENT_VARIABLES exists, has an extractor, and that
    extractor genuinely reads site.llm_evaluations (so it's an LLM-judgment var,
    not an arbitrary id). Guards the constant from drifting out of sync."""
    cat = Catalog.from_file()
    active = {v.variable_id for v in cat.all_variables(include_removed=False)}
    for vid in LLM_JUDGMENT_VARIABLES:
        assert vid in active, f"{vid} in LLM_JUDGMENT_VARIABLES is not an active var"
        fn = EXTRACTOR_REGISTRY.get(vid)
        assert fn is not None, f"{vid} has no registered extractor"
        assert "llm_evaluations" in inspect.getsource(fn), (
            f"{vid} is in LLM_JUDGMENT_VARIABLES but its extractor doesn't read "
            "site.llm_evaluations (not actually LLM-dependent)"
        )


def test_scoped_brief_returns_only_llm_vars():
    cat = Catalog.from_file()
    brief = build_brief(cat, only=LLM_JUDGMENT_VARIABLES)
    ids = {v["variable_id"] for v in brief["variables"]}
    assert ids == set(LLM_JUDGMENT_VARIABLES)
    assert brief["variable_count"] == len(LLM_JUDGMENT_VARIABLES)
    # each scoped entry carries the rubric the session needs
    for v in brief["variables"]:
        assert "rules" in v and "definition" in v


# ── 5. Smoke test: every extractor runs to a valid CaptureRecord ────────────
@pytest.mark.parametrize("vid", sorted(EXTRACTOR_REGISTRY))
def test_extractor_runs_to_valid_capture(vid: str):
    fn = EXTRACTOR_REGISTRY[vid]
    params = set(inspect.signature(fn).parameters)
    adapters = {a: _STUBS[a]() for a in ORCH_ADAPTERS if a in params}
    rec = asyncio.run(fn(_ctx(), _site(), **adapters))
    assert isinstance(rec, CaptureRecord), f"{vid} did not return a CaptureRecord"
    assert rec.variable_id == vid
    assert isinstance(rec.status, CaptureStatus)
