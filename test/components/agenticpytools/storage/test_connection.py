"""Unit tests for the sqlite connection factory."""

import pytest
from agenticpytools.storage import connection

pytestmark = pytest.mark.storage


def test_get_conn_creates_db(tmp_path, monkeypatch):
    db_path = tmp_path / "sub" / "kernels.db"
    monkeypatch.setattr(connection, "DB_PATH", db_path)

    conn = connection.get_conn()

    try:
        assert db_path.exists()

        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        assert "kernels" in tables
    finally:
        conn.close()
