"""Google PageSpeed Insights API adapter.

Free Google API (25k queries/day default quota; same Cloud project as
Knowledge Graph). Used by P2-08…P2-14 Core Web Vitals + page-loading
speed variables.

Requires ``GOOGLE_PSI_API_KEY`` in env. If the key is missing the
adapter still opens but every call raises ``PSINotConfigured``;
extractors catch that and report ``unmeasurable`` rather than
crashing the audit.

API reference: https://developers.google.com/speed/docs/insights/v5/get-started

Note: PSI runs a real Lighthouse audit on Google's servers — calls
typically take 20–40 seconds. We pre-fetch a small URL set
(homepage on mobile + desktop) once at audit start to bound the
runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from seomate.adapters._base import (
    AdapterContext,
    BaseAdapter,
    rate_limited,
    retry_transient,
    tracked,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_PATH = str(_REPO_ROOT / ".env")


class PSISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    GOOGLE_PSI_API_KEY: str = ""


class PSINotConfigured(RuntimeError):
    """Raised when the PSI adapter is invoked without an API key."""


PSIStrategy = Literal["mobile", "desktop"]


@dataclass(frozen=True)
class PSIResult:
    """Trimmed view of one PageSpeed Insights run for a single URL+strategy."""

    url: str
    strategy: PSIStrategy
    fetch_status: str               # 'ok' | 'lighthouse_error' | 'fetch_error'

    # Headline scores (Lighthouse-derived, 0-1 floats).
    performance_score: float | None
    accessibility_score: float | None
    best_practices_score: float | None
    seo_score: float | None

    # Core Web Vitals + key load metrics (lab measurements, milliseconds
    # except CLS which is unitless).
    lcp_ms: float | None              # Largest Contentful Paint
    fcp_ms: float | None              # First Contentful Paint
    tbt_ms: float | None              # Total Blocking Time
    cls: float | None                 # Cumulative Layout Shift (unitless)
    speed_index_ms: float | None
    tti_ms: float | None              # Time to Interactive
    ttfb_ms: float | None             # Server Response Time / TTFB

    # Field data from CrUX (only present for sites with enough Chrome traffic).
    crux_lcp_ms: float | None
    crux_inp_ms: float | None
    crux_cls: float | None
    crux_ttfb_ms: float | None
    has_field_data: bool

    # Mobile-relevant audit pass/fail booleans (None if absent).
    # Used by P2-15 mobile responsiveness + P2-17 mobile usability.
    #
    # Lighthouse-as-of-2026 has removed the classic mobile-friendly
    # audits 'font-size', 'tap-targets', and 'content-width' entirely;
    # only 'viewport-insight' survives as a successor to 'viewport'.
    # Discovered when our previous reads returned None across the
    # board. Kept these fields for backward compatibility on captures
    # written under the old schema; new audits populate only the
    # viewport-insight slot.
    audit_viewport_pass: bool | None = None
    audit_font_size_pass: bool | None = None          # deprecated by Lighthouse
    audit_tap_targets_pass: bool | None = None         # deprecated by Lighthouse
    audit_content_width_pass: bool | None = None       # deprecated by Lighthouse

    # Page weight, read from Lighthouse audits we already fetch (no extra cost):
    # 'total-byte-weight' = total transfer bytes; 'resource-summary' image row =
    # image transfer bytes. Feed P2-30 (page weight) + P1-30 (image size).
    total_byte_weight_bytes: int | None = None
    image_bytes: int | None = None

    error: str | None = None


class PSIAdapter(BaseAdapter):
    name: ClassVar[str] = "google_psi"
    # Free tier is 240 RPM (4 RPS) + 25k RPD. Lighthouse runs are slow so
    # we never approach those limits in practice; cap conservatively.
    default_rps: ClassVar[float] = 1.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        settings: PSISettings | None = None,
        rps: float | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.settings = settings or PSISettings()
        self._cache: dict[str, PSIResult] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.GOOGLE_PSI_API_KEY)

    async def __aenter__(self) -> "PSIAdapter":
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            base_url="https://www.googleapis.com",
            headers={"Accept": "application/json"},
        )
        return self

    @rate_limited
    @retry_transient()
    @tracked("psi.runPagespeed")
    async def run_pagespeed(
        self,
        url: str,
        *,
        strategy: PSIStrategy = "mobile",
    ) -> PSIResult:
        """Run a Lighthouse audit + CrUX lookup for one URL+strategy.

        Returns a PSIResult with both lab (always populated when the
        Lighthouse run succeeds) and field-data (populated only when
        the URL has CrUX coverage). Cached per (url, strategy).
        """
        if not self.is_configured:
            raise PSINotConfigured(
                "GOOGLE_PSI_API_KEY not set; PSI is unavailable."
            )

        cache_key = f"{strategy}|{url}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "url": url,
            "key": self.settings.GOOGLE_PSI_API_KEY,
            "strategy": strategy,
            "category": ["performance", "accessibility", "best-practices", "seo"],
        }
        try:
            response = await self.client.get(
                "/pagespeedonline/v5/runPagespeed",
                params=params,
            )
        except httpx.HTTPError as exc:
            result = _empty_result(url, strategy, fetch_status="fetch_error", error=str(exc))
            self._cache[cache_key] = result
            return result

        if response.status_code >= 400:
            result = _empty_result(
                url,
                strategy,
                fetch_status="fetch_error",
                error=f"HTTP {response.status_code}",
            )
            self._cache[cache_key] = result
            return result

        data = response.json()
        result = _result_from_psi_payload(data, url=url, strategy=strategy)
        self._cache[cache_key] = result
        return result


# ─── Parser ─────────────────────────────────────────────────────────────────


def _empty_result(
    url: str,
    strategy: PSIStrategy,
    *,
    fetch_status: str,
    error: str | None = None,
) -> PSIResult:
    return PSIResult(
        url=url,
        strategy=strategy,
        fetch_status=fetch_status,
        performance_score=None,
        accessibility_score=None,
        best_practices_score=None,
        seo_score=None,
        lcp_ms=None,
        fcp_ms=None,
        tbt_ms=None,
        cls=None,
        speed_index_ms=None,
        tti_ms=None,
        ttfb_ms=None,
        crux_lcp_ms=None,
        crux_inp_ms=None,
        crux_cls=None,
        crux_ttfb_ms=None,
        has_field_data=False,
        audit_viewport_pass=None,
        audit_font_size_pass=None,
        audit_tap_targets_pass=None,
        audit_content_width_pass=None,
        error=error,
    )


def _result_from_psi_payload(
    data: dict[str, Any],
    *,
    url: str,
    strategy: PSIStrategy,
) -> PSIResult:
    """Walk the PSI v5 response into our trimmed PSIResult shape."""
    lighthouse = data.get("lighthouseResult") or {}
    runtime_error = lighthouse.get("runtimeError") or {}
    if runtime_error.get("code"):
        return _empty_result(
            url,
            strategy,
            fetch_status="lighthouse_error",
            error=runtime_error.get("message") or runtime_error.get("code"),
        )

    cats = lighthouse.get("categories") or {}
    audits = lighthouse.get("audits") or {}

    perf = (cats.get("performance") or {}).get("score")
    a11y = (cats.get("accessibility") or {}).get("score")
    bp = (cats.get("best-practices") or {}).get("score")
    seo = (cats.get("seo") or {}).get("score")

    def _audit_ms(key: str) -> float | None:
        a = audits.get(key) or {}
        v = a.get("numericValue")
        return float(v) if v is not None else None

    def _audit_value(key: str) -> float | None:
        a = audits.get(key) or {}
        v = a.get("numericValue")
        return float(v) if v is not None else None

    def _audit_pass(key: str) -> bool | None:
        """Boolean pass/fail of a Lighthouse audit. None if absent."""
        a = audits.get(key)
        if not a:
            return None
        score = a.get("score")
        if score is None:
            return None
        try:
            return float(score) >= 0.9
        except (TypeError, ValueError):
            return None

    # CrUX field data lives in loadingExperience for the target URL,
    # originLoadingExperience for the origin (used as fallback). We
    # prefer loadingExperience and only fall back to origin if the URL
    # has no CrUX coverage.
    field_data: dict[str, Any] | None = None
    le = data.get("loadingExperience") or {}
    le_metrics = le.get("metrics") or {}
    if le_metrics:
        field_data = le_metrics
    else:
        ole = data.get("originLoadingExperience") or {}
        ole_metrics = ole.get("metrics") or {}
        if ole_metrics:
            field_data = ole_metrics

    def _crux_ms(key: str) -> float | None:
        if not field_data:
            return None
        m = field_data.get(key) or {}
        v = m.get("percentile")
        return float(v) if v is not None else None

    crux_lcp = _crux_ms("LARGEST_CONTENTFUL_PAINT_MS")
    crux_inp = _crux_ms("INTERACTION_TO_NEXT_PAINT")
    crux_cls_raw = _crux_ms("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    # CrUX returns CLS percentile multiplied by 100; convert back to unitless.
    crux_cls = crux_cls_raw / 100.0 if crux_cls_raw is not None else None
    crux_ttfb = _crux_ms("EXPERIMENTAL_TIME_TO_FIRST_BYTE")

    def _audit_int(key: str) -> int | None:
        a = audits.get(key) or {}
        v = a.get("numericValue")
        return int(v) if v is not None else None

    total_byte_weight = _audit_int("total-byte-weight")
    image_bytes: int | None = None
    _rs_items = ((audits.get("resource-summary") or {}).get("details") or {}).get("items") or []
    for _it in _rs_items:
        if _it.get("resourceType") == "image":
            _tb = _it.get("transferSize")
            image_bytes = int(_tb) if _tb is not None else None
            break

    return PSIResult(
        url=url,
        strategy=strategy,
        fetch_status="ok",
        performance_score=float(perf) if perf is not None else None,
        accessibility_score=float(a11y) if a11y is not None else None,
        best_practices_score=float(bp) if bp is not None else None,
        seo_score=float(seo) if seo is not None else None,
        lcp_ms=_audit_ms("largest-contentful-paint"),
        fcp_ms=_audit_ms("first-contentful-paint"),
        tbt_ms=_audit_ms("total-blocking-time"),
        cls=_audit_value("cumulative-layout-shift"),
        speed_index_ms=_audit_ms("speed-index"),
        tti_ms=_audit_ms("interactive"),
        ttfb_ms=_audit_ms("server-response-time"),
        crux_lcp_ms=crux_lcp,
        crux_inp_ms=crux_inp,
        crux_cls=crux_cls,
        crux_ttfb_ms=crux_ttfb,
        has_field_data=field_data is not None,
        # Modern Lighthouse exposes viewport via the new -insight name.
        # Old keys (viewport, font-size, tap-targets, content-width) are
        # gone from PSI; we leave those at None and let downstream
        # extractors check viewport meta directly from cached HTML.
        audit_viewport_pass=(
            _audit_pass("viewport-insight")
            or _audit_pass("viewport")
        ),
        audit_font_size_pass=None,
        audit_tap_targets_pass=None,
        audit_content_width_pass=None,
        total_byte_weight_bytes=total_byte_weight,
        image_bytes=image_bytes,
        error=None,
    )
