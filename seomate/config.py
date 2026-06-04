"""Audit configuration models and YAML loader.

Pydantic v2 models that mirror the schema documented in
docs/site-auditor-architecture.md §7.

Credentials are NEVER read from YAML — they come from environment
variables only (DATABASE_URL, DATAFORSEO_LOGIN, ANTHROPIC_API_KEY, etc.,
see .env.example for the full list). The YAML config describes WHAT to
audit; the env describes HOW to authenticate.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Audit-target sub-models ────────────────────────────────────────────────


class AuditSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(description="Bare domain, e.g. 'pixelettetech.com'")
    primary_url: str = Field(description="Canonical https URL of the homepage")
    business_type: str = Field(
        default="generic",
        description="Free-form classifier (e.g. 'saas-marketing', 'local-services').",
    )
    locales: list[str] = Field(
        default_factory=lambda: ["en-GB"],
        description="BCP-47 locale codes the site serves.",
    )
    disavow_domains: list[str] = Field(
        default_factory=list,
        description=(
            "Owner-supplied disavow file: domains the owner has disavowed in "
            "Google Search Console. Google exposes no read API for the disavow "
            "list, so this is the only path to measure P3-30. Leave empty when "
            "no disavow file has been submitted (P3-30 then reports N/A)."
        ),
    )

    @field_validator("primary_url")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("primary_url must include scheme (http:// or https://)")
        return v.rstrip("/")


class AuditBrand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    aliases: list[str] = Field(default_factory=list)
    legal_entities: list[str] = Field(default_factory=list)


class AuditGBP(BaseModel):
    """Optional. Populated only for sites with a Google Business Profile."""

    model_config = ConfigDict(extra="forbid")

    place_id: str | None = None


class AuditScope(BaseModel):
    """Filter which variables run."""

    model_config = ConfigDict(extra="forbid")

    pillars: Literal["all"] | list[Literal["P0", "P1", "P2", "P3", "P4", "P5", "P6"]] = "all"
    h1_stage: Literal["a", "b", "c", "d", "all"] = "all"
    skip_variables: list[str] = Field(
        default_factory=list,
        description="Explicit skip list, e.g. ['P6-27', 'P6-31']",
    )
    only_variables: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit allow-list. When non-empty, ONLY these variable IDs "
            "run; all others (including unrelated pillars) are skipped. "
            "Useful for validating a small batch of new extractors without "
            "paying the full audit cost."
        ),
    )


class AuditTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site: AuditSite
    brand: AuditBrand
    keywords_file: Path | None = Field(
        default=None,
        description="Path to keyword list YAML, relative to the config file's directory.",
    )
    competitors: list[str] = Field(default_factory=list)
    gbp: AuditGBP = Field(default_factory=AuditGBP)
    scope: AuditScope = Field(default_factory=AuditScope)


# ─── Run sub-models ──────────────────────────────────────────────────────────


class RateLimits(BaseModel):
    model_config = ConfigDict(extra="allow")  # adapter-name → rps

    dataforseo_rps: float = 5.0
    google_kg_rps: float = 10.0
    perplexity_rps: float = 1.0


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parallelism: int = Field(default=4, ge=1, le=32)
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    timeout_seconds: int = Field(default=300, ge=1)
    cost_cap_gbp: float = Field(default=5.00, ge=0.0)
    cost_warn_fraction: float = Field(default=0.80, gt=0.0, le=1.0)
    retain_raw_responses: bool = False
    log_dir: Path = Path("./data/logs")


# ─── Top-level config ────────────────────────────────────────────────────────


class SeoMateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit: AuditTarget
    run: RunConfig = Field(default_factory=RunConfig)


def load_config(path: Path) -> SeoMateConfig:
    """Load and validate a YAML config file.

    Resolves relative paths (e.g. ``keywords_file``) relative to the
    config file's directory, not the current working directory.
    """
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = SeoMateConfig.model_validate(raw)

    # Resolve relative keywords_file path against the config's directory
    if cfg.audit.keywords_file is not None and not cfg.audit.keywords_file.is_absolute():
        cfg.audit.keywords_file = (path.parent / cfg.audit.keywords_file).resolve()

    return cfg
