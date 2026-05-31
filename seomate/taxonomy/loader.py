"""Parse ``docs/o1-taxonomy.md`` into structured Variable records.

The parser is intentionally regex / line-walking based rather than using
a full markdown AST: it ignores prose formatting and only cares about
the heading skeleton (``# Pillar N``, ``## P{n}-{nn}``, ``### Step N``).

Robustness concerns the parser handles explicitly:

- Removed-variable redirects (``## P1-39 — ... *(removed — see P1-35)*``)
  are detected and flagged with ``removed=True`` and ``removed_into``.
- Variables with parenthetical suffixes in the title
  (``## P1-34 — Content depth / word count (also covers leaked numTokens)``)
  parse cleanly into ``name``.
- Step 1.5 is optional; pure-measurement variables have no rules block.
- Step 7 dependency edges are extracted with intent-tagging
  (``depends_on``, ``cross_reference``, ``cross_pillar``, etc.) rather
  than being treated as a single bag.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from seomate.data_contract import EvidenceWeight
from seomate.taxonomy.schemas import (
    Citation,
    Dependency,
    DependencyKind,
    Pillar,
    PillarId,
    TaxonomyRule,
    Variable,
)

# ─── Regex skeleton ─────────────────────────────────────────────────────────

PILLAR_HEADING_RE = re.compile(r"^# Pillar (?P<n>\d) [—-] (?P<name>.+?)\s*$")
VARIABLE_HEADING_RE = re.compile(
    r"^## (?P<id>P[0-6]-\d{2}) [—-] (?P<title>.+?)\s*$",
)
REMOVED_TITLE_RE = re.compile(r"\*\(removed\s*[—-]\s*see\s+(?P<into>P[0-6]-\d{2})\)\*", re.IGNORECASE)
STEP_HEADING_RE = re.compile(r"^### Step (?P<n>\d(?:\.5)?) [—-] (?P<name>.+?)\s*$")
PILLAR_FIELD_RE = re.compile(r"^\*\*Pillar:\*\*\s*(?P<value>.+?)\s*$")
WEIGHT_FIELD_RE = re.compile(r"^\*\*Evidence weight:\*\*\s*(?P<value>.+?)\s*$")
NUMBERED_RULE_RE = re.compile(
    r"^\d+\.\s+\*\*(?P<title>.+?)\*\*\s*(?P<rest>.*?)\s*$",
)
NUMBERED_RULE_BARE_RE = re.compile(
    # Permissive fallback for variables that don't use bold-prefixed titles
    # (e.g. P4-06 E-E-A-T uses category-grouped rules without per-rule bold).
    r"^\d+\.\s+(?P<rest>.+?)\s*$",
)
NUMBERED_CITATION_RE = re.compile(
    r"^\d+\.\s+\*\*(?P<label>.+?)\*\*\s*(?P<rest>.*?)\s*$",
)
URL_IN_PARENS_RE = re.compile(r"\((https?://[^\s)]+)")
DEPENDENCY_BULLET_RE = re.compile(
    r"^-\s+\*\*(?P<label>.+?):\*\*\s*(?P<text>.+?)\s*$",
)
VARIABLE_ID_RE = re.compile(r"\b(P[0-6]-\d{2})\b")

# Map dependency labels (lower-cased) to the canonical DependencyKind
DEPENDENCY_LABEL_KIND: dict[str, DependencyKind] = {
    "depends on": "depends_on",
    "depended upon by": "depended_upon_by",
    "cross-references": "cross_reference",
    "cross-reference": "cross_reference",
    "cross-pillar": "cross_pillar",
    "companion to": "companion",
    "companions": "companion",
    "subsumes": "subsumes",
    "related to": "related",
    "scope of this variable": "other",
    "schema family hierarchy": "other",
    "author authority hierarchy": "other",
    "hierarchy": "other",
}


def _normalise_label(label: str) -> str:
    return label.strip().lower().rstrip(":")


def _extract_url(text: str) -> str | None:
    m = URL_IN_PARENS_RE.search(text)
    return m.group(1) if m else None


# ─── Pillar id mapping ──────────────────────────────────────────────────────

PILLAR_ID_MAP: dict[str, PillarId] = {
    "0": "P0",
    "1": "P1",
    "2": "P2",
    "3": "P3",
    "4": "P4",
    "5": "P5",
    "6": "P6",
}


# ─── Section-level intermediate ─────────────────────────────────────────────


class _RawSection:
    """Buffer for one variable's prose, sliced by ``### Step`` headings."""

    def __init__(self, variable_id: str, pillar_id: PillarId, title: str) -> None:
        self.variable_id = variable_id
        self.pillar_id = pillar_id
        self.title = title
        self.removed = False
        self.removed_into: str | None = None
        self.preamble: list[str] = []
        self.steps: dict[str, list[str]] = {}
        self._current_step: str | None = None

    def add_line(self, line: str) -> None:
        if self._current_step is None:
            self.preamble.append(line)
        else:
            self.steps.setdefault(self._current_step, []).append(line)

    def begin_step(self, step_id: str) -> None:
        self._current_step = step_id

    def get_step(self, step_id: str) -> str:
        return "\n".join(self.steps.get(step_id, [])).strip()


