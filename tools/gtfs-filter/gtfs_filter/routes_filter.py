import csv
from pathlib import Path

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class RoutesFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'routes.txt'
        destination_path = destination_gtfs_path / 'routes.txt'
        log_message(f'Reading {source_path}; keeping routes for active route IDs')
        parsed_rows = 0
        kept_rows = 0
        context.active_agency_ids.clear()
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            column_names = list(reader.fieldnames)
            writer = CSV_Updater(destination_path, column_names)
            try:
                for row in reader:
                    parsed_rows += 1
                    if parsed_rows % 5_000_000 == 0:
                        log_message(f'Parsed {parsed_rows} routes rows; kept {kept_rows}')
                    if row['route_id'] not in context.active_route_ids:
                        continue
                    writer.prepare_row(row)
                    agency_id = row.get('agency_id', '')
                    context.active_agency_ids.add(agency_id)
                    kept_rows += 1
            finally:
                writer.close()
        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} routes to {destination_path}; discarded {dropped_rows}')
        log_message(f'Collected {len(context.active_agency_ids)} distinct agency IDs into context')
