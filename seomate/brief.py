"""Export the taxonomy as an audit *brief* for a Claude session.

In the agent-driven model the Claude session is the auditor: it reads
SEOMATE's understanding of the 226 variables and performs the diagnostic
itself. This module turns the parsed taxonomy (``Catalog``) into a single
machine-readable JSON document, the *brief*, that is the session's
instruction set: per variable, what it is, which data sources answer it,
and the Step 1.5 rules that decide pass/fail.

The brief is the input side of the boundary; ``ingest.py`` is the output
side. A session reads the brief, gathers data, evaluates each variable,
and emits an ingest document (see ``docs/ingest-contract.md``).

This is a pure transform over the ``Catalog`` (no network, no DB). Field
names mirror ``seomate.taxonomy.schemas.Variable`` exactly. ``seomate
export-brief`` writes the result to disk.
"""
from __future__ import annotations

from collections.abc import Collection
from typing import Any

from seomate.taxonomy import Catalog

# The LLM-judgment variables: those whose verdict genuinely needs an LLM (they
# read site.llm_evaluations). In the native run these go via the Anthropic API;
# in the session-driven hybrid a Claude session evaluates them for free against
# each variable's rubric and merge-ingests the verdicts. Keep this in sync with
# the extractors that read site.llm_evaluations (a test enforces it).
LLM_JUDGMENT_VARIABLES = frozenset({
    "P0-17", "P1-37",
    "P4-07", "P4-09", "P4-11", "P4-17", "P4-21", "P4-22", "P4-23",
    "P6-02", "P6-05", "P6-07", "P6-10", "P6-12", "P6-22", "P6-23",
    "P6-27", "P6-28", "P6-31",
})


def variable_brief(
    catalog: Catalog, *, only: Collection[str] | None = None
) -> list[dict[str, Any]]:
    """Return one brief entry per active (non-removed) variable.

    Each entry carries everything the session needs to diagnose that
    variable: its definition, evidence weight, the data sources that
    answer it, its Step 1.5 rules, citations, and the verification/cost
    guidance from the taxonomy. If ``only`` is given, restrict to that set
    of variable_ids (used by the scoped LLM-judgment brief).
    """
    entries: list[dict[str, Any]] = []
    for v in sorted(catalog, key=lambda x: x.variable_id):
        if only is not None and v.variable_id not in only:
            continue
        entries.append(
            {
                "variable_id": v.variable_id,
                "pillar": v.pillar,
                "name": v.name,
                "definition": v.definition,
                "evidence_weight": (
                    v.evidence_weight.value if v.evidence_weight is not None else None
                ),
                "weight_rationale": v.weight_rationale,
                "data_sources": list(v.data_sources),
                "rules": [
                    {"rule_id": r.rule_id, "title": r.title, "text": r.text}
                    for r in v.rules
                ],
                "citations": [
                    {"label": c.label, "url": c.url, "description": c.description}
                    for c in v.citations
                ],
                "verification": v.verification,
                "cost": v.cost,
                "hard_dependencies": v.hard_dependencies,
            }
        )
    return entries


def build_brief(catalog: Catalog, *, only: Collection[str] | None = None) -> dict[str, Any]:
    """Build the audit brief document from a Catalog.

    ``only`` restricts the brief to a subset of variable_ids (e.g.
    ``LLM_JUDGMENT_VARIABLES`` for the session-driven LLM-eval hybrid).

    Top-level fields:
      - ``taxonomy_version``: copy verbatim into the ingest document's
        ``taxonomy_version`` so captures are tagged with the exact taxonomy
        the session worked from.
      - ``variable_count`` / ``pillars``: sanity counts.
      - ``data_sources``: the union of every data source named across
        variables, so the session knows up front which sources it must be
        able to reach.
      - ``variables``: the per-variable instruction set.
    """
    variables = variable_brief(catalog, only=only)

    all_sources: set[str] = set()
    for entry in variables:
        all_sources.update(entry["data_sources"])

    pillars: dict[str, int] = {}
    for entry in variables:
        pillars[entry["pillar"]] = pillars.get(entry["pillar"], 0) + 1

    return {
        "taxonomy_version": catalog.version,
        "source_path": str(catalog.source_path),
        "variable_count": len(variables),
        "pillars": dict(sorted(pillars.items())),
        "data_sources": sorted(all_sources),
        "variables": variables,
    }
