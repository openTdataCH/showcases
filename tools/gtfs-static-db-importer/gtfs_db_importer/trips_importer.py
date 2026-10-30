import csv
from contextlib import closing
from pathlib import Path
from typing import cast

from .helpers.csv_updater import CSV_Updater
from .helpers.file_helpers import compute_file_rows_no
from .helpers.gtfs_helpers import convert_datetime_to_day_minutes, extract_stop_times_data_from_s, massage_datetime_to_hhmm
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .import_types import MissingTripMinutesCountRow, TripIdRow, TripRouteIdRow
from .import_context import ImportContext


class TripsImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def load_active_trip_ids(self):
        log_message('Development shortcut: load_active_trip_ids should not be called in the final import flow')
        self._context.active_trip_ids.clear()
        self._context.active_route_ids.clear()
        sql = 'SELECT trip_id, route_id FROM trips'
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            for db_row in db_cursor.execute(sql):
                trip_row = cast(TripRouteIdRow, db_row)
                self._context.active_trip_ids.add(trip_row['trip_id'])
                self._context.active_route_ids.add(trip_row['route_id'])
            # loop trips DB rows
        # with
        formatted_trip_count = f'{len(self._context.active_trip_ids):,}'.replace(',', "'")
        log_message(f'Loaded {formatted_trip_count} active trip IDs from existing trips')
        print()

    def import_trips(self):
        log_message('START import trips')
        trips_path = self._context.gtfs_folder_path / 'trips.txt'
        log_message(f'Reading {trips_path}')
        total_rows = compute_file_rows_no(trips_path) - 1
        if total_rows < 0:
            total_rows = 0
        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Found {formatted_total_rows} trips rows')

        trips_writer = self._context.db_engine.create_csv_writer('trips')
        self._context.active_trip_ids.clear()
        self._context.active_route_ids.clear()
        row_count = 0
        kept_rows = 0
        try:
            with trips_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for trip_row in csv_reader:
                    if row_count % 500_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                        log_message(
                            f'... parsed {formatted_row_count} / {formatted_total_rows} trips rows; '
                            f'kept {formatted_kept_rows}'
                        )

                    # Keep only trips whose service runs within the resolved calendar range.
                    if trip_row['service_id'] in self._context.active_service_ids:
                        trips_writer.prepare_row(trip_row)
                        self._context.active_trip_ids.add(trip_row['trip_id'])
                        self._context.active_route_ids.add(trip_row['route_id'])
                        kept_rows += 1
                    row_count += 1
                # loop trips.txt CSV rows
            # with
        finally:
            trips_writer.close()

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        log_message(
            f'Parsed {formatted_row_count} / {formatted_total_rows} trips rows; '
            f'kept {formatted_kept_rows}'
        )
        self._context.db_engine.drop_and_recreate_table('trips')
        self._context.db_engine.load_csv_into_table('trips', trips_writer.csv_path)
        self._context.db_engine.add_table_indexes('trips')
        log_message(f'Imported {formatted_kept_rows} / {formatted_row_count} trips rows')
        log_message('DONE import trips')
        print()

    def update_trips(self):
        '''
        - DROP trips
        - batch INSERT trips with new columns (departure_ / arrival_ , stop_times_s)
        
        - batch UPDATE stop_times with arrival_time, departure_time = NULL for endpoints
        '''
        log_message('START update trips/stop_times')

        db_temp_path = self._context.db_engine.get_db_tmp_path()
        
        trips_table_name = 'trips'
        new_trips_table_csv_file_path = Path(f'{db_temp_path}/new_trips.csv')
        trips_column_names = self._context.db_engine.map_columns_metadata[trips_table_name]['names']
        new_trips_table_csv_updater = CSV_Updater(new_trips_table_csv_file_path, trips_column_names)

        map_stop_times_reset_table: dict[str, CSV_Updater] = {}
        for time_type in ['arrival_time', 'departure_time']:
            csv_path = Path(f'{db_temp_path}/stop_times_reset_{time_type}.csv')
            column_names = ['table_rowid']
            map_stop_times_reset_table[time_type] = CSV_Updater(csv_path, column_names)

        rows_no = self._context.db_engine.count_rows_table(trips_table_name)
        formatted_rows_no = f'{rows_no:,}'.replace(',', "'")
        log_message(f'... found {formatted_rows_no} trips')

        sql_path = self._context.map_sql_queries['select_stop_times_group_by']
        sql = load_sql_from_file(sql_path)

        log_message(f"... running SELECT trips / stop_times GROUP_BY SQL")

        db_cursor = self._context.db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 500_000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')

            stop_times_s = db_row['stop_times_data']
            stop_times = extract_stop_times_data_from_s(stop_times_s)
                
            trip_new_row = {}
            for column_name in trips_column_names:
                trip_new_row[column_name] = db_row[column_name]
            
            # reset time fields
            trip_new_row['departure_day_minutes'] = None
            trip_new_row['departure_time'] = None
            trip_new_row['arrival_day_minutes'] = None
            trip_new_row['arrival_time'] = None
            trip_new_row['stop_times_s'] = None
            trip_new_row['stop_times_count'] = None

            for stop_type in ['from', 'to']:
                db_rowid = None
                stop_time = None
                reset_time_field = None
                stop_day_minutes_datetime_field = None
                trip_day_minutes_field = None
                
                if stop_type == 'from':
                    stop_time = stop_times[0]
                    reset_time_field = 'arrival_time'
                    stop_day_minutes_datetime_field = 'departure_time'
                    trip_day_minutes_field = 'departure_day_minutes'
                else:
                    stop_time = stop_times[-1]
                    reset_time_field = 'departure_time'
                    stop_day_minutes_datetime_field = 'arrival_time'
                    trip_day_minutes_field = 'arrival_day_minutes'

                db_rowid = stop_time['sql_row_id']

                stop_times_row_dict = {
                    'table_rowid': db_rowid, 
                }
                map_stop_times_reset_table[reset_time_field].prepare_row(stop_times_row_dict)

                stop_time[reset_time_field] = None
                stop_day_minutes_datetime = stop_time[stop_day_minutes_datetime_field]
                if stop_day_minutes_datetime is None:
                    continue

                stop_day_minutes = convert_datetime_to_day_minutes(stop_day_minutes_datetime)

                trip_new_row[trip_day_minutes_field] = stop_day_minutes
                trip_new_row[stop_day_minutes_datetime_field] = stop_day_minutes_datetime
            # loop from/to

            trip_stop_times_values = []
            for stop_time in stop_times:
                stop_id = stop_time['stop_id']

                arrival_time = massage_datetime_to_hhmm(stop_time['arrival_time'])
                departure_time = massage_datetime_to_hhmm(stop_time['departure_time'])
                
                stop_time_value = f'{stop_id}|{arrival_time}|{departure_time}'
                trip_stop_times_values.append(stop_time_value)
            # loop stop_times

            trip_new_row['stop_times_s'] = ' -- '.join(trip_stop_times_values)
            trip_new_row['stop_times_count'] = len(stop_times)

            new_trips_table_csv_updater.prepare_row(trip_new_row)

            row_id += 1
        # loop trips SQL
        db_cursor.close()

        new_trips_table_csv_updater.close()
        print('')

        log_message(f"... INSERT new trips ...")
        self._context.db_engine.drop_and_recreate_table(trips_table_name)
        self._context.db_engine.load_csv_into_table(trips_table_name, new_trips_table_csv_file_path)
        self._context.db_engine.add_table_indexes(trips_table_name)
        log_message(f"... DONE")
        print('')

        log_message(f'... START UPDATE stop_times reset from/to NULL')

        for time_type, stop_times_updater in map_stop_times_reset_table.items():
            template_sql_path = self._context.map_sql_queries['update_stop_times_reset']
            template_sql = load_sql_from_file(template_sql_path)
            template_sql = template_sql.replace('[COLUMN_TO_RESET]', time_type)

            csv_path = stop_times_updater.csv_path
            self._context.db_engine.update_table_from_csv(csv_path, template_sql)

            log_message(f'... DONE UPDATE for {time_type}')
        # loop time_type
        print('')

    def check_trips_day_minutes(self):
        log_message('START check trips day minutes')

        missing_minutes_condition = 'departure_day_minutes = -1 OR arrival_day_minutes = -1'
        db_cursor = self._context.db_engine.get_cursor()
        try:
            db_cursor.execute(f'SELECT COUNT(*) AS trips_count FROM trips WHERE {missing_minutes_condition}')
            count_row = cast(MissingTripMinutesCountRow, db_cursor.fetchone())
            missing_trips_count = count_row['trips_count']

            if missing_trips_count > 0:
                db_cursor.execute(f'SELECT trip_id FROM trips WHERE {missing_minutes_condition} LIMIT 5')
                trip_ids = []
                for db_row in db_cursor:
                    trip_row = cast(TripIdRow, db_row)
                    trip_ids.append(trip_row['trip_id'])
                trip_ids_s = ', '.join(trip_ids)
                raise ValueError(
                    f'{missing_trips_count} trips still have departure_day_minutes or arrival_day_minutes '
                    f'set to -1 after updating trips. Example trip IDs: {trip_ids_s}'
                )
        finally:
            db_cursor.close()

        log_message('DONE check trips day minutes')
        print('')
