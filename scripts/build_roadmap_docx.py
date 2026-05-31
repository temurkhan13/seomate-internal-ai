"""Convert ROADMAP.md to docs/SEOMATE-roadmap.docx.

Same engine as build_handover_docx.py; different source file.
Kept as a separate script (rather than parameterising the existing
one) so the conversion is reproducible per-document and trivially
greppable.

Run from the auditor/ dir:
    .venv/Scripts/python scripts/build_roadmap_docx.py
"""
from __future__ import annotations

from pathlib import Path

# Reuse the converter from build_handover_docx
import importlib.util


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "handover_converter", HERE / "build_handover_docx.py"
)
assert SPEC and SPEC.loader
_handover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_handover)


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "ROADMAP.md"
OUT = REPO_ROOT / "docs" / "SEOMATE-roadmap.docx"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"source not found: {SRC}")

    from docx import Document
    from docx.shared import Cm, Pt

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    md_text = SRC.read_text(encoding="utf-8")
    _handover.render_markdown(doc, md_text)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Wrote: {OUT}")


if __name__ == "__main__":
    main()
