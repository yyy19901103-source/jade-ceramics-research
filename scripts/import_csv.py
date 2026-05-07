#!/usr/bin/env python3
"""Import CSV files into the database.

Supported CSV types (detected by filename prefix):
  items_*.csv            → items table + authenticity_assessments
  references_*.csv       → references_ table
  fake_features_*.csv    → fake_features table
  auctions_*.csv         → auctions table
  images_*.csv           → images table
"""
import sys
import csv
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection
from src.risk_score import calculate

ITEM_FIELDS = {
    "name", "category", "material", "estimated_period", "estimated_origin",
    "size_description", "weight_g", "price", "currency", "seller",
    "source_url", "acquired_date", "description", "condition", "accessories",
    "has_certificate", "certificate_issuer", "returnable",
}

ASSESSMENT_FLAGS = {
    "no_certificate", "expensive_no_cert", "unknown_cert_issuer",
    "unclear_cert_image", "cert_item_mismatch", "no_provenance", "no_source_url",
    "weak_seller_info", "no_return", "few_transactions", "bad_reviews",
    "multi_site_selling", "photo_reuse_suspected", "below_market_price",
    "expensive_no_evidence", "inflated_keywords", "vague_price_explanation",
    "few_photos", "front_only", "no_side_bottom_closeup", "no_damage_explanation",
    "no_transmitted_light", "no_uv_photo", "low_resolution",
    "color_correction_suspected", "vague_description", "strong_selling_keywords",
    "vague_material", "no_period_basis", "no_origin_basis", "no_size_weight",
    "processing_suspected", "resin_suspected", "dyeing_suspected", "acid_suspected",
    "wax_oil_suspected", "substitute_material_suspected", "too_uniform_color",
    "unnatural_gloss", "unnatural_internal", "antique_fake_suspected",
    "artificial_soil_suspected", "artificial_aging_suspected", "modern_tool_marks",
    "unnatural_wear", "ancient_no_provenance", "excavated_no_legality",
    "no_foot_photo", "no_glaze_closeup", "no_repair_explanation",
    "no_mark_box_correspondence", "no_kiln_basis", "ceramic_expensive_no_evidence",
    "has_reliable_certificate", "major_auction_history", "museum_publication",
    "has_return_guarantee", "sufficient_hq_photos", "has_special_photos",
    "seller_established", "clear_provenance",
    "authenticity_probability", "reasoning",
}


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except ValueError:
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _bool(v):
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return 1 if v.strip().lower() in ("1", "true", "yes", "はい") else 0
    return 0


def import_items(rows: list[dict], conn):
    count = 0
    for row in rows:
        item = {}
        for k in ITEM_FIELDS:
            if k in row:
                v = row[k]
                if k in ("weight_g", "price"):
                    item[k] = _float(v)
                elif k in ("has_certificate", "returnable"):
                    item[k] = _bool(v)
                else:
                    item[k] = v or None

        cols = ", ".join(item.keys())
        ph = ", ".join("?" for _ in item)
        cur = conn.execute(f"INSERT INTO items ({cols}) VALUES ({ph})", list(item.values()))
        item_id = cur.lastrowid

        assessment = {"item_id": item_id, "_item_price": item.get("price", 0)}
        has_assessment = False
        for k in ASSESSMENT_FLAGS:
            if k in row and row[k] not in (None, ""):
                v = row[k]
                assessment[k] = _bool(v) if k not in ("authenticity_probability", "reasoning") else v
                has_assessment = True

        if has_assessment:
            result = calculate(assessment)
            afields = [c for c in result if not c.startswith("_") and c not in ("purchase_advice",)]
            acols = ", ".join(afields)
            aph = ", ".join("?" for _ in afields)
            conn.execute(
                f"INSERT OR REPLACE INTO authenticity_assessments ({acols}) VALUES ({aph})",
                [result[f] for f in afields],
            )
        count += 1
    return count


def import_references(rows: list[dict], conn):
    fields = ["title", "author", "year", "ref_type", "url", "pdf_path",
              "summary", "key_points", "related_fake_features", "related_materials", "reliability"]
    count = 0
    for row in rows:
        r = {k: row.get(k) or None for k in fields if k in row}
        if "year" in r:
            r["year"] = _int(r["year"])
        if "reliability" in r:
            r["reliability"] = _int(r["reliability"])
        cols = ", ".join(r.keys())
        ph = ", ".join("?" for _ in r)
        conn.execute(f"INSERT INTO references_ ({cols}) VALUES ({ph})", list(r.values()))
        count += 1
    return count


def import_fake_features(rows: list[dict], conn):
    fields = ["feature_name", "target_category", "description", "observation_method",
              "judgment_basis", "reference_url", "image_example_path", "danger_level", "memo"]
    count = 0
    for row in rows:
        r = {k: row.get(k) or None for k in fields if k in row}
        if "danger_level" in r:
            r["danger_level"] = _int(r["danger_level"])
        cols = ", ".join(r.keys())
        ph = ", ".join("?" for _ in r)
        conn.execute(f"INSERT INTO fake_features ({cols}) VALUES ({ph})", list(r.values()))
        count += 1
    return count


def import_auctions(rows: list[dict], conn):
    fields = ["auction_house", "lot_number", "item_name", "period", "material",
              "size_description", "estimate_low", "estimate_high", "hammer_price",
              "currency", "sale_date", "provenance", "condition_description",
              "source_url", "image_path", "comparison_memo"]
    count = 0
    for row in rows:
        r = {k: row.get(k) or None for k in fields if k in row}
        for flt in ("estimate_low", "estimate_high", "hammer_price"):
            if flt in r:
                r[flt] = _float(r[flt])
        cols = ", ".join(r.keys())
        ph = ", ".join("?" for _ in r)
        conn.execute(f"INSERT INTO auctions ({cols}) VALUES ({ph})", list(r.values()))
        count += 1
    return count


def import_file(path: Path, conn) -> int:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    name = path.name.lower()
    if name.startswith("items"):
        n = import_items(rows, conn)
    elif name.startswith("references"):
        n = import_references(rows, conn)
    elif name.startswith("fake_features"):
        n = import_fake_features(rows, conn)
    elif name.startswith("auctions"):
        n = import_auctions(rows, conn)
    else:
        print(f"  [SKIP] Unknown CSV type: {path.name}")
        return 0
    print(f"  [OK] {path.name}: {n} rows imported")
    return n


def main():
    parser = argparse.ArgumentParser(description="Import CSV files into the antiques database")
    parser.add_argument("files", nargs="*", help="CSV files to import (default: all in data/csv/)")
    parser.add_argument("--csv-dir", default="data/csv", help="Directory to scan for CSV files")
    args = parser.parse_args()

    conn = get_connection()
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = sorted(Path(args.csv_dir).glob("*.csv"))

    if not paths:
        print("No CSV files found.")
        return

    total = 0
    for p in paths:
        print(f"Importing {p} ...")
        total += import_file(p, conn)

    conn.commit()
    conn.close()
    print(f"\nTotal rows imported: {total}")


if __name__ == "__main__":
    main()