# ─── Public API ─────────────────────────────────────────────────────────────


def parse_taxonomy_file(path: Path) -> tuple[list[Pillar], str]:
    """Parse the taxonomy markdown and return (pillars, version_hash).

    The version hash is the first 12 chars of the SHA-256 of the file
    contents — any change bumps the version automatically. Captures
    record this so old captures retain meaning across taxonomy revisions.
    """
    text = Path(path).read_text(encoding="utf-8")
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    pillars = _parse_pillars(text)
    return pillars, version


def _parse_pillars(text: str) -> list[Pillar]:
    lines = text.splitlines()
    pillars: list[Pillar] = []
    current_pillar: Pillar | None = None
    sections: list[_RawSection] = []
    current_section: _RawSection | None = None

    for raw in lines:
        line = raw.rstrip()

        # Pillar boundary (``# Pillar N — Name``)
        m_pillar = PILLAR_HEADING_RE.match(line)
        if m_pillar:
            # Flush any in-progress section into the previous pillar
            if current_section and current_pillar is not None:
                sections.append(current_section)
                current_section = None
            n = m_pillar.group("n")
            current_pillar = Pillar(
                pillar_id=PILLAR_ID_MAP[n],
                name=m_pillar.group("name").strip(),
            )
            pillars.append(current_pillar)
            continue

        # Variable boundary (``## P{n}-{nn} — Name``)
        m_var = VARIABLE_HEADING_RE.match(line)
        if m_var:
            if current_section and current_pillar is not None:
                sections.append(current_section)
            if current_pillar is None:
                # Variable encountered before any pillar header —
                # adopt the variable's own prefix to derive the pillar.
                pillar_id = PILLAR_ID_MAP[m_var.group("id")[1]]
                current_pillar = Pillar(pillar_id=pillar_id, name="(unknown)")
                pillars.append(current_pillar)
            else:
                # Cross-pillar variable IDs in our doc are kept under their
                # own pillar; if the variable's prefix doesn't match the
                # current pillar, re-resolve to the right pillar (creating
                # if necessary). Pillar 0 is documented after Pillar 1 in
                # our taxonomy, so this happens routinely.
                wanted = PILLAR_ID_MAP[m_var.group("id")[1]]
                if current_pillar.pillar_id != wanted:
                    current_pillar = next(
                        (p for p in pillars if p.pillar_id == wanted),
                        None,
                    )
                    if current_pillar is None:
                        current_pillar = Pillar(pillar_id=wanted, name="(deferred)")
                        pillars.append(current_pillar)

            current_section = _RawSection(
                variable_id=m_var.group("id"),
                pillar_id=current_pillar.pillar_id,
                title=_clean_title(m_var.group("title")),
            )
            removed_match = REMOVED_TITLE_RE.search(m_var.group("title"))
            if removed_match:
                current_section.removed = True
                current_section.removed_into = removed_match.group("into")
            continue

        # Step boundary inside a variable
        m_step = STEP_HEADING_RE.match(line)
        if m_step and current_section is not None:
            current_section.begin_step(m_step.group("n"))
            continue

        if current_section is not None:
            current_section.add_line(raw)

    if current_section is not None:
        sections.append(current_section)

    # Materialise variables into their pillars
    pillars_by_id: dict[str, Pillar] = {p.pillar_id: p for p in pillars}
    for section in sections:
        variable = _section_to_variable(section)
        pillars_by_id[section.pillar_id].variables.append(variable)

    return pillars


def _clean_title(raw_title: str) -> str:
    """Strip the optional ``*(removed — see ...)*`` suffix from a title."""
    return REMOVED_TITLE_RE.sub("", raw_title).strip()


