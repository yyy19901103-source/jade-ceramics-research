#!/usr/bin/env python3
"""Validate CSV data files against expected schema."""

import csv
import sys
import argparse
from pathlib import Path

SCHEMAS = {
    "specimens.csv": {
        "required_fields": [
            "specimen_id", "site_name", "excavation_date", "material_type",
            "color", "weight_g", "dimensions_mm", "dynasty", "provenance",
            "condition", "reference_url", "notes",
        ],
        "validators": {
            "specimen_id": lambda v: v.startswith("SP") and v[2:].isdigit(),
            "weight_g": lambda v: v == "" or float(v) > 0,
            "condition": lambda v: v in ("excellent", "good", "fair", "poor", ""),
        },
    },
    "analysis_results.csv": {
        "required_fields": [
            "specimen_id", "analysis_date", "analyst", "method",
            "si_percent", "al_percent", "fe_percent", "ca_percent",
            "mg_percent", "na_percent", "k_percent", "hardness_mohs",
            "refractive_index", "reference_url", "notes",
        ],
        "validators": {
            "specimen_id": lambda v: v.startswith("SP") and v[2:].isdigit(),
            "method": lambda v: v in ("XRF", "EPMA", "Raman", "FTIR", ""),
            "hardness_mohs": lambda v: v == "" or 0 < float(v) <= 10,
        },
    },
}


def validate_file(filepath: Path) -> list[str]:
    errors = []
    schema = SCHEMAS.get(filepath.name)

    if schema is None:
        print(f"  [SKIP] No schema defined for {filepath.name}")
        return errors

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        actual_fields = reader.fieldnames or []

        missing = set(schema["required_fields"]) - set(actual_fields)
        if missing:
            errors.append(f"Missing columns: {', '.join(sorted(missing))}")
            return errors

        for row_num, row in enumerate(reader, start=2):
            for field, validator in schema["validators"].items():
                value = row.get(field, "")
                try:
                    if not validator(value):
                        errors.append(f"Row {row_num}: invalid '{field}' = '{value}'")
                except (ValueError, TypeError):
                    errors.append(f"Row {row_num}: cannot parse '{field}' = '{value}'")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate jade ceramics CSV files")
    parser.add_argument("--file", help="Specific CSV file to validate")
    parser.add_argument("--data-dir", default="data", help="Directory containing CSV files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: data directory '{data_dir}' not found")
        sys.exit(1)

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(data_dir.glob("*.csv"))

    if not files:
        print("No CSV files found.")
        sys.exit(0)

    all_passed = True
    for filepath in files:
        print(f"Validating {filepath} ...")
        errors = validate_file(filepath)
        if errors:
            all_passed = False
            for err in errors:
                print(f"  [ERROR] {err}")
        else:
            print(f"  [OK]")

    if all_passed:
        print("\nAll files passed validation.")
    else:
        print("\nValidation completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
