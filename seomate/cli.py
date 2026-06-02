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


@app.command(name="export-brief")
def export_brief(
    out: Path = typer.Option(
        Path("audit-brief.json"),
        "--out",
        "-o",
        help="Where to write the audit brief JSON.",
        resolve_path=True,
    ),
    path: Path | None = typer.Option(
        None,
        "--taxonomy-path",
        help="Path to o1-taxonomy.md (default: repo docs/o1-taxonomy.md).",
    ),
    llm_only: bool = typer.Option(
        False,
        "--llm-only",
        help=(
            "Scope the brief to ONLY the LLM-judgment variables (the hybrid "
            "path): a Claude session evaluates just those against their rubrics "
            "and merges the verdicts into a native audit via `ingest --merge-into`."
        ),
    ),
) -> None:
    """Export the taxonomy as an audit brief for a Claude session.

    The brief is the session's instruction set: per variable, its name,
    description, data sources, and Step 1.5 rules. With --llm-only it is scoped
    to the LLM-judgment variables for the session-driven hybrid (native does the
    deterministic vars; the session evaluates these for free). The session emits
    an ingest document (see docs/ingest-contract.md); `seomate ingest` (with
    --merge-into for the hybrid) writes it back to the dashboard.
    """
    import json

    from seomate.brief import LLM_JUDGMENT_VARIABLES, build_brief
    from seomate.taxonomy import Catalog

    catalog = Catalog.from_file(path)
    brief = build_brief(catalog, only=LLM_JUDGMENT_VARIABLES if llm_only else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    typer.echo(f"Wrote audit brief: {out}")
    typer.echo(f"  taxonomy version: {brief['taxonomy_version']}")
    typer.echo(f"  variables:        {brief['variable_count']}")
    typer.echo(f"  pillars:          {brief['pillars']}")
    typer.echo(f"  data sources:     {len(brief['data_sources'])}")


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
    merge_into: str | None = typer.Option(
        None,
        "--merge-into",
        help=(
            "HYBRID (canonical): merge these captures into an EXISTING native "
            "audit by UUID, replacing the matching variables in place , e.g. "
            "session-evaluated LLM-judgment vars from `export-brief --llm-only`. "
            "Does not create a new audit; recomputes the audit's outcome counts."
        ),
    ),
) -> None:
    """Ingest a Claude-session audit JSON into the SEOMATE database.

    Two modes:
      * --merge-into <audit_id> (CANONICAL hybrid): merge session-evaluated
        captures (the LLM-judgment variables) into an existing native audit,
        replacing those variables in place. This is the sanctioned way to fill
        the LLM vars for free with a Claude session instead of the paid API.
      * default (NON-CANONICAL / testing): write a brand-new audit from a
        full session-judged document. Mislabel-prone (it produced 26 mislabels
        in June 2026, purged); for experiments/fixtures only. Native
        ``seomate audit`` is the source of truth for a full run.
    """
    from seomate.ingest import (
        IngestError,
        ingest_audit,
        load_payload,
        merge_captures_into_audit,
        parse_payload,
    )

    try:
        payload = load_payload(file)
    except IngestError as exc:
        typer.echo("Ingest load failed:", err=True)
        for problem in exc.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(code=1) from exc

    # ── Canonical hybrid: merge session-evaluated vars into a native audit ──
    if merge_into:
        n = len(payload.get("captures") or [])
        typer.echo(f"Merge into audit: {merge_into}")
        typer.echo(f"Captures to merge: {n}")
        if dry_run:
            typer.echo("Dry run: not written (validation runs on apply).")
            return
        try:
            result = asyncio.run(merge_captures_into_audit(merge_into, payload))
        except IngestError as exc:
            typer.echo("Merge validation failed:", err=True)
            for problem in exc.problems:
                typer.echo(f"  - {problem}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(
            f"Merged {result['merged']} captures into {result['audit_id']} "
            f"(audit now {result['total_captures']} captures)."
        )
        return

    # ── Default: full new audit (non-canonical / testing) ──
    try:
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

    typer.secho(
        "WARNING: full manual ingest is the NON-CANONICAL path. The native "
        "`seomate audit` (weekly cron) is the source of truth; full session-judged "
        "ingests are mislabel-prone. For the LLM vars, prefer --merge-into.",
        err=True,
        fg=typer.colors.YELLOW,
    )
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


