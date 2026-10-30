import csv

from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .import_context import ImportContext


class StopTimesImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_stop_times(self):
        log_message('START import stop_times')
        stop_times_path = self._context.gtfs_folder_path / 'stop_times.txt'
        log_message(f'Reading {stop_times_path}')
        total_rows = compute_file_rows_no(stop_times_path) - 1
        if total_rows < 0:
            total_rows = 0
        self._context.source_table_rows['stop_times'] = total_rows
        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Found {formatted_total_rows} stop_times rows')

        stop_times_writer = self._context.db_engine.create_csv_writer('stop_times')
        row_count = 0
        kept_rows = 0
        try:
            with stop_times_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for stop_time_row in csv_reader:
                    if row_count % 5_000_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                        log_message(
                            f'... parsed {formatted_row_count} / {formatted_total_rows} stop_times rows; '
                            f'kept {formatted_kept_rows}'
                        )

                    # Keep only stop times belonging to trips retained in the selected date range.
                    if stop_time_row['trip_id'] in self._context.active_trip_ids:
                        stop_times_writer.prepare_row(stop_time_row)
                        kept_rows += 1
                    row_count += 1
                # loop stop_times.txt CSV rows
            # with
        finally:
            stop_times_writer.close()

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        log_message(
            f'Parsed {formatted_row_count} / {formatted_total_rows} stop_times rows; '
            f'kept {formatted_kept_rows}'
        )
        self._context.db_engine.drop_and_recreate_table('stop_times')
        self._context.db_engine.load_csv_into_table('stop_times', stop_times_writer.csv_path)
        self._context.db_engine.add_table_indexes('stop_times')
        log_message(f'Imported {formatted_kept_rows} / {formatted_row_count} stop_times rows')
        log_message('DONE import stop_times')
        print()
