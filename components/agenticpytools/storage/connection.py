import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from agenticpytools.storage.schema import PROJECT_KERNEL_SCHEMA

DB_PATH = Path.home() / ".python-repl-mcp" / "kernels.db"
TRANSACTION_TIMEOUT = 120


def get_conn(timeout: float = 10) -> sqlite3.Connection:
    """Open a connection with sane settings. Caller owns it (use as context manager)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    # No journal_mode=WAL switch: it fails, without waiting, while another process holds a lock.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(PROJECT_KERNEL_SCHEMA)

    return conn


@contextmanager
def transaction() -> Generator[sqlite3.Connection]:
    """Hold the database write lock for the block, across threads and processes.

    Writes inside the block must use the yielded connection: another one would wait on this lock.
    All writers are serialized, so kernel starts of different sessions wait on each other.
    """
    conn = get_conn(timeout=TRANSACTION_TIMEOUT)

    try:
        conn.execute("BEGIN IMMEDIATE")

        with conn:
            yield conn
    finally:
        conn.close()
