"""SEOMATE CLI entry point."""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

app = typer.Typer(
    name="seomate",
    help="SEOMATE Site Auditor - H1 data capture layer.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


@app.command()
def version() -> None:
    """Print the auditor version."""
    from seomate import __version__

    typer.echo(f"seomate {__version__}")


@app.command()
def migrate(
    revision: str = typer.Option(
        "head",
        "--to",
        help="Alembic revision to upgrade to (default: head).",
    ),
) -> None:
    """Apply Alembic migrations against the configured Postgres database."""
    from alembic import command
    from alembic.config import Config

    from seomate.storage.db import get_settings

    auditor_root = Path(__file__).resolve().parent.parent
    alembic_ini = auditor_root / "alembic.ini"
    if not alembic_ini.exists():
        typer.echo(f"alembic.ini not found at {alembic_ini}", err=True)
        raise typer.Exit(code=1)

    settings = get_settings()
    typer.echo(f"Target: {_redact_url(settings.sqlalchemy_url)}")

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(auditor_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)

    command.upgrade(cfg, revision)
    typer.echo(f"Migrations applied to {revision}.")


@app.command(name="migrate-status")
def migrate_status() -> None:
    """Show the current Alembic revision and the latest available head."""
    from alembic import command
    from alembic.config import Config

    from seomate.storage.db import get_settings

    auditor_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(auditor_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(auditor_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_url)

    typer.echo("Current revision:")
    command.current(cfg, verbose=False)
    typer.echo("Latest available:")
    command.heads(cfg, verbose=False)


@app.command()
def audit(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to the YAML audit config.",
        exists=True,
        readable=True,
        resolve_path=True,
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
    only: str | None = typer.Option(
        None,
        "--only",
        help=(
            "Comma-separated list of variable IDs to run exclusively "
            "(e.g. 'P3-08,P3-15,P3-20'). Skips all other extractors "
            "AND the LLM evaluator phase if none of the listed vars "
            "depend on it. Use during dev to validate a small batch "
            "without paying the full ~5min audit cost."
        ),
    ),
) -> None:
    """Run an audit against the configured site."""
    from seomate.config import load_config
    from seomate.orchestrator import AuditOrchestrator
    from seomate.utils.logging import configure_logging

    cfg = load_config(config)
    if only:
        cfg.audit.scope.only_variables = [v.strip() for v in only.split(",") if v.strip()]

    log_dir = cfg.run.log_dir
    if not log_dir.is_absolute():
        log_dir = (config.parent / log_dir).resolve()

    # Defer log file creation until we have an audit_id; for the run
    # itself we log to stderr only. Per-audit log file lands in H1a
    # alongside richer telemetry.
    configure_logging(log_level=log_level)

    orch = AuditOrchestrator(cfg)
    audit_id = asyncio.run(orch.run())
    typer.echo(f"Audit complete: {audit_id}")


@app.command(name="ping-dataforseo")
def ping_dataforseo() -> None:
    """Smoke test the DataForSEO adapter against the configured environment.

    Calls the cheap user_data endpoint to verify auth + connectivity. Prints
    a redacted summary including which environment we hit (sandbox vs live)
    and the reported account balance.
    """
    import asyncio
    from decimal import Decimal
    from uuid import uuid4

    from seomate.adapters import (
        AdapterContext,
        DataForSEOAdapter,
        DataForSEOSettings,
    )
    from seomate.utils.cost_tracker import CostTracker

    async def _ping() -> int:
        try:
            settings = DataForSEOSettings()  # type: ignore[call-arg]
        except Exception as exc:
            typer.echo(
                f"Could not load DataForSEO settings: {exc}\n"
                "Make sure .env contains DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD.",
                err=True,
            )
            return 1

        env = "sandbox" if settings.DATAFORSEO_USE_SANDBOX else "LIVE"
        typer.echo(f"Environment: {env} ({settings.base_url})")
        typer.echo(f"Login:       {settings.DATAFORSEO_LOGIN}")
        typer.echo("")

        ctx = AdapterContext(
            audit_id=uuid4(),
            cost_tracker=CostTracker(cap_gbp=1.0, warn_fraction=0.99),
        )
        async with DataForSEOAdapter(ctx, settings=settings) as dfs:
            try:
                response = await dfs.get_user_data()
            except Exception as exc:
                typer.echo(f"Call failed: {type(exc).__name__}: {exc}", err=True)
                return 1

        status = response.get("status_message", "(no message)")
        tasks = response.get("tasks", []) or []
        typer.echo(f"Response status: {status}")

        if tasks:
            user_data = (tasks[0].get("result") or [{}])[0]
            balance = user_data.get("money", {}).get("balance")
            limits = user_data.get("rates", {})
            typer.echo("")
            typer.echo(f"Reported balance: USD {balance}")
            if limits:
                typer.echo(
                    f"Rate limits:      "
                    f"{limits.get('limits_per_minute', '?')} req/min, "
                    f"{limits.get('limits_per_hour', '?')} req/hr"
                )

        # Adapter-call telemetry (via the @tracked decorator)
        calls = ctx.drain_calls()
        if calls:
            call = calls[0]
            typer.echo("")
            typer.echo(
                f"Adapter call:    {call.endpoint} "
                f"({call.duration_ms} ms, GBP {call.cost_gbp})"
            )
        return 0

    raise typer.Exit(code=asyncio.run(_ping()))


@app.command(name="taxonomy-stats")
def taxonomy_stats(
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to o1-taxonomy.md (default: docs/o1-taxonomy.md in repo root).",
    ),
) -> None:
    """Parse the taxonomy and print structural counts for sanity-checking."""
    from seomate.taxonomy import Catalog

    catalog = Catalog.from_file(path)
    s = catalog.stats()

    typer.echo(f"Source:           {s['source_path']}")
    typer.echo(f"Version:          {s['version']}")
    typer.echo(f"Active variables: {s['active_variables']}")
    typer.echo(f"Removed:          {s['removed_variables']}")
    typer.echo(f"With Step 1.5:    {s['with_step_1_5']}")
    typer.echo("")
    typer.echo("By pillar:")
    for p in s["by_pillar"]:
        typer.echo(
            f"  {p['pillar_id']:<3} {p['name']:<40} "
            f"active={p['active']:<3} rules={p['with_rules']:<3} "
            f"removed={p['removed']}"
        )
    typer.echo("")
    typer.echo("By evidence weight:")
    for weight, count in sorted(s["by_weight"].items()):
        typer.echo(f"  {weight:<20} {count}")
    typer.echo("")
    typer.echo("Hard-dependency graph:")
    typer.echo(f"  vars with no hard deps:  {s['no_hard_deps']}")
    typer.echo(f"  max hard deps on one var: {s['max_hard_deps']}")
    typer.echo("  top 5 most-referenced:")
    for vid, count in s["top_referenced"]:
        typer.echo(f"    {vid}  referenced by {count} other vars")
    typer.echo("")
    typer.echo("Removed redirects:")
    for r in s["removed_redirects"]:
        typer.echo(f"  {r['from']}  ->  {r['into']}")
    typer.echo("")
    cycles = catalog.detect_cycles()
    if cycles:
        typer.echo(f"Cycle check: FAIL ({len(cycles)} cycle(s) detected)", err=True)
        for cycle in cycles:
            typer.echo(f"  {' -> '.join(cycle)}", err=True)
        raise typer.Exit(code=1)
    else:
        typer.echo("Cycle check: PASS (no hard-dependency cycles)")


@app.command()
def ingest(
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="Path to the session-produced audit JSON (see docs/ingest-contract.md).",
        exists=True,
        readable=True,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate the document and report counts, but write nothing to the DB.",
    ),
) -> None:
    """Ingest a Claude-session audit JSON into the SEOMATE database.

    The session performs the 226-variable diagnostic itself (using the
    taxonomy as its understanding) and emits one JSON document. This writes
    it as a normal audit so it shows on the dashboard. Reuses the same
    schema and capture contract as a natively-run audit.
    """
    from seomate.ingest import (
        IngestError,
        ingest_audit,
        load_payload,
        parse_payload,
    )

    try:
        payload = load_payload(file)
        audit_id, meta, captures = parse_payload(payload)
    except IngestError as exc:
        typer.echo("Ingest validation failed:", err=True)
        for problem in exc.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Site:             {meta['site_domain']}")
    typer.echo(f"Taxonomy version: {meta['taxonomy_version']}")
    typer.echo(f"Captures:         {len(captures)}")
    if dry_run:
        typer.echo("Dry run: document is valid; nothing written.")
        return

    written_id = asyncio.run(ingest_audit(payload))
    typer.echo(f"Ingest complete: {written_id}")


