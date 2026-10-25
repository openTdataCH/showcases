# GTFS merger

Merge two GTFS folders into one output folder. GTFS1 is the earlier dataset and GTFS2 is the later dataset.

## Merge rules

Output columns and their order come from `gtfs_schema_path` in `gtfs_merger/config.yml`.

| Table | Merge rules |
| --- | --- |
| `feed_info` | Use GTFS1's start date and GTFS2's end date. Keep other fields from GTFS1, except `feed_version`, which combines both versions as `db1:<version1>+gtfs2:<version2>`. Require GTFS1 start < GTFS2 start and GTFS1 end < GTFS2 end. No gap check. |
| `agency` | Write GTFS2 first, then GTFS1. Keep the first row for each `agency_id`, so GTFS2 takes precedence. |
| `calendar` | Write all GTFS2 rows unchanged, then all GTFS1 rows with `d1.` prefixed to `service_id`. |
| `calendar_dates` | Write all GTFS2 rows unchanged, then all GTFS1 rows with `d1.` prefixed to `service_id`. Keep `date` and `exception_type` unchanged. |
| `frequencies` | Write all GTFS2 rows unchanged, then all GTFS1 rows with `d1.` prefixed to `trip_id`. |
| `routes` | Write GTFS2 first. For each GTFS1 route: keep its ID unchanged if absent from GTFS2; skip the duplicate if its ID and `agency_id`, `route_short_name`, `route_desc`, and `route_type` match; otherwise prefix its ID with `d1.` and insert it. Missing optional comparison values count as empty strings. Raise on output ID collisions. Retain the GTFS1 route ID mapping for trips. |

TBA rest

## Installation

```
$ bash bootstrap.sh 
```

## Scripts

```bash
python3 cli_merge_gtfs.py \
  --gtfs1 /path/to/earlier-gtfs \
  --gtfs2 /path/to/later-gtfs \
  --output-gtfs /path/to/merged-gtfs
```

The output folder is created if it does not exist.
