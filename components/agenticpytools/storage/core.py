"""Sqlite-backed kernel registry.

Writes accept the connection of an open transaction, and otherwise open their own.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from agenticpytools.storage.connection import get_conn


@contextmanager
def _connection(conn: sqlite3.Connection | None) -> Generator[sqlite3.Connection]:
    if conn is not None:
        yield conn
        return

    with get_conn() as new_conn:
        yield new_conn


def load_entry(kernel_name: str, conn: sqlite3.Connection | None = None) -> dict | None:
    with _connection(conn) as c:
        row = c.execute(
            "SELECT kernel_name, connection_file, project_path "
            "FROM kernels WHERE kernel_name = ?",
            (kernel_name,),
        ).fetchone()
    return dict(row) if row else None


def save_entry(
    kernel_name: str,
    connection_file: str,
    project_path: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    with _connection(conn) as c:
        c.execute(
            """INSERT INTO kernels (kernel_name, connection_file, project_path)
               VALUES (?, ?, ?)
               ON CONFLICT(kernel_name) DO UPDATE SET
                   connection_file = excluded.connection_file,
                   project_path    = excluded.project_path,
                   updated_at      = datetime('now')""",
            (kernel_name, connection_file, project_path),
        )


def delete_entry(kernel_name: str, conn: sqlite3.Connection | None = None) -> None:
    with _connection(conn) as c:
        c.execute("DELETE FROM kernels WHERE kernel_name = ?", (kernel_name,))


def list_entries() -> list[dict]:
    """Handy for a future 'status' tool."""
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute("SELECT * FROM kernels ORDER BY updated_at DESC")
        ]