@app.command()
def inspect(
    audit_id: str = typer.Argument(..., help="Audit UUID to inspect."),
) -> None:
    """Print a structured summary of an audit by ID."""
    from sqlalchemy import select

    from seomate.storage import Audit, Capture, session_scope

    async def _inspect() -> None:
        async with session_scope() as s:
            audit_row = (
                await s.execute(select(Audit).where(Audit.audit_id == audit_id))
            ).scalar_one_or_none()
            if audit_row is None:
                typer.echo(f"No audit found for id={audit_id}", err=True)
                raise typer.Exit(code=1)

            captures = (
                await s.execute(select(Capture).where(Capture.audit_id == audit_id))
            ).scalars().all()

        typer.echo(f"Audit:        {audit_row.audit_id}")
        typer.echo(f"Site:         {audit_row.site_domain}")
        typer.echo(f"Status:       {audit_row.status}")
        typer.echo(f"Started:      {audit_row.started_at}")
        typer.echo(f"Completed:    {audit_row.completed_at}")
        typer.echo(f"Total cost:   GBP {audit_row.total_cost_gbp}")
        typer.echo(
            f"Captures:     {audit_row.variables_attempted} attempted "
            f"(passed={audit_row.variables_passed}, "
            f"failed={audit_row.variables_failed}, "
            f"partial={audit_row.variables_partial}, "
            f"error={audit_row.variables_errored}, "
            f"unmeasurable={audit_row.variables_unmeasurable})"
        )
        typer.echo("")
        typer.echo("Captures:")
        for c in captures:
            typer.echo(
                f"  {c.variable_id:<6} {c.pillar:<3} {c.status:<14} "
                f"{c.evidence_weight:<11} GBP {c.cost_incurred_gbp}"
            )

    asyncio.run(_inspect())


