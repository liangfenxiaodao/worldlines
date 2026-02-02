"""Read-only SQLite connection for the web process."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Generator


@contextmanager
def get_readonly_connection(database_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Open a read-only SQLite connection with WAL mode.

    Uses URI mode to enforce read-only access. Sets query_only pragma
    as an additional safeguard. Yields the connection and closes on exit.
    """
    conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
