"""Pydantic models for the parsed taxonomy.

These mirror the structural sections in docs/o1-taxonomy.md (the
seven-step process plus the optional Step 1.5 evaluation rules) but
flatten the prose into the fields the orchestrator and downstream
layers actually consume.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from seomate.data_contract import EvidenceWeight


PillarId = Literal["P0", "P1", "P2", "P3", "P4", "P5", "P6"]
DependencyKind = Literal[
    "depends_on",
    "depended_upon_by",
    "cross_reference",
    "cross_pillar",
    "companion",
    "subsumes",
    "related",
    "other",
]


class TaxonomyRule(BaseModel):
    """One Step 1.5 evaluation rule extracted from a variable."""

    model_config = ConfigDict(frozen=True)

    rule_id: int = Field(ge=1)
    title: str = Field(description="Bold-prefixed title of the rule")
    text: str = Field(description="Full rule prose including title")


class Citation(BaseModel):
    """One citation extracted from a variable's Step 2."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(description="Bold-prefixed source label")
    url: str | None = None
    description: str | None = None


class Dependency(BaseModel):
    """A dependency edge between two variables.

    The taxonomy distinguishes hard dependencies (``depends_on``) that
    constrain execution order from softer cross-references that only
    inform downstream UI / documentation.
    """

    model_config = ConfigDict(frozen=True)

    target_id: str
    kind: DependencyKind
    note: str | None = None


class Variable(BaseModel):
    """A single variable parsed from o1-taxonomy.md.

    Removed variables (the dedup-audit redirects like P1-39, P2-34) are
    parsed but flagged ``removed=True`` and excluded from the active
    catalog.
    """

    model_config = ConfigDict(extra="forbid")

    variable_id: str = Field(pattern=r"^P[0-6]-\d{2}$")
    pillar: PillarId
    name: str
    evidence_weight: EvidenceWeight | None = None
    definition: str = ""
    rules: list[TaxonomyRule] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    weight_rationale: str = ""
    data_sources: list[str] = Field(default_factory=list)
    verification: str = ""
    cost: str = ""
    dependencies: list[Dependency] = Field(default_factory=list)
    removed: bool = False
    removed_into: str | None = Field(
        default=None,
        description="If removed, the canonical variable that subsumed this one (e.g. P1-39 -> P1-35)",
    )

    @property
    def has_step_1_5(self) -> bool:
        return len(self.rules) > 0

    @property
    def hard_dependencies(self) -> list[str]:
        """Variable IDs this variable hard-depends on (for topological sort)."""
        return [d.target_id for d in self.dependencies if d.kind == "depends_on"]

    @property
    def all_referenced_ids(self) -> list[str]:
        """All variable IDs referenced from Step 7, regardless of edge kind."""
        return [d.target_id for d in self.dependencies]


class Pillar(BaseModel):
    """A pillar grouping with its child variables."""

    model_config = ConfigDict(extra="forbid")

    pillar_id: PillarId
    name: str
    description: str = ""
    variables: list[Variable] = Field(default_factory=list)