def _section_to_variable(section: _RawSection) -> Variable:
    if section.removed:
        return Variable(
            variable_id=section.variable_id,
            pillar=section.pillar_id,
            name=section.title,
            evidence_weight=None,
            removed=True,
            removed_into=section.removed_into,
        )

    pillar_value, weight_value = _extract_preamble(section.preamble)

    rules = _parse_rules(section.get_step("1.5"))
    definition = section.get_step("1")
    citations = _parse_citations(section.get_step("2"))
    weight_rationale = section.get_step("3")
    data_sources = _parse_bullet_list(section.get_step("4"))
    verification = section.get_step("5")
    cost = section.get_step("6")
    dependencies = _parse_dependencies(section.get_step("7"))

    weight: EvidenceWeight | None = None
    if weight_value:
        try:
            weight = EvidenceWeight(weight_value)
        except ValueError:
            weight = None

    return Variable(
        variable_id=section.variable_id,
        pillar=section.pillar_id,
        name=section.title,
        evidence_weight=weight,
        definition=definition,
        rules=rules,
        citations=citations,
        weight_rationale=weight_rationale,
        data_sources=data_sources,
        verification=verification,
        cost=cost,
        dependencies=dependencies,
        removed=False,
    )


def _extract_preamble(lines: list[str]) -> tuple[str | None, str | None]:
    pillar_value: str | None = None
    weight_value: str | None = None
    for raw in lines:
        line = raw.strip()
        m = PILLAR_FIELD_RE.match(line)
        if m:
            pillar_value = m.group("value").strip()
            continue
        m = WEIGHT_FIELD_RE.match(line)
        if m:
            weight_value = m.group("value").strip()
            continue
    return pillar_value, weight_value


def _parse_rules(text: str) -> list[TaxonomyRule]:
    """Parse Step 1.5 rules from markdown.

    Two formats supported:
    - Standard: ``1. **Title.** Description text...`` (per-rule bold title).
    - Bare numbered: ``1. Description text...`` (used by P4-06 E-E-A-T which
      groups rules under category headers instead of per-rule titles).
    """
    if not text:
        return []
    rules: list[TaxonomyRule] = []
    for block in _split_numbered_items(text):
        leading = block.split(".", 1)[0].strip()
        try:
            rule_id = int(leading)
        except ValueError:
            continue
        m = NUMBERED_RULE_RE.match(block)
        if m:
            title = m.group("title").strip().rstrip(".")
        else:
            bare = NUMBERED_RULE_BARE_RE.match(block)
            if not bare:
                continue
            # Title is best-effort: first sentence or first 80 chars.
            rest = bare.group("rest").strip()
            first_period = rest.find(".")
            title = rest[: first_period].strip() if 0 < first_period <= 80 else rest[:80].strip()
        rules.append(TaxonomyRule(rule_id=rule_id, title=title, text=block.strip()))
    return rules


def _parse_citations(text: str) -> list[Citation]:
    if not text:
        return []
    citations: list[Citation] = []
    for block in _split_numbered_items(text):
        m = NUMBERED_CITATION_RE.match(block)
        if not m:
            continue
        label = m.group("label").strip()
        rest = m.group("rest").strip()
        url = _extract_url(rest)
        citations.append(Citation(label=label, url=url, description=rest or None))
    return citations


def _parse_bullet_list(text: str) -> list[str]:
    if not text:
        return []
    items: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("- ") or line.startswith("* "):
            if current:
                items.append(" ".join(current).strip())
                current = []
            current.append(line[2:].strip())
        elif line.startswith("  ") and current:
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    return items


def _parse_dependencies(text: str) -> list[Dependency]:
    if not text:
        return []
    edges: list[Dependency] = []
    seen: set[tuple[str, DependencyKind]] = set()
    for raw in text.splitlines():
        line = raw.rstrip()
        m = DEPENDENCY_BULLET_RE.match(line)
        if not m:
            continue
        label = _normalise_label(m.group("label"))
        kind: DependencyKind = DEPENDENCY_LABEL_KIND.get(label, "other")
        body = m.group("text")
        for vid in VARIABLE_ID_RE.findall(body):
            key = (vid, kind)
            if key in seen:
                continue
            seen.add(key)
            edges.append(Dependency(target_id=vid, kind=kind, note=label))
    return edges


def _split_numbered_items(text: str) -> list[str]:
    """Split a Markdown-flavoured numbered list into per-item strings.

    The taxonomy's numbered lists run with one item per line. Blank
    lines or non-numbered content terminates the list.
    """
    items: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^\d+\.\s", line):
            if current:
                items.append(" ".join(current).strip())
            current = [line]
        elif line.startswith("   ") and current:
            current.append(line.strip())
        elif not line and current:
            # Blank line: keep the current item open in case continuation follows.
            continue
        else:
            if current:
                items.append(" ".join(current).strip())
                current = []
    if current:
        items.append(" ".join(current).strip())
    return items
