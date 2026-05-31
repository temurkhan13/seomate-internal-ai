"""Per-audit cost tracking with hard cap and soft warning.

Decimal arithmetic throughout — float would accumulate rounding error
across thousands of calls and produce wrong total_cost_gbp on the audits
table.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class CostCapExceeded(RuntimeError):
    """Raised by CostTracker.assert_under_cap() when total >= cap_gbp."""


class CostTracker:
    """Tracks £ cost across an audit. One instance per AuditOrchestrator run.

    Usage in an extractor:

        marker = ctx.cost_tracker.set_marker()
        ... call adapters which call ctx.cost_tracker.record(...)
        cost_for_this_extractor = ctx.cost_tracker.delta_since(marker)
    """

    def __init__(self, cap_gbp: float, warn_fraction: float = 0.8) -> None:
        if cap_gbp < 0:
            raise ValueError("cap_gbp must be non-negative")
        if not 0 < warn_fraction <= 1:
            raise ValueError("warn_fraction must be in (0, 1]")
        self._cap = Decimal(str(cap_gbp))
        self._warn_threshold = self._cap * Decimal(str(warn_fraction))
        self._total = Decimal("0")
        self._per_adapter: dict[str, Decimal] = {}
        self._warned = False

    def record(self, adapter: str, cost_gbp: float | Decimal) -> None:
        """Add a cost increment for one adapter call."""
        amount = cost_gbp if isinstance(cost_gbp, Decimal) else Decimal(str(cost_gbp))
        if amount < 0:
            raise ValueError("cost_gbp must be non-negative")
        self._total += amount
        self._per_adapter[adapter] = self._per_adapter.get(adapter, Decimal("0")) + amount

    def set_marker(self) -> Decimal:
        """Snapshot current total. Pass return value to delta_since()."""
        return self._total

    def delta_since(self, marker: Decimal) -> float:
        """Return the cost incurred since the given marker, in £."""
        return float(self._total - marker)

    @property
    def total(self) -> float:
        return float(self._total)

    @property
    def total_decimal(self) -> Decimal:
        """Decimal precision — use for DB writes."""
        return self._total

    @property
    def cap(self) -> float:
        return float(self._cap)

    @property
    def remaining(self) -> float:
        return float(self._cap - self._total)

    @property
    def per_adapter(self) -> Mapping[str, float]:
        return {k: float(v) for k, v in self._per_adapter.items()}

    @property
    def is_capped(self) -> bool:
        return self._total >= self._cap

    @property
    def should_warn(self) -> bool:
        """True if we've crossed the soft warn threshold but haven't been told yet."""
        if self._warned:
            return False
        if self._total >= self._warn_threshold:
            self._warned = True
            return True
        return False

    def assert_under_cap(self) -> None:
        """Raise CostCapExceeded if the cap has been reached.

        Call this before dispatching new captures; the orchestrator uses
        it as a hard halt.
        """
        if self.is_capped:
            raise CostCapExceeded(
                f"Cost cap of £{self._cap:.4f} reached (total £{self._total:.4f})"
            )
