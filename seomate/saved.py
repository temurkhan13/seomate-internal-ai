"""Persistence for saved competitive + strategy analyses (the SavedAnalysis table).

A thin repo over ``session_scope`` so the API can save a run, list past runs for
a domain, and fetch one for free revisiting , the history behind the Competitive
and Strategy surfaces (so a colleague can browse past analyses like audits, and
not re-pay DataForSEO to look at one again).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from seomate.storage import SavedAnalysis, session_scope


async def save_analysis(
    kind: str,
    target: str,
    payload: dict[str, Any],
    cost_gbp: float | None = None,
) -> str:
    """Persist one analysis run; return its id."""
    async with session_scope() as s:
        row = SavedAnalysis(
            kind=kind, target=target, payload=payload, cost_gbp=cost_gbp
        )
        s.add(row)
        await s.flush()
        return str(row.analysis_id)


async def list_analyses(
    kind: str, target: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Saved analyses of a kind (optionally for one domain), newest first.

    Summary only (no payload) , for the history list.
    """
    async with session_scope() as s:
        stmt = select(
            SavedAnalysis.analysis_id,
            SavedAnalysis.kind,
            SavedAnalysis.target,
            SavedAnalysis.created_at,
            SavedAnalysis.cost_gbp,
        ).where(SavedAnalysis.kind == kind)
        if target:
            stmt = stmt.where(SavedAnalysis.target == target)
        stmt = stmt.order_by(SavedAnalysis.created_at.desc()).limit(limit)
        rows = (await s.execute(stmt)).all()
    return [
        {
            "analysis_id": str(aid),
            "kind": k,
            "target": t,
            "created_at": str(c) if c else None,
            "cost_gbp": float(g) if g is not None else None,
        }
        for aid, k, t, c, g in rows
    ]


async def get_analysis(analysis_id: str | UUID) -> dict[str, Any] | None:
    """One saved analysis with its payload, or None if not found."""
    async with session_scope() as s:
        row = await s.get(SavedAnalysis, UUID(str(analysis_id)))
        if row is None:
            return None
        return {
            "analysis_id": str(row.analysis_id),
            "kind": row.kind,
            "target": row.target,
            "created_at": str(row.created_at) if row.created_at else None,
            "cost_gbp": float(row.cost_gbp) if row.cost_gbp is not None else None,
            "payload": row.payload,
        }
