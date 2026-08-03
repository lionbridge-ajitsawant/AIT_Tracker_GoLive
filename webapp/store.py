"""SQLite-backed persistence for wizard drafts and provisioning jobs.

Replaces plain in-memory dicts so state survives an app restart and is
visible across threads (and worker processes, since SQLite arbitrates
access to the shared file). Each draft/job is stored as a single JSON blob
keyed by its id - callers still work with plain dicts, they just fetch and
save explicitly instead of mutating a shared in-memory reference.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

# Override in production (e.g. Azure App Service) to a path outside the
# deployed code directory, so the DB survives redeploys - see
# docs/HOSTING_SETUP.md.
DB_PATH = Path(os.getenv("WIZARD_DB_PATH", str(Path(__file__).resolve().parent / "state.db")))

_local = threading.local()


def _conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        # WAL lets readers and one writer proceed concurrently (multiple gunicorn
        # threads/workers hitting the same file); NORMAL sync trades a small
        # durability window (an in-flight write could be lost on a hard crash)
        # for much lower write latency under concurrency - fine here since this
        # DB only holds transient wizard state, not the SharePoint data itself.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        _local.conn = conn
    return conn


def init_db():
    conn = _conn()
    conn.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.commit()


def _get(table, key):
    row = _conn().execute(f"SELECT data FROM {table} WHERE id = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def _set(table, key, value):
    conn = _conn()
    conn.execute(
        f"INSERT INTO {table} (id, data) VALUES (?, ?) "
        f"ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()


def get_draft(draft_id):
    return _get("drafts", draft_id)


def set_draft(draft_id, draft):
    _set("drafts", draft_id, draft)


def get_job(job_id):
    return _get("jobs", job_id)


def set_job(job_id, job):
    _set("jobs", job_id, job)
