import csv
from pathlib import Path
from typing import Set

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class StopsFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'stops.txt'
        destination_path = destination_gtfs_path / 'stops.txt'
        self._retain_parent_stops(source_path, context)
        log_message(f'Reading {source_path}; keeping stops for active stop IDs')
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
                        log_message(f'Parsed {parsed_rows} stops rows; kept {kept_rows}')
                    if row['stop_id'] not in context.active_stop_ids:
                        continue
                    writer.prepare_row(row)
                    kept_rows += 1
            finally:
                writer.close()
        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} stops to {destination_path}; discarded {dropped_rows}')

    def _retain_parent_stops(self, source_path: Path, context: FilterContext) -> None:
        log_message(f'Reading {source_path}; collecting direct parents of active stops')
        parent_stop_ids: Set[str] = set()
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            for row in reader:
                if row['stop_id'] not in context.active_stop_ids:
                    continue
                parent_stop_id = row.get('parent_station')
                if parent_stop_id is None or parent_stop_id == '':
                    continue
                parent_stop_ids.add(parent_stop_id)

        additional_parent_ids = parent_stop_ids - context.active_stop_ids
        context.active_stop_ids.update(parent_stop_ids)
        log_message(f'Retained {len(additional_parent_ids)} additional direct parent stops')
