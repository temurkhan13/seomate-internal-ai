"""Pillar capture modules.

Each variable in the taxonomy that has been operationalised lives in
the pillar module matching its prefix (P1- vars → ``p1_onpage.py``,
etc.). Variables register themselves into ``EXTRACTOR_REGISTRY`` so the
orchestrator can dispatch by id without hard-coding imports.

Variables are added incrementally through H1a–H1d. Anything in the
catalog without a registered extractor is simply skipped at audit
time — no error.
"""
from seomate.pillars._base import (
    EXTRACTOR_REGISTRY,
    BrandIdentity,
    Extractor,
    PageAudit,
    SiteData,
    normalise_instant_page_response,
    register_extractor,
)

# Side-effect imports register each pillar module's extractors.
from seomate.pillars import p0_strategic  # noqa: F401
from seomate.pillars import p1_onpage  # noqa: F401
from seomate.pillars import p1_schema  # noqa: F401
from seomate.pillars import p2_psi  # noqa: F401
from seomate.pillars import p2_technical  # noqa: F401
from seomate.pillars import p3_backlinks  # noqa: F401
from seomate.pillars import p4_content  # noqa: F401
from seomate.pillars import p5_local  # noqa: F401
from seomate.pillars import p6_geo  # noqa: F401
from seomate.pillars import p6_serp  # noqa: F401
from seomate.pillars import p_embeddings  # noqa: F401
from seomate.pillars import p_freebatch  # noqa: F401
from seomate.pillars import p_keyword  # noqa: F401

__all__ = [
    "EXTRACTOR_REGISTRY",
    "BrandIdentity",
    "Extractor",
    "PageAudit",
    "SiteData",
    "normalise_instant_page_response",
    "register_extractor",
]
