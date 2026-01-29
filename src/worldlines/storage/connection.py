"""SQLite connection management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Generator


@contextmanager
def get_connection(database_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    Commits on clean exit, rolls back on exception, and always closes.
    """
    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
