# GTFS DB importer

See [CHANGELOG](./CHANGELOG.md) for latest changes

Python tools that imports a GTFS dataset into SQLite DB. The DB schema is specified in [./inc/config/gtfs_schema.yml](./inc/config/gtfs_schema.yml).

## Installation

```
$ bash bootstrap.sh 
```

## Scripts

### gtfs_db_importer_cli.py

CLI tool that ingests GTFS data into a SQLite DB

Usage: `python3 gtfs_db_importer_cli.py [-h] [--gtfs-folder-path GTFS_FOLDER_PATH] [--output-db-path OUTPUT_DB_PATH] [--from DATE] [--to DATE]`

| Param | Required | Description | Example |
| - | - | - | - |
| `--gtfs-db-path` | `YES` | input path to GTFS folder, relative or absolute|  |
| `--output-db-path` |  | path to output SQLite DB, relative or absolute. If not givem the script will create it under ./data/gtfs-static-dbs folder| `/tmp/foo.db` |
| `--from` |  | Inclusive calendar start date in `YYYYMMDD` or `YYYY-MM-DD` format. Defaults to `feed_info.feed_start_date`. | `2026-12-13` |
| `--to` |  | Inclusive calendar end date in `YYYYMMDD` or `YYYY-MM-DD` format. Defaults to `feed_info.feed_end_date`. | `2027-12-11` |

Missing feed date bounds are derived from the earliest/latest dates across `calendar.txt` and `calendar_dates.txt`. If either bound remains unavailable, the import raises before DB creation. The resolved feed range must not exceed 500 days (`end - start`). Both CLI bounds must be within that range, and `--from` must be on or before `--to`.

Example

```
$ python3 gtfs_db_importer_cli.py \
    --gtfs-folder-path data/gtfs-static/current/gtfs_fp2021_2021-04-07_09-10
```

The script detects the GTFS date from the GTFS static folder and ingests the content into `gtfs_2021-04-07.sqlite` SQLite file.

### cli_filter_gtfs.py

CLI tool that filters GTFS content from a GTFS database created with `gtfs_db_importer_cli.py`

Usage: `cli_filter_gtfs.py [-h] [--gtfs-db-path GTFS_DB_PATH] [--gtfs-output-path GTFS_OUTPUT_PATH] [--bbox BBOX] [--agency AGENCY] [--day DAY]`

| Param | Required | Description | Example |
| - | - | - | - |
| `--gtfs-db-path` | `YES` | input path to GTFS SQLite DB | `data/gtfs-static-dbs/gtfs_2026-05-03.sqlite` |
| `--gtfs-output-path` | `YES` | path to the folder that will contain GTFS filtered files | `./tmp/gtfs-bern-crop` |
| `--bbox` |  | filter for BBOX coordinates given (minLon, minLat, maxLon, maxLat format) | `7.444310,46.961013,7.472076,46.971907` - Bern area filter |
| `--agency` |  | filter for agency_id values, separated with `,` | `33,827` - BLS, Bern Mobil |
| `--day` |  | filter for a day of operations given in `YYYY-MM-DD` format | `2026-03-25` - 25.March 2026 |

Example filter for BLS (agency_id=33), BernMobil (agency_id=827)

```
python3 cli_filter_gtfs.py \
    --gtfs-db-path data/gtfs-static-dbs/gtfs_2026-03-21.sqlite \
    --gtfs-output-path tmp/gtfs-agency-bls-bernmobil \
    --agency 33,827
```
