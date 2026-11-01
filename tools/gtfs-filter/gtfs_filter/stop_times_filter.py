import csv
from pathlib import Path
from typing import Set, TypedDict

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class StopIdRow(TypedDict):
    stop_id: str


class StopTimesFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path,
        db_engine: SQLiteDBEngine, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'stop_times.txt'
        destination_path = destination_gtfs_path / 'stop_times.txt'
        log_message(f'Reading {source_path}; keeping stop times for active trip IDs')
        parsed_rows = 0
        kept_rows = 0
        active_stop_ids: Set[str] = set()
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            column_names = list(reader.fieldnames)
            stop_ids_writer = db_engine.create_csv_writer('stops')
            try:
                writer = CSV_Updater(destination_path, column_names)
                try:
                    for row in reader:
                        parsed_rows += 1
                        if parsed_rows % 5_000_000 == 0:
                            log_message(f'Parsed {parsed_rows} stop_times rows; kept {kept_rows}')
                        if row['trip_id'] not in context.active_trip_ids:
                            continue

                        writer.prepare_row(row)
                        kept_rows += 1
                        stop_id = row['stop_id']
                        if stop_id not in active_stop_ids:
                            stop_id_row: StopIdRow = {'stop_id': stop_id}
                            stop_ids_writer.prepare_row(stop_id_row)
                            active_stop_ids.add(stop_id)
                finally:
                    writer.close()
            finally:
                stop_ids_writer.close()

        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} stop times to {destination_path}; discarded {dropped_rows}')
        log_message(f'Loading {len(active_stop_ids)} distinct stop IDs from {stop_ids_writer.csv_path}')
        db_engine.drop_and_recreate_table('stops')
        db_engine.load_csv_into_table('stops', stop_ids_writer.csv_path)
        log_message(f'Stored {len(active_stop_ids)} active stop IDs in the intermediate stops table')
