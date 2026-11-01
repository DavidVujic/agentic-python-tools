PROJECT_KERNEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS kernels (
    kernel_name     TEXT PRIMARY KEY,
    connection_file TEXT NOT NULL,
    project_path    TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
