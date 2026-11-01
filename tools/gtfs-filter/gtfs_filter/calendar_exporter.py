import csv
from pathlib import Path

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class CalendarExporter:
    def export(
        self, source_gtfs_path: Path, destination_gtfs_path: Path, context: FilterContext,
    ) -> None:
        for filename in ['calendar.txt', 'calendar_dates.txt']:
            source_path = source_gtfs_path / filename
            destination_path = destination_gtfs_path / filename
            self._write_table(source_path, destination_path, context)

    def _write_table(
        self, source_path: Path, destination_path: Path, context: FilterContext,
    ) -> None:
        if not source_path.is_file():
            log_message(f'Skipping {source_path.name}: source file not found at {source_path}')
            return

        log_message(f'Reading {source_path}; keeping rows for active service IDs')
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
                    if parsed_rows % 5_000_000 == 0:
                        log_message(f'Parsed {parsed_rows} {source_path.name} rows; kept {kept_rows}')
                    if row['service_id'] not in context.active_service_ids:
                        continue
                    writer.prepare_row(row)
                    kept_rows += 1
            finally:
                writer.close()
        log_message(f'Saved {kept_rows} / {parsed_rows} rows to {destination_path}')
