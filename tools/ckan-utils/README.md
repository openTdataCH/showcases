# CKAN utils

An `opentransportdata.swiss` API key is needed to run these tools. The key is stored in `OTD_KEY` [.env](../../.env) project file.

- see [./inc/config.yml](./inc/config.yml) for resource paths. 
- `PACKAGE_ID` param comes from https://data.opentransportdata.swiss/en/organization/oevch

## Installation

```
$ bash bootstrap.sh 
```

## Fetch CKAN package metadata

Usage: `fetch_metadata_cli.py [-h] [--package_id PACKAGE_ID]`

|Param|Description|Example|
| -- | -- | -- |
| --package_id| package_id from https://data.opentransportdata.swiss/en/organization/oevch | `timetable-2026-gtfs2020` or `timetable-54-2026-hrdf` |

## Fetch CKAN package resource

Usage: `fetch_package_cli.py [-h] [--package_id PACKAGE_ID] [--resource_title RESOURCE_TITLE] [--output OUTPUT_DIR] [--partial_match] [--overwrite]`

|Param|Description|Example|
| -- | -- | -- |
| --package_id| package_id from https://data.opentransportdata.swiss/en/organization/oevch | `timetable-54-2025-hrdf` |
| --resource_title | If present, the script will try to fetch fetch the resource named with this title. If missing, the script will fetch the first resource in the list (last updated) | `OeV_Sammlung_CH_HRDF_5_40_41_2022_20220513_211738.zip` or `None` |
| --output | Directory for downloaded resources and extracted ZIP contents. Defaults to `resource_paths.package_base_path` in `inc/config.yml`, with `[PACKAGE_ID]` replaced by the selected package ID. Missing parent directories are created automatically. | `./data/gtfs` |
| --partial_match | Match the beginning of the resource filename when using `--resource_title`. | `--partial_match` |
| --overwrite | Download and extract again even if the destination file or folder already exists. | `--overwrite` |

Example with a custom output directory:

```bash
python3 fetch_package_cli.py --package_id timetable-2026-gtfs2020 --output ./data/gtfs
```
