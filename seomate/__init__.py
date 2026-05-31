"""SEOMATE Site Auditor — H1 data capture layer."""
from __future__ import annotations

import asyncio
import sys

__version__ = "0.1.0"

# psycopg's async mode is incompatible with Python's default ProactorEventLoop
# on Windows: SQLAlchemy raises psycopg.InterfaceError on connect. Switching to
# SelectorEventLoop fixes async DB access and is harmless for sync code paths.
# Set the policy as early as possible — before any asyncio loop is created.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
