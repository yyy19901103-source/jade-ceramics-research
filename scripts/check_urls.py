#!/usr/bin/env python3
"""Check that reference URLs in CSV files are reachable."""

import csv
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

URL_FIELDS = ("reference_url",)


def extract_urls(filepath: Path) -> list[tuple[int, str, str]]:
    """Return list of (row_num, field, url) tuples."""
    urls = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            for field in URL_FIELDS:
                value = (row.get(field) or "").strip()
                if value:
                    urls.append((row_num, field, value))
    return urls


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def check_url(url: str, timeout: int) -> tuple[bool, str]:
    if not HAS_REQUESTS:
        return True, "requests not installed — skipped"
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code < 400:
            return True, str(resp.status_code)
        return False, f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, f"connection error: {e}"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Check reference URLs in CSV files")
    parser.add_argument("--file", help="Specific CSV file to check")
    parser.add_argument("--data-dir", default="data", help="Directory containing CSV files")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only validate URL format, skip HTTP requests")
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

    total = 0
    failed = 0

    for filepath in files:
        print(f"\nChecking URLs in {filepath} ...")
        entries = extract_urls(filepath)

        if not entries:
            print("  No URLs found.")
            continue

        for row_num, field, url in entries:
            total += 1
            if not is_valid_url(url):
                print(f"  [INVALID] Row {row_num} '{field}': {url}")
                failed += 1
                continue

            if args.dry_run:
                print(f"  [FORMAT OK] Row {row_num}: {url}")
                continue

            ok, status = check_url(url, args.timeout)
            if ok:
                print(f"  [OK {status}] Row {row_num}: {url}")
            else:
                print(f"  [FAIL {status}] Row {row_num}: {url}")
                failed += 1

    print(f"\nChecked {total} URLs. {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