@app.command(name="audit-diff")
def audit_diff(
    audit_id_a: str = typer.Argument(..., help="Older audit UUID (baseline)."),
    audit_id_b: str = typer.Argument(..., help="Newer audit UUID (comparison)."),
) -> None:
    """Compare two audits variable-by-variable; flag changed outcomes.

    Used for the reliability question: when we re-run an audit, do
    extractors produce the same result? Anything in CHANGED is an
    extractor whose output is non-deterministic given identical
    inputs (or whose inputs themselves are unstable).
    """
    from sqlalchemy import select

    from seomate.storage import Capture, session_scope

    async def _diff() -> None:
        async with session_scope() as s:
            cap_a = (
                await s.execute(
                    select(Capture).where(Capture.audit_id == audit_id_a)
                )
            ).scalars().all()
            cap_b = (
                await s.execute(
                    select(Capture).where(Capture.audit_id == audit_id_b)
                )
            ).scalars().all()

        by_a = {c.variable_id: c for c in cap_a}
        by_b = {c.variable_id: c for c in cap_b}
        all_vars = sorted(set(by_a) | set(by_b))

        same_count = 0
        changed: list[tuple[str, str, str]] = []
        only_a: list[str] = []
        only_b: list[str] = []
        for vid in all_vars:
            a = by_a.get(vid)
            b = by_b.get(vid)
            if a is None:
                only_b.append(vid)
                continue
            if b is None:
                only_a.append(vid)
                continue
            if a.status == b.status:
                same_count += 1
            else:
                changed.append((vid, a.status, b.status))

        typer.echo(f"Audit A: {audit_id_a}")
        typer.echo(f"Audit B: {audit_id_b}")
        typer.echo("")
        typer.echo(f"Variables in both:  {len(by_a) & len(by_b)}")
        typer.echo(f"  unchanged status: {same_count}")
        typer.echo(f"  changed status:   {len(changed)}")
        typer.echo(f"Only in A: {len(only_a)}")
        typer.echo(f"Only in B: {len(only_b)}")
        typer.echo("")
        if changed:
            typer.echo("Status changes (variables whose outcome flipped):")
            for vid, sa, sb in changed:
                typer.echo(f"  {vid:<6}  {sa:<14} -> {sb}")
        if only_a:
            typer.echo("\nOnly in A:")
            for vid in only_a:
                typer.echo(f"  {vid}")
        if only_b:
            typer.echo("\nOnly in B:")
            for vid in only_b:
                typer.echo(f"  {vid}")

    asyncio.run(_diff())


