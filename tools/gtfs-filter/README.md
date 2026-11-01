# GTFS filter

Filter a GTFS folder by an inclusive date range and write the retained services, trips, routes, agencies, stops and transfers to an output folder.

## Table processing order

| Order | Table | Notes |
| --- | --- | --- |
| 1 | `feed_info` | Update feed dates. |
| 2 | `calendar`, `calendar_dates` | Determine active `service_id` |
| 3 | `trips` | Keep trips for active `service_id` |
| 4 | `routes` | Keep routes referenced by retained trips |
| 5 | `agency` | Keep agencies referenced by retained routes |
| 6 | `frequencies` | Keep rows for active trips, if the file exists |
| 7 | `stop_times` | Keep rows for active trips |
| 8 | `stops` | Keep stops referenced by retained stop times |
| 9 | `transfers` | Keep rows matching active references, if the file exists |

Processing notes

- output files preserve the input columns and their order 
- retained values stay unchanged except for `feed_start_date` and `feed_end_date`

## Installation

Run from `tools/gtfs-filter`:

```bash
bash bootstrap.sh
```

## Scripts

```bash
.venv/bin/python3 cli_filter_gtfs.py \
  --gtfs-src /path/to/source-gtfs \
  --gtfs-dst /path/to/filtered-gtfs \
  --from 2026-10-21 \
  --to 2026-12-12
```

- `--gtfs-src` / `--gtfs_src`: required existing source folder.
- `--gtfs-dst` / `--gtfs_dst`: required destination folder path. Its parent must exist and be writable.
- `--from`: inclusive start date in strict `YYYY-MM-DD` format.
- `--to`: inclusive end date in strict `YYYY-MM-DD` format.

At least one of `--from` or `--to` is required. An omitted bound uses the corresponding `feed_start_date` or `feed_end_date` from the input `feed_info.txt`; missing or invalid dates stop processing. The resolved start date must be on or before the end date.

The output folder is created if it does not exist. 
