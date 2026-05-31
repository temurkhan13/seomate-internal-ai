"""Structured access to the parsed taxonomy.

The Catalog is built once at audit start (``Catalog.from_file()``) and
queried by the orchestrator and downstream layers. It exposes:

- per-id lookup
- filters by pillar, evidence weight, removed-status
- a topological sort over hard ``depends_on`` edges
- cycle detection
- summary stats for the ``seomate taxonomy-stats`` CLI command
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from seomate.data_contract import EvidenceWeight
from seomate.taxonomy.loader import parse_taxonomy_file
from seomate.taxonomy.schemas import Pillar, PillarId, Variable

if TYPE_CHECKING:
    from collections.abc import Sequence


import os as _os


def _resolve_default_taxonomy_path() -> Path:
    """Locate the taxonomy file at call time.

    Search order:
    1. ``SEOMATE_TAXONOMY_PATH`` env var. Use this for cloud deploys where the
       seomate package is pip-installed into site-packages and the taxonomy doc
       lives somewhere outside that tree.
    2. ``parents[2] / docs / o1-taxonomy.md`` — correct for the post-split
       ``seomate-ai`` repo layout where ``seomate/`` sits at repo root.
    3. ``parents[3] / docs / o1-taxonomy.md`` — historical monorepo layout
       (``seomate/auditor/seomate/taxonomy/catalog.py``).

    The last existing path wins. If none exist, the post-split path is returned
    and ``parse_taxonomy_file`` will raise a clear FileNotFoundError.
    """
    env_override = _os.environ.get("SEOMATE_TAXONOMY_PATH")
    if env_override:
        return Path(env_override)
    here = Path(__file__).resolve()
    for parents_idx in (2, 3):
        candidate = here.parents[parents_idx] / "docs" / "o1-taxonomy.md"
        if candidate.is_file():
            return candidate
    return here.parents[2] / "docs" / "o1-taxonomy.md"


# Eager evaluation kept for backward compatibility with existing imports.
# ``Catalog.from_file()`` re-evaluates at call time so changes to the env var
# after import are honoured.
DEFAULT_TAXONOMY_PATH = _resolve_default_taxonomy_path()


class Catalog:
    """In-memory taxonomy with lookup, filtering, and topological sort."""

    def __init__(
        self,
        pillars: list[Pillar],
        version: str,
        source_path: Path,
    ) -> None:
        self._pillars = pillars
        self._version = version
        self._source_path = source_path
        self._by_id: dict[str, Variable] = {}
        for pillar in pillars:
            for variable in pillar.variables:
                self._by_id[variable.variable_id] = variable

    @classmethod
    def from_file(cls, path: Path | None = None) -> "Catalog":
        """Parse ``docs/o1-taxonomy.md`` (or the supplied path) into a catalog."""
        path = Path(path) if path is not None else _resolve_default_taxonomy_path()
        pillars, version = parse_taxonomy_file(path)
        return cls(pillars=pillars, version=version, source_path=path)

    # ─── Identity ────────────────────────────────────────────────────────────

    @property
    def version(self) -> str:
        """Content-derived hash of the taxonomy file. Bumps on any change."""
        return self._version

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def pillars(self) -> list[Pillar]:
        return self._pillars

    # ─── Lookups ─────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        """Active (non-removed) variable count."""
        return sum(1 for v in self._by_id.values() if not v.removed)

    def __iter__(self) -> Iterator[Variable]:
        """Iterate over active variables only."""
        return (v for v in self._by_id.values() if not v.removed)

    def __contains__(self, variable_id: str) -> bool:
        return variable_id in self._by_id

    def get(self, variable_id: str) -> Variable | None:
        return self._by_id.get(variable_id)

    def require(self, variable_id: str) -> Variable:
        v = self._by_id.get(variable_id)
        if v is None:
            raise KeyError(f"Variable not in taxonomy: {variable_id}")
        return v

    def all_variables(self, *, include_removed: bool = False) -> list[Variable]:
        if include_removed:
            return list(self._by_id.values())
        return [v for v in self._by_id.values() if not v.removed]

    def by_pillar(
        self,
        pillar_id: PillarId,
        *,
        include_removed: bool = False,
    ) -> list[Variable]:
        out: list[Variable] = []
        for pillar in self._pillars:
            if pillar.pillar_id != pillar_id:
                continue
            for v in pillar.variables:
                if v.removed and not include_removed:
                    continue
                out.append(v)
        return out

    def by_weight(self, weight: EvidenceWeight) -> list[Variable]:
        return [v for v in self if v.evidence_weight is weight]

    def with_step_1_5(self) -> list[Variable]:
        return [v for v in self if v.has_step_1_5]

    def removed_variables(self) -> list[Variable]:
        return [v for v in self._by_id.values() if v.removed]

    # ─── Dependency graph ────────────────────────────────────────────────────

    def hard_dependency_graph(self) -> dict[str, list[str]]:
        """Return the ``depends_on`` adjacency list across active variables.

        Edges to removed variables are dropped (the parser preserved
        them for forensics; the orchestrator should not try to dispatch
        them).
        """
        graph: dict[str, list[str]] = {}
        for v in self:
            edges = [
                target
                for target in v.hard_dependencies
                if target in self._by_id and not self._by_id[target].removed
            ]
            graph[v.variable_id] = edges
        return graph

    def topological_order(self) -> list[str]:
        """Return active variable IDs sorted so that every dependency
        precedes its dependants.

        Raises :class:`ValueError` if a cycle is found among hard
        dependencies. Stable order: among nodes with equal in-degree we
        sort by variable_id so the result is deterministic across runs.
        """
        graph = self.hard_dependency_graph()
        nodes = list(graph)
        in_degree: dict[str, int] = defaultdict(int)
        # Reverse adjacency for outgoing-edge bookkeeping
        dependants: dict[str, list[str]] = defaultdict(list)

        for v_id, deps in graph.items():
            for d in deps:
                in_degree[v_id] += 1
                dependants[d].append(v_id)

        ready = sorted([n for n in nodes if in_degree[n] == 0])
        order: list[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for child in sorted(dependants.get(n, [])):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    # Insert preserving sorted order
                    _insort_sorted(ready, child)

        if len(order) != len(nodes):
            cycle = self.detect_cycles()
            raise ValueError(
                "Hard-dependency cycle detected in taxonomy: "
                + (" -> ".join(cycle[0]) if cycle else "unknown cycle")
            )

        return order

    def detect_cycles(self) -> list[list[str]]:
        """Return any simple cycles found in the hard-dependency graph.

        Implementation: depth-first search with an active-stack;
        whenever we revisit an active node, we extract that segment as
        a cycle. Returns an empty list if the graph is a DAG.
        """
        graph = self.hard_dependency_graph()
        cycles: list[list[str]] = []
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = {n: WHITE for n in graph}
        stack: list[str] = []

        def dfs(node: str) -> None:
            colour[node] = GREY
            stack.append(node)
            for child in graph.get(node, []):
                if colour.get(child) == GREY:
                    idx = stack.index(child)
                    cycles.append([*stack[idx:], child])
                elif colour.get(child) == WHITE:
                    dfs(child)
            stack.pop()
            colour[node] = BLACK

        for n in graph:
            if colour[n] == WHITE:
                dfs(n)
        return cycles

    # ─── Stats summary (used by `seomate taxonomy-stats`) ───────────────────

    def stats(self) -> dict[str, object]:
        active = self.all_variables(include_removed=False)
        removed = self.removed_variables()
        weight_counts: dict[str, int] = defaultdict(int)
        for v in active:
            if v.evidence_weight is not None:
                weight_counts[v.evidence_weight.value] += 1
            else:
                weight_counts["(unweighted)"] += 1
        per_pillar: list[dict[str, object]] = []
        for pillar in self._pillars:
            active_in_pillar = [v for v in pillar.variables if not v.removed]
            per_pillar.append(
                {
                    "pillar_id": pillar.pillar_id,
                    "name": pillar.name,
                    "active": len(active_in_pillar),
                    "removed": sum(1 for v in pillar.variables if v.removed),
                    "with_rules": sum(1 for v in active_in_pillar if v.has_step_1_5),
                }
            )
        graph = self.hard_dependency_graph()
        no_dep_count = sum(1 for v in graph.values() if not v)
        max_dep_count = max((len(v) for v in graph.values()), default=0)
        most_referenced: list[tuple[str, int]] = []
        ref_counter: dict[str, int] = defaultdict(int)
        for v in active:
            for d in v.dependencies:
                ref_counter[d.target_id] += 1
        most_referenced = sorted(
            ref_counter.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )[:5]
        return {
            "version": self._version,
            "source_path": str(self._source_path),
            "active_variables": len(active),
            "removed_variables": len(removed),
            "with_step_1_5": sum(1 for v in active if v.has_step_1_5),
            "by_weight": dict(weight_counts),
            "by_pillar": per_pillar,
            "no_hard_deps": no_dep_count,
            "max_hard_deps": max_dep_count,
            "top_referenced": most_referenced,
            "removed_redirects": [
                {"from": v.variable_id, "into": v.removed_into} for v in removed
            ],
        }


def _insort_sorted(seq: list[str], value: str) -> None:
    """Insert ``value`` into a sorted ``seq`` preserving order. O(n)."""
    for i, existing in enumerate(seq):
        if value < existing:
            seq.insert(i, value)
            return
    seq.append(value)