@app.command(name="snapshot-save")
def snapshot_save(
    audit_id: str = typer.Argument(..., help="Audit UUID to snapshot."),
    out_path: Path = typer.Option(
        Path("tests/snapshots/pixelette.json"),
        "--out",
        help="JSON file to write the snapshot to (relative to the auditor/ dir or absolute).",
        resolve_path=True,
    ),
) -> None:
    """Save a per-variable snapshot of a known-good audit to disk.

    Captures variable_id + status + (selected, deterministic) value
    fields per capture, plus audit-level metadata. Used as the
    regression-test baseline: future audits can be checked with
    ``seomate snapshot-check`` to detect silent extractor regressions.
    """
    import json
    from sqlalchemy import select
    from seomate.storage import Audit, Capture, session_scope

    async def _save() -> None:
        async with session_scope() as s:
            audit = (
                await s.execute(select(Audit).where(Audit.audit_id == audit_id))
            ).scalar_one_or_none()
            if audit is None:
                typer.echo(f"audit {audit_id} not found", err=True)
                raise typer.Exit(code=1)
            caps = (
                await s.execute(select(Capture).where(Capture.audit_id == audit_id))
            ).scalars().all()

        rows = []
        for c in sorted(caps, key=lambda x: x.variable_id):
            value = c.value or {}
            rows.append(
                {
                    "variable_id": c.variable_id,
                    "status": c.status,
                    "pillar": c.pillar,
                    # Hash-friendly fields from value where present;
                    # avoid sample arrays / timestamps that drift.
                    "value_keys": sorted(value.keys()) if isinstance(value, dict) else [],
                    "rule_outcomes": [
                        {"id": r.get("rule_id"), "passed": r.get("passed")}
                        for r in (c.rules or [])
                    ],
                    "data_sources": list(c.data_sources_used or []),
                    "errors": list(c.errors or []) if c.errors else [],
                }
            )
        snapshot = {
            "audit_id": audit_id,
            "site_domain": audit.site_domain,
            "taxonomy_version": audit.taxonomy_version,
            "captured_at": audit.started_at.isoformat() if audit.started_at else None,
            "status": audit.status,
            "total_variables": len(rows),
            "variables": rows,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        typer.echo(f"Wrote snapshot: {out_path}")
        typer.echo(f"  variables: {len(rows)}")
        typer.echo(f"  audit_status: {audit.status}")

    asyncio.run(_save())


@app.command(name="snapshot-check")
def snapshot_check(
    audit_id: str = typer.Argument(..., help="Audit UUID to compare against the snapshot."),
    snapshot_path: Path = typer.Option(
        Path("tests/snapshots/pixelette.json"),
        "--snapshot",
        help="Snapshot file to compare against (relative to the auditor/ dir or absolute).",
        resolve_path=True,
    ),
    fail_on_diff: bool = typer.Option(
        True,
        "--fail-on-diff/--no-fail-on-diff",
        help="Exit non-zero if any variable's status differs from the snapshot.",
    ),
) -> None:
    """Compare an audit against a baseline snapshot and fail on drift.

    Detects the silent-regression class of bug: an audit that completes
    with no errors but produces different status outcomes than the
    known-good baseline (typically a sign of upstream data loss or
    extractor logic drift).
    """
    import json
    from sqlalchemy import select
    from seomate.storage import Capture, session_scope

    if not snapshot_path.exists():
        typer.echo(f"snapshot not found: {snapshot_path}", err=True)
        raise typer.Exit(code=2)

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    baseline = {v["variable_id"]: v for v in snapshot["variables"]}

    async def _check() -> None:
        async with session_scope() as s:
            caps = (
                await s.execute(select(Capture).where(Capture.audit_id == audit_id))
            ).scalars().all()
        current = {c.variable_id: c.status for c in caps}

        status_changes: list[tuple[str, str, str]] = []
        rule_outcome_drift: list[tuple[str, int, bool, bool]] = []
        new_in_audit: list[str] = []
        missing_in_audit: list[str] = []

        # Status drift
        for vid, base in baseline.items():
            if vid not in current:
                missing_in_audit.append(vid)
            elif current[vid] != base["status"]:
                status_changes.append((vid, base["status"], current[vid]))

        for vid in current:
            if vid not in baseline:
                new_in_audit.append(vid)

        # Rule-outcome drift (same status, different rule pass/fails)
        for c in caps:
            base = baseline.get(c.variable_id)
            if base is None or c.status != base["status"]:
                continue
            base_rules = {r["id"]: r["passed"] for r in base.get("rule_outcomes", [])}
            for cur_rule in (c.rules or []):
                rid = cur_rule.get("rule_id")
                cur_passed = cur_rule.get("passed")
                if rid in base_rules and base_rules[rid] != cur_passed:
                    rule_outcome_drift.append(
                        (c.variable_id, rid, base_rules[rid], cur_passed)
                    )

        typer.echo(f"Snapshot:    {snapshot_path}")
        typer.echo(f"  baseline:  {snapshot['audit_id']} ({len(baseline)} vars)")
        typer.echo(f"Comparing:   {audit_id} ({len(current)} vars)")
        typer.echo("")
        typer.echo(f"Status changes:        {len(status_changes)}")
        typer.echo(f"Rule-outcome drift:    {len(rule_outcome_drift)}")
        typer.echo(f"New in audit:          {len(new_in_audit)}")
        typer.echo(f"Missing in audit:      {len(missing_in_audit)}")

        if status_changes:
            typer.echo("\nStatus changes (silent-regression candidates):")
            for vid, base_s, cur_s in status_changes:
                typer.echo(f"  {vid:<8}  {base_s:<14} -> {cur_s}")

        if rule_outcome_drift:
            typer.echo("\nRule-outcome drift (same status, different per-rule pass/fail):")
            for vid, rid, base_p, cur_p in rule_outcome_drift:
                typer.echo(f"  {vid:<8}  rule {rid}: {base_p} -> {cur_p}")

        if missing_in_audit:
            typer.echo("\nMissing in audit (variables that were captured in baseline but not here):")
            for vid in missing_in_audit:
                typer.echo(f"  {vid}")

        if new_in_audit:
            typer.echo("\nNew in audit (not in baseline):")
            for vid in new_in_audit:
                typer.echo(f"  {vid}")

        has_drift = bool(status_changes or rule_outcome_drift or missing_in_audit)
        if has_drift and fail_on_diff:
            typer.echo("\nFAIL: drift detected vs snapshot baseline.")
            raise typer.Exit(code=1)
        typer.echo("\nOK: no drift vs snapshot baseline." if not has_drift else "")

    asyncio.run(_check())


def _redact_url(url: str) -> str:
    """Replace the password component in a SQLAlchemy URL for safe display."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{scheme}://{creds}@{host}"


if __name__ == "__main__":
    app()
