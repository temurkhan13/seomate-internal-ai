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

from typing import Any

from seomate.taxonomy import Catalog


def variable_brief(catalog: Catalog) -> list[dict[str, Any]]:
    """Return one brief entry per active (non-removed) variable.

    Each entry carries everything the session needs to diagnose that
    variable: its definition, evidence weight, the data sources that
    answer it, its Step 1.5 rules, citations, and the verification/cost
    guidance from the taxonomy.
    """
    entries: list[dict[str, Any]] = []
    for v in sorted(catalog, key=lambda x: x.variable_id):
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


def build_brief(catalog: Catalog) -> dict[str, Any]:
    """Build the full audit brief document from a Catalog.

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
    variables = variable_brief(catalog)

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
