import sqlite3
from pathlib import Path

from agenticpytools.storage.schema import PROJECT_KERNEL_SCHEMA

DB_PATH = Path.home() / ".python-repl-mcp" / "kernels.db"


def get_conn() -> sqlite3.Connection:
    """Open a connection with sane settings. Caller owns it (use as context manager)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(PROJECT_KERNEL_SCHEMA)

    return conn