@app.command()
def gather(
    domain: str = typer.Option(
        ...,
        "--domain",
        "-d",
        help="Target domain to audit, e.g. 'abcd.com' (scheme/www optional).",
    ),
    out: Path = typer.Option(
        Path("audit-cache"),
        "--out",
        "-o",
        help="Directory to write the gathered data + manifest.json.",
        resolve_path=True,
    ),
    location_code: int | None = typer.Option(
        None,
        "--location-code",
        help="DataForSEO location code override (default: derived from the domain TLD; UK=2826, US=2840).",
    ),
) -> None:
    """Gather every reachable data source for DOMAIN into a cache directory.

    This is the deterministic data-collection half of the agent-driven audit.
    A Claude session runs this, then reads the cache + the export-brief, applies
    per-variable judgment, and emits an ingest document.

    Auto-derives keyword seeds (from the site's own pages) and market (from the
    TLD). Each source reports availability honestly: anything unconfigured or
    failing is recorded ``unavailable`` so the session marks dependent variables
    ``unmeasurable`` rather than guessing.

    Sources: page crawl + link graph, robots/llms.txt, PageSpeed, CrUX, Wayback,
    Knowledge Graph, and (when keys are set) DataForSEO SERP/Labs/Business/
    backlinks + Google Search Console.
    """
    from seomate.agent import gather as run_gather

    market_override = {"location_code": location_code, "country": "?", "label": f"override({location_code})"} if location_code else None
    result = asyncio.run(run_gather(domain, out, market_override=market_override))

    typer.echo(f"Domain:   {result.domain}")
    typer.echo(f"Market:   {result.market.get('label')} (location_code {result.market.get('location_code')})")
    typer.echo(f"Out dir:  {result.out_dir}")
    typer.echo(f"Cost:     £{result.total_cost_gbp}")
    typer.echo("")
    typer.echo("Sources available:")
    for name in result.available_sources:
        typer.echo(f"  [ok]   {name}")
    if result.unavailable_sources:
        typer.echo("Sources unavailable (dependent variables -> unmeasurable):")
        for name, reason in result.unavailable_sources.items():
            typer.echo(f"  [skip] {name}: {reason}")
    typer.echo("")
    typer.echo(f"Wrote {result.out_dir / 'manifest.json'}. Next: read the manifest + brief, evaluate, then `seomate ingest`.")


@app.command(name="plan-fixes")
def plan_fixes_cmd(
    audit_id: str = typer.Argument(..., help="The audit UUID to plan fixes for (from `seomate inspect` / the dashboard)."),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Write the full plan JSON here (default: print a summary only).",
        resolve_path=True,
    ),
) -> None:
    """Build a remediation plan from a completed audit's failed/partial captures.

    The diagnostic -> execution handoff. Joins each actionable finding with its
    remediation spec (how to fix it, what it needs, how to verify) and prints a
    prioritised plan grouped by who can action it: session-automatable wins
    first, then owner/human/offsite/budget. Writes nothing to the site , this
    produces the work orders an executor (a fixing session or a human) consumes.
    """
    import json

    from seomate.agent import plan_fixes

    try:
        plan = asyncio.run(plan_fixes(audit_id))
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"Site:               {plan['site_domain']}")
    typer.echo(f"Audit:              {plan['audit_id']}")
    typer.echo(f"Actionable findings: {plan['actionable_findings']} (failed + partial)")
    typer.echo("")
    typer.echo("By who can action it:")
    for cls, n in sorted(plan["by_fix_class"].items()):
        typer.echo(f"  {cls:8} {n}")
    typer.echo("")
    typer.echo(f"Session-automatable now ({len(plan['session_automatable'])}): {', '.join(plan['session_automatable']) or 'none'}")
    if plan["needs_remediation_authoring"]:
        typer.echo(f"No authored spec yet ({len(plan['needs_remediation_authoring'])}): {', '.join(plan['needs_remediation_authoring'])}")
    typer.echo("")
    typer.echo("Top work orders (prioritised):")
    for w in plan["work_orders"][:12]:
        r = w["remediation"]
        typer.echo(f"  [{r['fix_class']}/{'auto' if r['automatable'] else 'manual'}] {w['variable_id']} ({w['diagnostic_status']}) , {r['concrete_change'][:90]}")

    if out:
        out.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        typer.echo("")
        typer.echo(f"Full plan -> {out}")


