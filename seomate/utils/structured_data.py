"""Structured-data extraction and normalisation.

Parses every form of structured data Google or schema.org consumers
care about — JSON-LD, microdata, RDFa, OpenGraph, microformat (mf2),
DublinCore — using ``extruct`` and normalises the result into a flat
list of typed schema blocks. Downstream P1-21/P1-22/P1-47/P6-19/P6-20
extractors operate against the normalised view, never against
``extruct``'s raw output, so the data shape is stable across library
versions.

We deliberately keep validation light here (presence + parseability +
``@context`` / ``@type`` shape). Per-type required-property checks
live in the extractors that consume this module, because what counts
as "required" depends on which schema family the variable is gating
(P1-22 uses Google Rich Results requirements; P6-20 uses schema.org's
Person / Organization recommendations; the two lists overlap but
aren't identical).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import extruct
from w3lib.html import get_base_url

# Common schema.org @context URLs we accept as "real" schema.org markup.
SCHEMA_ORG_CONTEXTS = (
    "http://schema.org",
    "https://schema.org",
    "http://schema.org/",
    "https://schema.org/",
    "//schema.org",
    "//schema.org/",
)

# extruct returns one bucket per syntax; we walk every bucket so the
# downstream view is uniform regardless of how the site declared its
# structured data.
_EXTRUCT_SYNTAXES = ("json-ld", "microdata", "rdfa", "opengraph", "microformat", "dublincore")


@dataclass(frozen=True)
class SchemaBlock:
    """One normalised structured-data block found on a page."""

    syntax: str                        # 'json-ld' | 'microdata' | 'rdfa' | ...
    types: tuple[str, ...]             # @type values, normalised (no schema.org/ prefix)
    context: str | None                # @context, lowercased; None if absent
    is_schema_org: bool                # @context resolves to schema.org
    raw: dict[str, Any]                # the raw block (extruct shape)
    properties: tuple[str, ...]        # top-level property names present
    has_id: bool                       # @id present
    parse_error: str | None = None     # populated for malformed JSON-LD


@dataclass(frozen=True)
class GraphRef:
    """One graph-linkage fact: which @id appears, and which references point to it."""

    id_value: str
    declared_in_types: tuple[str, ...]   # @type values of blocks declaring this @id
    referenced_in_types: tuple[str, ...] # @type values of blocks referencing this @id


@dataclass(frozen=True)
class StructuredData:
    """The full structured-data view of one page."""

    url: str
    blocks: tuple[SchemaBlock, ...]
    json_ld_parse_errors: tuple[str, ...]
    graph_refs: tuple[GraphRef, ...]      # @graph + @id references found across blocks
    open_graph: dict[str, str] = field(default_factory=dict)

    @property
    def schema_org_blocks(self) -> tuple[SchemaBlock, ...]:
        return tuple(b for b in self.blocks if b.is_schema_org)

    @property
    def all_types(self) -> tuple[str, ...]:
        seen: set[str] = set()
        out: list[str] = []
        for b in self.blocks:
            for t in b.types:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
        return tuple(out)

    def blocks_of_type(self, schema_type: str) -> tuple[SchemaBlock, ...]:
        target = _normalise_type(schema_type)
        return tuple(b for b in self.blocks if target in b.types)


def parse_structured_data(html: str, *, url: str) -> StructuredData:
    """Parse structured data from one page's HTML.

    Catches ``extruct`` parse errors per syntax and records them
    rather than aborting — a malformed JSON-LD block on the page is
    interesting evidence for P1-22 (validity), not a reason to fail
    the whole capture.
    """
    if not html:
        return StructuredData(
            url=url,
            blocks=(),
            json_ld_parse_errors=(),
            graph_refs=(),
        )

    base = get_base_url(html, url)
    json_ld_errors: list[str] = []
    extracted: dict[str, Any] = {}
    for syntax in _EXTRUCT_SYNTAXES:
        try:
            partial = extruct.extract(
                html,
                base_url=base,
                syntaxes=[syntax],
                uniform=False,
            )
            extracted.update(partial)
        except Exception as exc:  # noqa: BLE001
            if syntax == "json-ld":
                json_ld_errors.append(f"{type(exc).__name__}: {exc}")

    blocks: list[SchemaBlock] = []
    for syntax in _EXTRUCT_SYNTAXES:
        for raw in extracted.get(syntax, []) or []:
            blocks.extend(_normalise_block(syntax, raw))

    graph_refs = _collect_graph_refs(blocks)
    open_graph = _flatten_opengraph(extracted.get("opengraph", []) or [])

    return StructuredData(
        url=url,
        blocks=tuple(blocks),
        json_ld_parse_errors=tuple(json_ld_errors),
        graph_refs=graph_refs,
        open_graph=open_graph,
    )


# ─── Normalisation helpers ──────────────────────────────────────────────────


def _normalise_block(syntax: str, raw: Any) -> Iterable[SchemaBlock]:
    """Walk a raw extruct block. Handles ``@graph`` by yielding sub-blocks."""
    if isinstance(raw, list):
        for item in raw:
            yield from _normalise_block(syntax, item)
        return
    if not isinstance(raw, dict):
        return

    # Microdata wraps payload in {'type': [...], 'properties': {...}}
    if syntax == "microdata" and "properties" in raw and "type" in raw:
        type_list = raw.get("type") or []
        types = tuple(_normalise_type(t) for t in type_list if isinstance(t, str))
        props = raw.get("properties") or {}
        yield SchemaBlock(
            syntax=syntax,
            types=types,
            context="schema.org",
            is_schema_org=True,
            raw=raw,
            properties=tuple(sorted(props.keys())) if isinstance(props, dict) else (),
            has_id=isinstance(raw.get("id"), str) and bool(raw.get("id")),
        )
        return

    # RDFa returns each block keyed by @id with a list of @type predicates.
    # JSON-LD blocks may carry a top-level @graph list — flatten it.
    if syntax == "json-ld" and isinstance(raw.get("@graph"), list):
        outer_context = raw.get("@context")
        for sub in raw["@graph"]:
            if isinstance(sub, dict) and "@context" not in sub and outer_context:
                sub_with_ctx = {"@context": outer_context, **sub}
            else:
                sub_with_ctx = sub
            yield from _normalise_block(syntax, sub_with_ctx)
        return

    context = _stringify_context(raw.get("@context"))
    is_schema_org = bool(context and any(s in context for s in SCHEMA_ORG_CONTEXTS))
    type_field = raw.get("@type") or raw.get("type")
    if isinstance(type_field, str):
        types = (_normalise_type(type_field),)
    elif isinstance(type_field, list):
        types = tuple(_normalise_type(t) for t in type_field if isinstance(t, str))
    else:
        types = ()

    properties = tuple(
        sorted(k for k in raw.keys() if not k.startswith("@") and k not in ("type",))
    )
    has_id = isinstance(raw.get("@id"), str) and bool(raw.get("@id"))

    yield SchemaBlock(
        syntax=syntax,
        types=types,
        context=context,
        is_schema_org=is_schema_org,
        raw=raw,
        properties=properties,
        has_id=has_id,
    )


def _normalise_type(t: str) -> str:
    """Strip schema.org URL prefixes so 'Organization' == 'http://schema.org/Organization'."""
    if not isinstance(t, str):
        return ""
    s = t.strip()
    for prefix in (
        "https://schema.org/",
        "http://schema.org/",
        "//schema.org/",
        "schema:",
    ):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def _stringify_context(ctx: Any) -> str | None:
    if isinstance(ctx, str):
        return ctx.lower()
    if isinstance(ctx, list) and ctx:
        # Pick the schema.org entry if present.
        for c in ctx:
            if isinstance(c, str) and "schema.org" in c.lower():
                return c.lower()
        first = ctx[0]
        return first.lower() if isinstance(first, str) else None
    if isinstance(ctx, dict):
        # Linked-data style: take the @vocab entry, falling back to anything pointing at schema.org.
        v = ctx.get("@vocab")
        if isinstance(v, str):
            return v.lower()
        for val in ctx.values():
            if isinstance(val, str) and "schema.org" in val.lower():
                return val.lower()
    return None


def _collect_graph_refs(blocks: list[SchemaBlock]) -> tuple[GraphRef, ...]:
    """Walk blocks and build the @id → references-to-it index."""
    declared: dict[str, list[str]] = {}
    referenced: dict[str, list[str]] = {}
    for block in blocks:
        if block.has_id:
            id_value = str(block.raw.get("@id"))
            declared.setdefault(id_value, []).extend(block.types)
        for ref_id in _walk_id_refs(block.raw):
            if ref_id != block.raw.get("@id"):
                referenced.setdefault(ref_id, []).extend(block.types)
    out: list[GraphRef] = []
    for id_value in sorted(set(declared) | set(referenced)):
        out.append(
            GraphRef(
                id_value=id_value,
                declared_in_types=tuple(declared.get(id_value, [])),
                referenced_in_types=tuple(referenced.get(id_value, [])),
            )
        )
    return tuple(out)


def _walk_id_refs(node: Any) -> Iterable[str]:
    """Yield every ``@id`` value found in a nested block, except the top-level one."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "@id" and isinstance(v, str):
                # Distinguish "@id of this block" vs "{ @id: ... } reference object"
                # The caller filters out the top-level @id; here we just emit values
                # that appear inside nested {"@id": ...} objects (which are pure refs).
                yield v
            else:
                yield from _walk_id_refs(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_id_refs(item)


def _flatten_opengraph(blocks: list[Any]) -> dict[str, str]:
    """Reduce extruct's opengraph output to a flat ``{property: content}`` view."""
    flat: dict[str, str] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        props = block.get("properties") or block.get("og") or block
        if isinstance(props, list):
            for pair in props:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    k, v = pair
                    if isinstance(k, str) and isinstance(v, str):
                        flat.setdefault(k, v)
        elif isinstance(props, dict):
            for k, v in props.items():
                if isinstance(k, str) and isinstance(v, str):
                    flat.setdefault(k, v)
    return flat
