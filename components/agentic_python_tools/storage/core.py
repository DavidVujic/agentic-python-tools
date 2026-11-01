"""Sqlite-backed kernel registry."""

from agentic_python_tools.storage.connection import get_conn


def load_entry(kernel_name: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT kernel_name, connection_file, project_path "
            "FROM kernels WHERE kernel_name = ?",
            (kernel_name,),
        ).fetchone()
    return dict(row) if row else None


def save_entry(kernel_name: str, connection_file: str, project_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO kernels (kernel_name, connection_file, project_path)
               VALUES (?, ?, ?)
               ON CONFLICT(kernel_name) DO UPDATE SET
                   connection_file = excluded.connection_file,
                   project_path    = excluded.project_path,
                   updated_at      = datetime('now')""",
            (kernel_name, connection_file, project_path),
        )
        conn.commit()


def delete_entry(kernel_name: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM kernels WHERE kernel_name = ?", (kernel_name,))
        conn.commit()


def list_entries() -> list[dict]:
    """Handy for a future 'status' tool."""
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute("SELECT * FROM kernels ORDER BY updated_at DESC")
        ]
