# Showcases

Repository structure:

- [apps](./apps/) - (web)applications (Angular)
- [tools](./tools/) - server side tools (Python, NodeJs)

## GTFS Apps & Tools

| App / Repo Path | Description / Demo URL |
|-|-|
| Atlas-Lines compare GTFS-Routes <br/> [./apps/atlas-routes-compare-gtfs](./apps/atlas-routes-compare-gtfs/) | Visualize and compare Atlas line with GTFS routes.txt dataset <br/> https://tools.opentransportdata.swiss/atlas-route-compare-gtfs/ |
| GTFS-RT -static Report <br/> [./apps/gtfs-rt-static-report](./apps/gtfs-rt-static-report/) | Visualize the monthly comparison between GTFS-RT and GTFS static datasets <br/> https://tools.opentransportdata.swiss/gtfs-rt-static-report/ |
| GTFS-RT Status <br/> [./apps/gtfs-rt-status](./apps/gtfs-rt-status/) | Visualize the current comparison between GTFS-RT and GTFS static datasets <br/> https://tools.opentransportdata.swiss/gtfs-rt-status/ |
| GTFS-static query API <br/> [./apps/gtfs-query](./apps/gtfs-query) | GTFS-static query API built on top of current dataset <br/> https://github.com/openTdataCH/showcases/tree/develop/apps/gtfs-query |
| GTFS - HRDF Compare <br/> [./tools/gtfs-hrdf-compare/](./tools/gtfs-hrdf-compare/) | CLI tool that compares GTFS and HRDF datasets <br/> https://github.com/openTdataCH/showcases/blob/develop/tools/gtfs-hrdf-compare |
| GTFS Datasets Compare <br/> [./tools/gtfs-hrdf-compare/](./tools/gtfs-prev-compare/) | CLI tool that compares 2 GTFS datasets <br/> https://github.com/openTdataCH/showcases/blob/develop/tools/gtfs-prev-compare |
| GTFS-RT - GTFS-static compare <br/> [./tools/gtfs-rt-static-compare/](./tools/gtfs-rt-static-compare/) | CLI tool that compares GTFS-static and GTFS-RT datasets <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/gtfs-rt-static-compare |
| GTFS-static DB importer <br/> [./tools/gtfs-static-db-importer/](./tools/gtfs-static-db-importer/) | Tool that ingests a given GTFS-static dataset into a SQLite DB <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/gtfs-static-db-importer |
| GTFS merger <br/> [./tools/gtfs-merger/](./tools/gtfs-merger/) | CLI tool that merges two GTFS datasets into one GTFS folder |

## HRDF Apps & Tools

| App / Repo Path | Description / Demo URL |
|-|-|
| Bitfeld visualizer <br/> [./apps/bitfeld-viz](./apps/bitfeld-viz/) | Visualize HRDF [Bitfeld](https://opentransportdata.swiss/de/cookbook/timetable-cookbook/hafas-rohdaten-format-hrdf/#BITFELD) strings <br/> https://tools.opentransportdata.swiss/bitfeld-viz/ |
| HRDF Duplicates Report <br/> [./apps/hrdf-duplicates-report](./apps/hrdf-duplicates-report/) | Visualize current HRDF dataset duplicates on Fahrtnummer <br/> https://tools.opentransportdata.swiss/hrdf-duplicates-report/ |
| HRDF query API <br/> [./apps/hrdf-query](./apps/hrdf-query) | HRDF query API built on top of current dataset <br/> https://github.com/openTdataCH/showcases/tree/develop/apps/hrdf-query |
| GTFS - HRDF Compare <br/> [./tools/gtfs-hrdf-compare/](./tools/gtfs-hrdf-compare/) | CLI tool that compares GTFS and HRDF datasets <br/> https://github.com/openTdataCH/showcases/blob/develop/tools/gtfs-hrdf-compare |
| HRDF Check duplicates <br/> [./tools/hrdf-check-duplicates/](./tools/hrdf-check-duplicates/) | Tool that checks for FPLAN duplicates in a given HRDF dataset <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/hrdf-check-duplicates |
| HRDF DB importer <br/> [./tools/gtfs-static-db-importer/](./tools/hrdf-db-importer/) | Tool that ingests a given HRDF dataset into a SQLite DB <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/hrdf-db-importer |

## SIRI-SX / SIRI-ET Apps

| App / Repo Path | Description / Demo URL |
|-|-|
| SIRI-ET check SLOIDs <br/> [./apps/siri-et-check-sloids](./apps/siri-et-check-sloids/) | Visualize [SIRI-ET](https://opentransportdata.swiss/en/cookbook/siri-et-pt-with-request-response/) messages for missing [SLOIDs](https://www.oev-info.ch/de/datenmanagement/sid4pt-swiss-id-public-transport/swiss-location-identification-sloid) <br/> https://tools.opentransportdata.swiss/siri-et-check-sloids/ |
| SIRI-ET compare with GTFS-RT <br/> [./apps/siri-et-compare-gtfs-rt](./apps/siri-et-compare-gtfs-rt/) | Visualize [SIRI-ET](https://opentransportdata.swiss/en/cookbook/siri-et-pt-with-request-response/) dataset with [GTFS-RT](https://opentransportdata.swiss/en/cookbook/gtfs-sa/) feed <br/> https://tools.opentransportdata.swiss/siri-et-compare-gtfs-rt/ |

## Miscellanous

| App / Repo Path | Description / Demo URL |
|-|-|
| Atlas Geocode Lines Stops <br/> [./tools/atlas-geocode-lines/](./tools/atlas-geocode-lines/) | Tool that extracts stop names from [Atlas-Lines](https://data.opentransportdata.swiss/de/dataset/slnid-line) dataset and geocodes them against [Location Information OJP Service](https://opentransportdata.swiss/en/cookbook/ojplocationinformationrequest/) <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/atlas-geocode-lines |
| Atlas Lookup Lines <br/> [./tools/atlas-lookup-lines/](./tools/atlas-lookup-lines/) | Tool that intersects [Atlas-Lines](https://data.opentransportdata.swiss/de/dataset/slnid-line) dataset rows with [oev-info.ch](https://www.oev-info.ch/de/fahrplan-aktuell/fahrplanfelder-abfragen) results. <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/atlas-lookup-lines |
| CKAN utils <br/> [./tools/ckan-utils/](./tools/ckan-utils/) | CLI tool that fetches datasets from [opentransportdata.swiss](https://opentransportdata.swiss/) <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/ckan-utils |
| Ist-Daten Filter <br/> [./tools/ist-daten-filter/](./tools/ist-daten-filter/) | CLI tools that fetch and filter [ist-daten](https://archive.opentransportdata.swiss/actual_data_archive.htm) datasets <br/> https://github.com/openTdataCH/showcases/tree/develop/tools/ist-daten-filter |
