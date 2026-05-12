"""Database connection management."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "antiques.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def dict_from_row(row: sqlite3.Row) -> dict:
    return dict(row) if row else {}