@app.command(name="apply-fixes")
def apply_fixes_cmd(
    audit_id: str = typer.Argument(..., help="The audit UUID to generate fix artifacts for."),
    cache: Path = typer.Option(
        ...,
        "--cache",
        "-c",
        help="The gather cache directory for this site (from `seomate gather`).",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Write the full apply manifest JSON here.", resolve_path=True,
    ),
    target_repo: str | None = typer.Option(
        None, "--target-repo",
        help="GATED: GitHub repo 'owner/name' of the AUDITED SITE to open a fix PR against. Needs GITHUB_TOKEN env with write access. Omit to stay in propose mode.",
    ),
    apply: bool = typer.Option(
        False, "--apply",
        help="GATED: actually open the draft PR (requires --target-repo + GITHUB_TOKEN). Without it, the target step is a dry run.",
    ),
    allow_stale: bool = typer.Option(
        False, "--allow-stale",
        help="Override the guard that refuses to apply against a non-latest audit for the domain. Use only deliberately.",
    ),
) -> None:
    """Generate concrete fix artifacts for an audit's automatable findings.

    Default (no --target-repo): PROPOSE mode , builds the real artifacts
    (llms.txt body, sitemap priority map, JSON-LD blocks, orphan link plan) from
    the gather cache, writes nothing.

    With --target-repo (GATED): opens a DRAFT pull request against the audited
    site's repo with the auto-applyable file artifacts + a review checklist for
    the rest. Token comes from GITHUB_TOKEN env (never a CLI arg). Defaults to a
    dry run; pass --apply to actually open the PR. Never commits to the default
    branch, never auto-merges , a human reviews + merges, then you re-audit.
    """
    import json
    import os

    from seomate.agent import build_apply_manifest, plan_fixes

    try:
        plan = asyncio.run(plan_fixes(audit_id))
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e

    manifest = build_apply_manifest(plan, cache)

    typer.echo(f"Site:                {manifest['site_domain']}")
    typer.echo(f"Audit:               {manifest['audit_id']}")
    typer.echo(f"Mode:                {manifest['mode']} (no writes to the target site)")
    typer.echo(f"Artifacts generated: {manifest['artifacts_generated']}")
    typer.echo(f"Manual work orders:  {manifest['manual_work_orders']}")
    typer.echo("")
    typer.echo("Generated fix artifacts (review, then apply with site access):")
    for a in manifest["generated"]:
        typer.echo(f"  [{a['variable_id']}] -> {a['apply_to']}  ({a['artifact_kind']})")
        typer.echo(f"      verify: {a['verify']}")

    if out:
        out.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        typer.echo("")
        typer.echo(f"Full apply manifest -> {out}")

    # ── GATED: target-site apply ──────────────────────────────────────────────
    if target_repo:
        from seomate.agent.target import GitHubPRTarget

        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            typer.echo("\n--target-repo given but GITHUB_TOKEN is not set; cannot apply.", err=True)
            raise typer.Exit(code=1)
        if manifest.get("is_latest_audit") is False:
            typer.echo(f"\nNOTE: audit {manifest['audit_id'][:8]} is NOT the latest for {manifest['site_domain']} (latest: {str(manifest.get('latest_audit_id'))[:8]}).", err=True)
        try:
            tgt = GitHubPRTarget(target_repo, token, dry_run=not apply, allow_stale=allow_stale)
            res = asyncio.run(tgt.apply(manifest))
        except ValueError as e:
            typer.echo(f"\ntarget error: {e}", err=True)
            raise typer.Exit(code=1) from e

        typer.echo("")
        typer.echo(f"Target:   {res.repo}  (branch {res.branch})")
        typer.echo(f"Apply:    {'DRY RUN' if res.dry_run else 'LIVE'}")
        typer.echo(f"Files to write: {', '.join(res.files_written) or 'none'}")
        typer.echo(f"Needs manual integration: {len(res.manual_checklist)}")
        if res.errors:
            for e in res.errors:
                typer.echo(f"  error: {e}", err=True)
        if res.pr_url:
            typer.echo(f"Draft PR: {res.pr_url}")
        typer.echo(res.note)


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
