"""Taxonomy parser and structured catalog.

The taxonomy is the constitutional reference (docs/o1-taxonomy.md, 232
active variables across 7 pillars). The auditor parses it once at audit
start so every layer downstream — orchestrator, FastAPI, Next.js UI —
queries against a structured representation rather than raw markdown.
"""
from seomate.taxonomy.catalog import DEFAULT_TAXONOMY_PATH, Catalog
from seomate.taxonomy.loader import parse_taxonomy_file
from seomate.taxonomy.schemas import (
    Citation,
    Dependency,
    DependencyKind,
    Pillar,
    PillarId,
    TaxonomyRule,
    Variable,
)

__all__ = [
    "DEFAULT_TAXONOMY_PATH",
    "Catalog",
    "Citation",
    "Dependency",
    "DependencyKind",
    "Pillar",
    "PillarId",
    "TaxonomyRule",
    "Variable",
    "parse_taxonomy_file",
]
