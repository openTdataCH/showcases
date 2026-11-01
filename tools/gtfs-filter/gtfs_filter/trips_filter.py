import csv
from pathlib import Path
from typing import TypedDict

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class TripIdRow(TypedDict):
    trip_id: str


class TripsFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path,
        db_engine: SQLiteDBEngine, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'trips.txt'
        destination_path = destination_gtfs_path / 'trips.txt'
        log_message(f'Reading {source_path}; keeping trips for active service IDs')
        parsed_rows = 0
        kept_rows = 0
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            column_names = list(reader.fieldnames)
            trip_ids_writer = db_engine.create_csv_writer('trips')
            try:
                writer = CSV_Updater(destination_path, column_names)
                try:
                    for row in reader:
                        parsed_rows += 1
                        if parsed_rows % 5_000_000 == 0:
                            log_message(f'Parsed {parsed_rows} trips rows; kept {kept_rows}')
                        if row['service_id'] not in context.active_service_ids:
                            continue

                        writer.prepare_row(row)
                        trip_id_row: TripIdRow = {'trip_id': row['trip_id']}
                        trip_ids_writer.prepare_row(trip_id_row)
                        kept_rows += 1
                finally:
                    writer.close()
            finally:
                trip_ids_writer.close()

        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} trips to {destination_path}; discarded {dropped_rows}')
        log_message(f'Loading retained trip IDs from {trip_ids_writer.csv_path}')
        db_engine.drop_and_recreate_table('trips')
        db_engine.load_csv_into_table('trips', trip_ids_writer.csv_path)
        log_message(f'Stored {kept_rows} trip IDs in the intermediate trips table')
