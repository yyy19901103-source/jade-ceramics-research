# Data Schema

## specimens.csv

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| specimen_id | string | yes | Format: SP + 3-digit number (e.g. SP001) |
| site_name | string | yes | Archaeological site name |
| excavation_date | date | yes | ISO 8601 (YYYY-MM-DD) |
| material_type | string | yes | e.g. nephrite, jadeite |
| color | string | yes | Color description |
| weight_g | float | yes | Weight in grams (> 0) |
| dimensions_mm | string | yes | Format: LxWxH |
| dynasty | string | yes | Cultural period or dynasty |
| provenance | string | yes | Geographic origin |
| condition | enum | yes | excellent / good / fair / poor |
| reference_url | url | no | HTTP/HTTPS link to source |
| notes | string | no | Free text |

## analysis_results.csv

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| specimen_id | string | yes | Must match specimens.csv |
| analysis_date | date | yes | ISO 8601 (YYYY-MM-DD) |
| analyst | string | yes | Analyst name |
| method | enum | yes | XRF / EPMA / Raman / FTIR |
| si_percent | float | no | Silicon dioxide % |
| al_percent | float | no | Aluminium oxide % |
| fe_percent | float | no | Iron oxide % |
| ca_percent | float | no | Calcium oxide % |
| mg_percent | float | no | Magnesium oxide % |
| na_percent | float | no | Sodium oxide % |
| k_percent | float | no | Potassium oxide % |
| hardness_mohs | float | no | Mohs hardness (0–10) |
| refractive_index | float | no | Refractive index |
| reference_url | url | no | HTTP/HTTPS link to report |
| notes | string | no | Free text |
