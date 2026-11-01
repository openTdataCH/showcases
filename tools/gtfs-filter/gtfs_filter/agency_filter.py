import csv
from pathlib import Path

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class AgencyFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'agency.txt'
        destination_path = destination_gtfs_path / 'agency.txt'
        log_message(f'Reading {source_path}; keeping agencies referenced by retained routes')
        parsed_rows = 0
        kept_rows = 0
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            column_names = list(reader.fieldnames)
            writer = CSV_Updater(destination_path, column_names)
            try:
                for row in reader:
                    parsed_rows += 1
                    agency_id = row.get('agency_id', '')
                    # Routes may omit agency_id when the feed has a single agency.
                    if '' not in context.active_agency_ids:
                        if agency_id not in context.active_agency_ids:
                            continue
                    writer.prepare_row(row)
                    kept_rows += 1
            finally:
                writer.close()
        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} agencies to {destination_path}; discarded {dropped_rows}')
