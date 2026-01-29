"""Storage layer — SQLite database access and schema management."""

from worldlines.storage.connection import get_connection
from worldlines.storage.schema import init_db

__all__ = ["get_connection", "init_db"]
