# GTFS merger

Merge two GTFS folders into one output folder. GTFS1 is the earlier dataset and GTFS2 is the later dataset.

## Merge rules

Output columns and their order come from `gtfs_schema_path` in `gtfs_merger/config.yml`.

Except for `feed_info`, process GTFS2 first and then GTFS1. Unless specified below, column values remain unchanged. For `agency`, `routes`, and `stops`, keep GTFS2's row when a duplicate is merged.

| Table | Merge rules |
| --- | --- |
| `feed_info` | <ul><li><code>feed_start_date</code>: use GTFS1's value; require GTFS1 &lt; GTFS2<li><code>feed_end_date</code>: use GTFS2's value; require GTFS1 &lt; GTFS2. No gap check<li><code>feed_version</code>: combine as <code>db1:&lt;version1&gt;+gtfs2:&lt;version2&gt;</code><li>Other columns: keep GTFS1's values</ul> |
| `agency` | <ul><li><code>agency_id</code>: unique key; skip IDs already written<li>Other columns: keep values from the first row for that ID</ul> |
| `calendar` | <ul><li><code>service_id</code>: prefix GTFS1 values with <code>d1.</code></ul> |
| `calendar_dates` | <ul><li><code>service_id</code>: prefix GTFS1 values with <code>d1.</code><li><code>date</code>: unchanged<li><code>exception_type</code>: unchanged</ul> |
| `frequencies` | <ul><li><code>trip_id</code>: prefix GTFS1 values with <code>d1.</code></ul> |
| `routes` | <ul><li><code>route_id</code>: keep GTFS1-only IDs unchanged. For shared IDs, skip GTFS1's row if all four comparison columns match; otherwise prefix GTFS1's ID with <code>d1.</code>. Raise on output ID collisions. Retain a GTFS1 ID map<li><code>agency_id</code>: compare for equality<li><code>route_short_name</code>: compare for equality<li><code>route_desc</code>: compare for equality<li><code>route_type</code>: compare for equality<li>Missing optional comparison values: treat as empty strings</ul> |
| `trips` | <ul><li><code>route_id</code>: map GTFS1 values using the route ID map; raise if missing<li><code>service_id</code>: prefix GTFS1 values with <code>d1.</code><li><code>trip_id</code>: prefix GTFS1 values with <code>d1.</code></ul> |
| `stop_times` | <ul><li><code>trip_id</code>: prefix GTFS1 values with <code>d1.</code><li><code>stop_id</code>: unchanged</ul> |
| `stops` | <ul><li><code>stop_id</code>: unique key; skip IDs already written. Keep IDs unchanged<li><code>parent_station</code>: unchanged<li>Other columns: keep values from the first row for that ID</ul> |
| `transfers` | <ul><li><code>from_stop_id</code>: unchanged<li><code>to_stop_id</code>: unchanged<li><code>from_route_id</code>: map nonempty GTFS1 values using the route ID map; raise if missing<li><code>to_route_id</code>: map nonempty GTFS1 values using the route ID map; raise if missing<li><code>from_trip_id</code>: prefix nonempty GTFS1 values with <code>d1.</code><li><code>to_trip_id</code>: prefix nonempty GTFS1 values with <code>d1.</code><li><code>service_id</code>: prefix nonempty GTFS1 values with <code>d1.</code><li>Other columns: unchanged. Empty optional IDs stay empty</ul> |

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
