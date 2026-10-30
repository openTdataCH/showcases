import csv
from pathlib import Path

from .helpers.csv_updater import CSV_Updater
from .helpers.file_helpers import compute_file_rows_no

from .helpers.gtfs_helpers import convert_datetime_to_day_minutes, extract_stop_times_data_from_s, seconds_to_hhmmss
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .import_context import ImportContext


class FrequenciesImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_frequencies(self):
        log_message('START import frequencies')
        frequencies_path = self._context.gtfs_folder_path / 'frequencies.txt'
        frequencies_writer = self._context.db_engine.create_csv_writer('frequencies')
        row_count = 0
        kept_rows = 0
        try:
            if frequencies_path.is_file():
                log_message(f'Reading {frequencies_path}')
                total_rows = compute_file_rows_no(frequencies_path) - 1
                if total_rows < 0:
                    total_rows = 0
                self._context.source_table_rows['frequencies'] = total_rows
                formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
                log_message(f'Found {formatted_total_rows} frequencies rows')
                with frequencies_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for frequency_row in csv_reader:
                        if row_count % 50_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                            log_message(
                                f'... parsed {formatted_row_count} / {formatted_total_rows} frequencies rows; '
                                f'kept {formatted_kept_rows}'
                            )

                        # Keep only frequency definitions for retained trips.
                        if frequency_row['trip_id'] in self._context.active_trip_ids:
                            frequencies_writer.prepare_row(frequency_row)
                            kept_rows += 1
                        row_count += 1
                    # loop frequencies.txt CSV rows
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                log_message(
                    f'Parsed {formatted_row_count} / {formatted_total_rows} frequencies rows; '
                    f'kept {formatted_kept_rows}'
                )
            else:
                log_message('No frequencies.txt present; creating an empty frequencies table')
        finally:
            frequencies_writer.close()

        self._context.db_engine.drop_and_recreate_table('frequencies')
        self._context.db_engine.load_csv_into_table('frequencies', frequencies_writer.csv_path)
        self._context.db_engine.add_table_indexes('frequencies')
        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        log_message(f'Imported {formatted_kept_rows} / {formatted_row_count} frequencies rows')

        # Expand the retained definitions into trips and stop_times using the existing logic.
        if kept_rows > 0:
            self._update_frequencies()
        log_message('DONE import frequencies')
        print()

    def _update_frequencies(self):
        '''
        INSERT into trips, stop_times from frequencies.txt
        '''
        log_message(f'START parsing frequencies...')

        db_temp_path = self._context.db_engine.get_db_tmp_path()

        trips_table_name = 'trips'
        trips_column_names = self._context.db_engine.map_columns_metadata[trips_table_name]['names']
        trips_frequencies_table_csv_file_path = Path(f'{db_temp_path}/trips_frequencies.csv')
        trips_frequencies_csv_updater = CSV_Updater(trips_frequencies_table_csv_file_path, trips_column_names)

        stop_times_table_name = 'stop_times'
        stop_times_column_names = self._context.db_engine.map_columns_metadata[stop_times_table_name]['names']
        stop_times_frequencies_table_csv_file_path = Path(f'{db_temp_path}/stop_times_frequencies.csv')
        stop_times_frequencies_table_csv_updater = CSV_Updater(stop_times_frequencies_table_csv_file_path, stop_times_column_names)

        sql_path = self._context.map_sql_queries['select_trips_group_by_stop_times_frequencies']
        sql = load_sql_from_file(sql_path)

        log_message(f"... running select_stop_times_group_by + frequencies SQL")

        db_cursor = self._context.db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 1_000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')

            start_seconds = convert_datetime_to_day_minutes(db_row['start_time']) * 60
            headway_seconds = db_row['headway_secs']
            
            current_seconds = start_seconds + headway_seconds
            end_seconds = convert_datetime_to_day_minutes(db_row['end_time']) * 60

            stop_times_data_s = db_row['stop_times_data']
            stop_times_data = extract_stop_times_data_from_s(stop_times_data_s)

            original_trip_id = db_row['trip_id']
            
            freq_idx = 1
            while current_seconds <= end_seconds:
                delta_seconds = current_seconds - start_seconds

                trip_id = f'{original_trip_id}.freq.{freq_idx}'
                stop_times_s_parts = []

                for stop_idx, stop_time_data in enumerate(stop_times_data):
                    stop_id = stop_time_data['stop_id']

                    new_stop_time = {
                        'trip_id': trip_id,
                        'arrival_time': None,
                        'departure_time': None,
                        'stop_id': stop_id,
                        'stop_sequence': stop_idx + 1,
                    }

                    stop_times_s_part = [
                        stop_id,
                    ]

                    arrival_seconds = stop_time_data['arrival_seconds']
                    if arrival_seconds is None:
                        stop_times_s_part.append('')
                    else:
                        new_stop_time['arrival_time'] = seconds_to_hhmmss(arrival_seconds + delta_seconds)
                        arrival_time_m = new_stop_time['arrival_time'][0:5]
                        stop_times_s_part.append(arrival_time_m)
                    
                    departure_seconds = stop_time_data['departure_seconds']
                    if departure_seconds is None:
                        stop_times_s_part.append('')
                    else:
                        new_stop_time['departure_time'] = seconds_to_hhmmss(departure_seconds + delta_seconds)
                        departure_time_m = new_stop_time['departure_time'][0:5]
                        stop_times_s_part.append(departure_time_m)

                    stop_times_s_parts.append('|'.join(stop_times_s_part))

                    stop_times_frequencies_table_csv_updater.prepare_row(new_stop_time)
                # loop stop_times

                departure_day_seconds = db_row['departure_day_minutes'] * 60 + delta_seconds
                departure_day_minutes = int(departure_day_seconds / 60)
                departure_time = seconds_to_hhmmss(departure_day_seconds)

                arrival_day_seconds = db_row['arrival_day_minutes'] * 60 + delta_seconds
                arrival_day_minutes = int(arrival_day_seconds / 60)
                arrival_time = seconds_to_hhmmss(arrival_day_seconds)

                stop_times_s = ' -- '.join(stop_times_s_parts)
                
                new_trip = {
                    'trip_id': trip_id,
                    'route_id': db_row['route_id'],
                    'service_id': db_row['service_id'],
                    'trip_headsign': db_row['trip_headsign'],
                    'trip_short_name': db_row['trip_short_name'],
                    'direction_id': db_row['direction_id'],
                    'block_id': db_row['block_id'],
                    'departure_day_minutes': departure_day_minutes,
                    'arrival_day_minutes': arrival_day_minutes,
                    'departure_time': departure_time,
                    'arrival_time': arrival_time,
                    'stop_times_s': stop_times_s,
                    'stop_times_count': db_row['stop_times_count'],
                    'shape_id': db_row['shape_id'],
                    'original_trip_id': db_row['original_trip_id'],
                    'hints': db_row['hints'],
                }

                trips_frequencies_csv_updater.prepare_row(new_trip)
                self._context.active_trip_ids.add(trip_id)

                current_seconds += headway_seconds
                freq_idx += 1
            # loop frequencies
            row_id += 1
        # loop DB trips-with-frequencies
        db_cursor.close()

        log_message(f'... saving CSV files')

        trips_frequencies_csv_updater.close()
        stop_times_frequencies_table_csv_updater.close()

        log_message(f'... load into DB')

        self._context.db_engine.load_csv_into_table(trips_table_name, trips_frequencies_table_csv_file_path)
        self._context.db_engine.load_csv_into_table(stop_times_table_name, stop_times_frequencies_table_csv_file_path)

        log_message(f'... DONE')
        print()
