# Jade Ceramics Research

A data management and validation toolkit for jade ceramics specimen research.

## Project Structure

```
jade-ceramics-research/
├── data/               # CSV datasets for ceramic specimens
├── scripts/            # Validation and utility scripts
│   ├── validate_csv.py # Validate CSV files against schema
│   └── check_urls.py   # Check URLs in reference fields
├── templates/          # CSV templates for data entry
└── docs/               # Documentation and schema definitions
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Validate CSV data files

```bash
python3 scripts/validate_csv.py
python3 scripts/validate_csv.py --file data/specimens.csv
```

### Check reference URLs

```bash
python3 scripts/check_urls.py
python3 scripts/check_urls.py --file data/specimens.csv --timeout 10
```

## Data Schema

See `docs/schema.md` for field definitions and validation rules.

## Templates

Use `templates/specimen_template.csv` as a starting point for new data entry.
