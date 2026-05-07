#!/usr/bin/env python3
"""Initialize the SQLite database with the full schema."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection, DB_PATH
from src.models import SCHEMA_SQL


def init(db_path=None):
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"Database initialized: {path}")


if __name__ == "__main__":
    init()
