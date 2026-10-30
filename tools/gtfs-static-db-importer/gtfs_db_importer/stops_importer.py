import csv
from typing import cast

from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file

from .import_types import StopMissingParentRow, StopParentDepthRow
from .import_context import ImportContext


class StopsImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_stops(self):
        log_message('START import stops')
        stops_path = self._context.gtfs_folder_path / 'stops.txt'
        log_message(f'Reading {stops_path}')
        total_rows = compute_file_rows_no(stops_path) - 1
        if total_rows < 0:
            total_rows = 0
        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Found {formatted_total_rows} stops rows')

        stops_writer = self._context.db_engine.create_csv_writer('stops')
        row_count = 0
        try:
            with stops_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for stop_row in csv_reader:
                    if row_count % 50_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        log_message(
                            f'... parsed {formatted_row_count} / {formatted_total_rows} stops rows; '
                            f'kept {formatted_row_count}'
                        )

                    # Keep the full stop catalogue, regardless of service in the selected date range.
                    stops_writer.prepare_row(stop_row)
                    row_count += 1
                # loop stops.txt CSV rows
            # with
        finally:
            stops_writer.close()

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        log_message(
            f'Parsed {formatted_row_count} / {formatted_total_rows} stops rows; '
            f'kept {formatted_row_count}'
        )
        self._context.db_engine.drop_and_recreate_table('stops')
        self._context.db_engine.load_csv_into_table('stops', stops_writer.csv_path)
        self._context.db_engine.add_table_indexes('stops')

        # Validate the original hierarchy before standalone stops become their own synthetic stations.
        self._check_stops_parent_depth()
        self._check_stops_missing_parents()
        log_message(f'Imported {formatted_row_count} / {formatted_total_rows} stops rows')
        log_message('DONE import stops')
        print()

    def _check_stops_parent_depth(self):
        log_message('START check stops parent depth')

        sql_path = self._context.map_sql_queries['select_stops_exceeding_parent_depth']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._context.db_engine.get_cursor()
        db_cursor.execute(sql)
        db_row = db_cursor.fetchone()
        db_cursor.close()

        if db_row is not None:
            invalid_stop = cast(StopParentDepthRow, db_row)
            stop_id = invalid_stop['stop_id']
            parent_stop_id = invalid_stop['parent_stop_id']
            grandparent_stop_id = invalid_stop['grandparent_stop_id']
            raise ValueError(
                f'Stop hierarchy exceeds one parent level: '
                f'{stop_id} -> {parent_stop_id} -> {grandparent_stop_id}'
            )

        log_message('DONE check stops parent depth')
        print('')

    def _check_stops_missing_parents(self):
        log_message('START check stops missing parents')

        sql_path = self._context.map_sql_queries['select_stops_missing_parents']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._context.db_engine.get_cursor()
        db_cursor.execute(sql)
        db_row = db_cursor.fetchone()
        db_cursor.close()

        if db_row is not None:
            invalid_stop = cast(StopMissingParentRow, db_row)
            stop_id = invalid_stop['stop_id']
            parent_station = invalid_stop['parent_station']
            raise ValueError(f'Stop {stop_id} references missing parent stop {parent_station}')

        log_message('DONE check stops missing parents')
        print('')
