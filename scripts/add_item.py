#!/usr/bin/env python3
"""Register a single item, its assessment, and optional image paths."""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection
from src.risk_score import calculate


def add_item(data: dict, assessment: dict = None, images: list[dict] = None, db_path=None) -> int:
    conn = get_connection(db_path) if db_path else get_connection()
    cur = conn.cursor()

    item_fields = [
        "name", "category", "material", "estimated_period", "estimated_origin",
        "size_description", "weight_g", "price", "currency", "seller",
        "source_url", "acquired_date", "description", "condition", "accessories",
        "has_certificate", "certificate_issuer", "returnable",
    ]
    row = {k: data.get(k) for k in item_fields}
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    cur.execute(f"INSERT INTO items ({cols}) VALUES ({placeholders})", list(row.values()))
    item_id = cur.lastrowid

    if assessment:
        assessment["item_id"] = item_id
        assessment["_item_price"] = data.get("price", 0)
        result = calculate(assessment)

        afields = [c for c in result if not c.startswith("_") and c not in ("purchase_advice",)]
        acols = ", ".join(afields)
        aph = ", ".join("?" for _ in afields)
        cur.execute(
            f"INSERT OR REPLACE INTO authenticity_assessments ({acols}) VALUES ({aph})",
            [result[f] for f in afields],
        )

    for img in (images or []):
        img["item_id"] = item_id
        fields = ["item_id", "filename", "file_path", "image_type", "source_url", "rights_info", "memo"]
        icols = ", ".join(f for f in fields if f in img)
        iph = ", ".join("?" for f in fields if f in img)
        cur.execute(
            f"INSERT INTO images ({icols}) VALUES ({iph})",
            [img[f] for f in fields if f in img],
        )

    conn.commit()
    conn.close()
    print(f"Item registered: id={item_id} name={data.get('name')}")
    return item_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a single item from JSON file")
    parser.add_argument("json_file", help="Path to JSON file with keys: item, assessment, images")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    add_item(
        data=payload.get("item", {}),
        assessment=payload.get("assessment"),
        images=payload.get("images"),
    )
