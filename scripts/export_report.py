#!/usr/bin/env python3
"""Export a Markdown authenticity/risk report for one or more items."""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.report_writer import generate
from src.db import get_connection


def main():
    parser = argparse.ArgumentParser(description="Export Markdown report for an item")
    parser.add_argument("item_ids", nargs="*", type=int, help="Item IDs to export (omit for all)")
    parser.add_argument("--all", action="store_true", help="Export reports for all items")
    args = parser.parse_args()

    if args.all or not args.item_ids:
        conn = get_connection()
        ids = [r["id"] for r in conn.execute("SELECT id FROM items ORDER BY id").fetchall()]
        conn.close()
    else:
        ids = args.item_ids

    for item_id in ids:
        try:
            path = generate(item_id)
            print(f"Report saved: {path}")
        except Exception as e:
            print(f"Error for item {item_id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
