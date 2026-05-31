# SEOMATE Auditor

The Site Auditor (H1) — Python data capture layer.

Single writer to the shared Postgres + pgvector database. CLI-driven.

## Layout

```
auditor/
├── pyproject.toml
├── alembic.ini                  # (added in Day 2)
├── alembic/                     # migrations (added in Day 2)
├── seomate/
│   ├── __init__.py
│   ├── cli.py                   # `seomate audit | inspect | smoke | migrate`
│   ├── config.py                # YAML + env loader
│   ├── orchestrator.py          # audit lifecycle
│   ├── data_contract.py         # CaptureRecord, RuleResult, enums
│   ├── storage/                 # SQLAlchemy models, repository
│   ├── adapters/                # external API clients
│   ├── pillars/                 # one module per pillar
│   ├── taxonomy/                # parser for o1-taxonomy.md
│   ├── composition/             # internal computation modules
│   └── utils/
├── tests/
├── configs/
│   ├── pixelette.yml
│   └── pixelette-keywords.yml
└── data/                        # gitignored — logs and SQLite-ish artefacts
```

## Setup (will be filled in during Foundation week)

```bash
# from repo root
docker compose up -d            # boot Postgres+pgvector

cd auditor
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ".[dev]"

seomate migrate                 # apply Alembic migrations
seomate audit --config=configs/pixelette.yml
```

---

## Multi-Repo Layout

This repo is one of three sibling repos that together form **SEOMATE Phase 1**:

| Repo | What |
|---|---|
| [`temurkhan13/seomate-ai`](https://github.com/temurkhan13/seomate-ai) | Auditor pipeline (Python CLI). Sole writer to the shared Postgres. Carries `docs/o1-taxonomy.md`. |
| [`temurkhan13/seomate-be`](https://github.com/temurkhan13/seomate-be) | Read-only FastAPI serving the inspection UI. Imports SQLAlchemy models from `seomate-ai`. |
| [`temurkhan13/seomate-fe`](https://github.com/temurkhan13/seomate-fe) | Next.js 16 + React 19 inspection UI. Talks to `seomate-be` over HTTP. |

**Original monorepo** (preserves the full 50-commit build history): [`h-chishty/seomate`](https://github.com/h-chishty/seomate). Handover authored 2026-05-15 by Humza Chishty. See `HANDOVER.md` and `ROADMAP.md` in this repo for full context, architecture, deferred work, and Phase 2/3 plans.

### Local dev across all three

Clone them as siblings under one parent directory:

```bash
mkdir seomate && cd seomate
git clone https://github.com/temurkhan13/seomate-ai.git
git clone https://github.com/temurkhan13/seomate-be.git
git clone https://github.com/temurkhan13/seomate-fe.git
```

Then per the setup notes above, `seomate-be` installs `seomate-ai` as an editable sibling: `pip install -e ../seomate-ai`.

`docker-compose.yml` lives in `seomate-be`; it boots the Postgres + pgvector instance that both the auditor and the API talk to.
