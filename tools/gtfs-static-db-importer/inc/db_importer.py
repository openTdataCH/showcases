import os, sys

from pathlib import Path

import math
import yaml
from typing import Optional, TypedDict, cast

import calendar, datetime

from .shared.inc.helpers.db_engine import SQLiteDBEngine
from .shared.inc.controllers.bo_controller import BusinessOrganisationGtfsRtCsvRow
from .shared.inc.models.gtfs.agency import AgencyDB

from .shared.inc.helpers.csv_helpers import read_csv_rows
from .shared.inc.helpers.csv_updater import CSV_Updater
from .shared.inc.helpers.gtfs_helpers import convert_datetime_to_day_minutes, extract_stop_times_data_from_s, massage_datetime_to_hhmm, seconds_to_hhmmss
from .shared.inc.helpers.log_helpers import log_message
from .shared.inc.helpers.db_helpers import load_sql_from_file
from .shared.inc.helpers.file_helpers import compute_file_rows_no

class CalendarData(TypedDict):
    start_date: datetime.datetime
    end_date: datetime.datetime
    days_no: int

class StationRoutesDayBitsRow(TypedDict):
    station_id: str
    day_bits: str
    routes_day_bits: Optional[str]

class StationIdRow(TypedDict):
    station_id: str

class StopMissingParentRow(TypedDict):
    stop_id: str
    parent_station: str

class GTFS_DB_Importer:
    _map_sql_queries: dict[str, str]
    _db_engine: SQLiteDBEngine
    
    _gtfs_folder_path: Path
    _db_lock_path: Path
    _bo_realtime_csv_path: Path
    _calendar_data: CalendarData

    def __init__(self, app_config, gtfs_folder_path: Path, db_path: Path):
        self._map_sql_queries = app_config['map_sql_queries']

        script_path = Path(os.path.realpath(__file__))
        db_schema_path = Path(f"{script_path.parent}/config/gtfs_schema.yml")
        self._db_engine = SQLiteDBEngine.init_read_write(db_path, db_schema_path=db_schema_path)
        
        self._gtfs_folder_path = gtfs_folder_path
        self._db_lock_path = Path(f'{self._db_engine.db_path}.lock')
        self._bo_realtime_csv_path = Path(app_config['bo_realtime_csv_path'])

    def start(self):
        log_message("START GTFS IMPORT")
        log_message(f'GTFS PATH : {self._gtfs_folder_path}')
        log_message(f'DB PATH   : {self._db_engine.db_path}')
        print()
        
        if os.path.isfile(self._db_lock_path):
            print('ERROR: lock path present, ABORT')
            print(f'ls -al {self._db_lock_path.parent}')
            sys.exit(1)
        #
        
        self._write_lock_file()

        self._import_csv_tables()
        
        self._resolve_day_bits_date_range()
        self._populate_agency_gtfs_rt()
        self._check_stops_parent_depth()
        self._check_stops_missing_parents()

        self._update_calendar()
        self._update_trips()
        self._update_frequencies()
        self._update_routes()
        self._populate_stations()
        self._update_stations_day_bits()
        self._update_agency_day_bits()
        self._update_routes_representative_trip()
        self._create_fts_routes()
        
        self._cleanup()
        
        self._remove_lock_file()

        log_message("DONE GTFS IMPORT")

    # private
    def _load_schema_config(self):
        script_path = Path(os.path.realpath(__file__))
        db_schema_path = f"{script_path.parent}/config/gtfs_schema.yml"
        db_schema_config = yaml.safe_load(open(db_schema_path, encoding='utf-8'))

        return db_schema_config
    
    def _write_lock_file(self):
        now_f = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lock_file_text = f'START: {now_f}'
        lock_file = open(self._db_lock_path, 'w', encoding='utf-8')
        lock_file.write(lock_file_text)
        lock_file.close()
        
    def _remove_lock_file(self):
        os.remove(self._db_lock_path)

    def _populate_agency_gtfs_rt(self):
        log_message(f'START populate GTFS-RT status')

        map_gtfs_agency = cast(dict[str, AgencyDB], self._db_engine.query_table_map_by_field('agency', 'agency_id'))
        
        map_gtfs_rt_agency_ids: dict[str, bool] = {}
        for csv_row in read_csv_rows(self._bo_realtime_csv_path, delimiter=';'):
            bo_csv_row = cast(BusinessOrganisationGtfsRtCsvRow, csv_row)

            agency_lookup_id = bo_csv_row['vdvBetreiberId']
            agency_id_parts = agency_lookup_id.split(':')
            if len(agency_id_parts) != 2:
                raise ValueError(f'Unexpected delimiter for vdvBetreiberId: {agency_lookup_id}')
            
            agency_id = agency_id_parts[1]
            if agency_id not in map_gtfs_agency:
                continue

            map_gtfs_rt_agency_ids[agency_id] = True
        # loop csv rows

        table_name = 'link_agency'
        self._db_engine.drop_and_recreate_table(table_name)
        table_csv_writer = self._db_engine.create_csv_writer(table_name)

        for agency_id, agency in map_gtfs_agency.items():
            has_gtfs_rt = 1 if agency_id in map_gtfs_rt_agency_ids else 0

            row_dict = {
                'agency_id': agency_id,
                'has_gtfs_rt': has_gtfs_rt,
            }
            table_csv_writer.prepare_row(row_dict)
        # loop agencies

        table_csv_writer.close()

        self._db_engine.load_csv_into_table(table_name, table_csv_writer.csv_path)
        self._db_engine.add_table_indexes(table_name)

        log_message(f'... DONE')
        print()
    
    def _check_stops_parent_depth(self):
        log_message('START check stops parent depth')

        sql_path = self._map_sql_queries['select_stops_exceeding_parent_depth']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._db_engine.get_cursor()
        db_cursor.execute(sql)
        invalid_stop = db_cursor.fetchone()
        db_cursor.close()

        if invalid_stop is not None:
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

        sql_path = self._map_sql_queries['select_stops_missing_parents']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._db_engine.get_cursor()
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

    def _import_csv_tables(self):
        '''
        Batch TRUNCATE / INSERT csv rows from GTFS in db.
        '''
        table_names = ['agency', 'calendar', 'calendar_dates', 'feed_info', 'frequencies', 'routes', 'shapes', 'stop_times', 'stops', 'transfers', 'trips']

        log_message(f'START BATCH IMPORT')

        for table_name in table_names:
            log_message(f'... TABLE: {table_name}')
            if not table_name in self._db_engine.map_columns_metadata:
                print(f'ERROR - missing config for table {table_name}')
                sys.exit(1)

            self._db_engine.drop_and_recreate_table(table_name)

            gtfs_file_path = Path(f'{self._gtfs_folder_path}/{table_name}.txt')
            if not os.path.isfile(gtfs_file_path):
                is_skip_ok = False

                if table_name in ['feed_info', 'frequencies', 'shapes', 'transfers']:
                    is_skip_ok = True

                if table_name == 'calendar':
                    calendar_dates_path = f'{self._gtfs_folder_path}/calendar_dates.txt'
                    if os.path.isfile(calendar_dates_path):
                        log_message('... no calendar found, using calendar_dates instead')
                        is_skip_ok = True
                
                if is_skip_ok:
                    continue
                else:
                    print(f'ERROR = required table "{table_name}" not found {gtfs_file_path}')
                    sys.exit()
            # endif check if file exists

            self._db_engine.load_csv_into_table(table_name, gtfs_file_path)
            self._db_engine.add_table_indexes(table_name)
        # loop table names
        print()
        
        log_message(f'... DONE BATCH IMPORT')
        print('')

    def _update_calendar(self):
        '''
        - if calendar.txt is missing
            INSERT into calendar.txt DISTINCT rows from calendar_dates
        - UPDATE calendar SET day_bits, start_date, end_date
        '''
        log_message('START update calendar')
        
        rows_no = self._db_engine.count_rows_table('calendar')
        formatted_rows_no = f'{rows_no:,}'.replace(',', "'")
        log_message(f'... found {formatted_rows_no} rows in calendar')
        print()

        if rows_no == 0:
            self._fill_calendar_from_calendar_dates()

        db_temp_path = self._db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/calendar_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['service_id', 'day_bits', 'start_date', 'end_date'])

        calendar_start_date = self._calendar_data['start_date']
        calendar_end_date = self._calendar_data['end_date']

        log_message('CALENDAR DATES:')

        calendar_days_no = self._calendar_data['days_no']
        calendar_weeks_no = math.ceil(calendar_days_no / 7)
        
        log_message(f'   START      : {calendar_start_date}')
        log_message(f'   END        : {calendar_end_date}')
        log_message(f'   DAYS NO    : {calendar_days_no}')
        log_message(f'   WEEKS NO   : {calendar_weeks_no}')
        print('')

        log_message(f"... running calendar + GROUP_CONCAT(calendar_dates) SQL")

        self._db_engine.run_sql("UPDATE calendar SET day_bits = ''")

        sql_path = self._map_sql_queries['select_calendar_dates_group_by']
        sql = load_sql_from_file(sql_path)

        calendar_days = list(calendar.day_name)

        db_cursor = self._db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 10000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')

            service_id = db_row['service_id']
            day_bits = self._compute_calendar_day_bits(db_row, calendar_days, calendar_start_date, calendar_end_date)

            row_dict = {
                'service_id': service_id,
                'day_bits': day_bits,
                'start_date': calendar_start_date.strftime("%Y%m%d"),
                'end_date': calendar_end_date.strftime("%Y%m%d"),
            }
            table_csv_updater.prepare_row(row_dict)
            
            row_id += 1
        db_cursor.close()
        print()

        table_csv_updater.close()

        log_message(f'DB_Table_CSV_Updater: START UPDATE from CSV: {table_csv_path.name}')
        lines_no = compute_file_rows_no(table_csv_path) - 1
        formatted_lines_no = f'{lines_no:,}'.replace(',', "'")
        log_message(f'... found {formatted_lines_no} rows')

        sql_template = 'UPDATE calendar SET day_bits = :day_bits, start_date = :start_date, end_date = :end_date WHERE service_id = :service_id'
        self._db_engine.update_table_from_csv(table_csv_updater.csv_path, sql_template)

        log_message('DONE update calendar')
        print('')

    def _compute_calendar_day_bits(self, calendar_db_row, calendar_days, calendar_start_date, calendar_end_date):
        start_date_s = calendar_db_row['start_date']
        end_date_s = calendar_db_row['end_date']

        start_date = datetime.datetime.strptime(start_date_s, "%Y%m%d")
        if start_date < calendar_start_date:
            start_date = calendar_start_date

        end_date = datetime.datetime.strptime(end_date_s, "%Y%m%d")
        if end_date > calendar_end_date:
            end_date = calendar_end_date

        days_no = (end_date - start_date).days
        weeks_no = math.ceil((days_no + 1) / 7)

        map_weekdays_pattern = {}
        for calendar_day in calendar_days:
            day_key = calendar_day.lower()
            is_enabled = int(calendar_db_row[day_key]) == 1
            map_weekdays_pattern[calendar_day] = is_enabled

        if start_date > end_date:
            feed_days_no = (calendar_end_date - calendar_start_date).days + 1
            day_bits = '0' * feed_days_no
        else:
            day_bits_list = self._fill_day_bits_pattern(start_date, end_date, weeks_no, map_weekdays_pattern)
            day_bits = ''.join(day_bits_list)

            days_no_before = (start_date - calendar_start_date).days
            days_no_after = (calendar_end_date - end_date).days

            day_bits = '0' * days_no_before + day_bits + '0' * days_no_after

        day_bits_list = list(day_bits)
        self._update_day_bits_from_calendar_dates(day_bits_list, calendar_db_row, calendar_start_date)
        day_bits = ''.join(day_bits_list)

        return day_bits

    def _fill_day_bits_pattern(self, start_date, end_date, weeks_no, map_weekdays_pattern):
        day_bits_7d = []
        current_date = start_date
        while current_date <= end_date:
            weekday_s = current_date.strftime("%A")
            day_bit = '1' if map_weekdays_pattern[weekday_s] else '0'
            day_bits_7d.append(day_bit)
            
            current_date = current_date + datetime.timedelta(days=1)

            if len(day_bits_7d) == 7:
                break

        day_bits_s = ''.join(day_bits_7d) * weeks_no
        days_no = (end_date - start_date).days
        day_bits_end_idx = days_no + 1
        day_bits_s = day_bits_s[0:day_bits_end_idx]

        day_bits = list(day_bits_s)

        return day_bits
    
    def _update_day_bits_from_calendar_dates(self, day_bits_list, calendar_db_row, start_date):
        calendar_dates_cno = calendar_db_row['calendar_dates_cno']
        if calendar_dates_cno == 0:
            return

        exception_dates = calendar_db_row['exception_dates'].split(',')

        for calendar_dates_s in exception_dates:
            (date_s, exception_type_s) = calendar_dates_s.split('|')
            row_date = datetime.datetime.strptime(date_s, "%Y%m%d")
            exception_type = int(exception_type_s)

            day_bit = None
            if exception_type == 1:
                day_bit = '1'
            if exception_type == 2:
                day_bit = '0'
            if not day_bit:
                print(f'ERROR - cant interpret exception_type {calendar_dates_s}')
                sys.exit()

            day_idx = (row_date-start_date).days
            if day_idx < 0:
                continue
            if day_idx >= len(day_bits_list):
                continue
            day_bits_list[day_idx] = day_bit

    def _update_trips(self):
        '''
        - DROP trips
        - batch INSERT trips with new columns (departure_ / arrival_ , stop_times_s)
        '''
        log_message('START update trips/stop_times')

        db_temp_path = self._db_engine.get_db_tmp_path()
        
        trips_table_name = 'trips'
        new_trips_table_csv_file_path = Path(f'{db_temp_path}/new_trips.csv')
        trips_column_names = self._db_engine.map_columns_metadata[trips_table_name]['names']
        new_trips_table_csv_updater = CSV_Updater(new_trips_table_csv_file_path, trips_column_names)

        map_stop_times_reset_table: dict[str, CSV_Updater] = {}
        for time_type in ['arrival_time', 'departure_time']:
            csv_path = Path(f'{db_temp_path}/stop_times_reset_{time_type}.csv')
            column_names = ['table_rowid']
            map_stop_times_reset_table[time_type] = CSV_Updater(csv_path, column_names)

        rows_no = self._db_engine.count_rows_table(trips_table_name)
        formatted_rows_no = f'{rows_no:,}'.replace(',', "'")
        log_message(f'... found {formatted_rows_no} trips')

        sql_path = self._map_sql_queries['select_stop_times_group_by']
        sql = load_sql_from_file(sql_path)

        log_message(f"... running SELECT trips / stop_times GROUP_BY SQL")

        db_cursor = self._db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 200_000 == 0:
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
        self._db_engine.drop_and_recreate_table(trips_table_name)
        self._db_engine.load_csv_into_table(trips_table_name, new_trips_table_csv_file_path)
        self._db_engine.add_table_indexes(trips_table_name)
        log_message(f"... DONE")
        print('')

        log_message(f'... START UPDATE stop_times reset from/to NULL')

        for time_type, stop_times_updater in map_stop_times_reset_table.items():
            template_sql_path = self._map_sql_queries['update_stop_times_reset']
            template_sql = load_sql_from_file(template_sql_path)
            template_sql = template_sql.replace('[COLUMN_TO_RESET]', time_type)

            csv_path = stop_times_updater.csv_path
            self._db_engine.update_table_from_csv(csv_path, template_sql)

            log_message(f'... DONE UPDATE for {time_type}')
        # loop time_type
        print('')
    # _update_trips
    
    def _update_routes(self):
        '''
        - DROP routes
        - batch INSERT routes with new columns (day_bits)
        '''
        log_message('START update routes')

        map_db_routes = self._db_engine.query_table_map_by_field('routes', 'route_id')
        
        sql_path = self._map_sql_queries['select_route_trips_calendar_day_bits']
        sql = load_sql_from_file(sql_path)
        
        log_message(f"... running select_route_trips_calendar_day_bits SQL")

        db_cursor = self._db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 1000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')
                
            trips_day_bits_s: str = db_row['trips_day_bits']
            if trips_day_bits_s is None:
                print(db_row)
                raise ValueError('calendar.day_bits is not computed')
            trips_day_bits = trips_day_bits_s.split(',')
            
            route_day_bits = ['0'] * len(trips_day_bits[0])
            for trip_day_bits in trips_day_bits:
                for idx, day_bit in enumerate(trip_day_bits):
                    if day_bit == '1':
                        route_day_bits[idx] = '1'
                        
            route_day_bits_s = ''.join(route_day_bits)
            
            route_id = db_row['route_id']
            map_db_routes[route_id]['day_bits'] = route_day_bits_s

            row_id += 1
        # loop SQL

        log_message(f"... INSERT new routes ...")

        db_temp_path = self._db_engine.get_db_tmp_path()

        table_name = 'routes'
        table_csv_file_path = Path(f'{db_temp_path}/new_routes.csv')
        table_column_names = self._db_engine.map_columns_metadata[table_name]['names']
        new_routes_table_csv_updater = CSV_Updater(table_csv_file_path, table_column_names)
        
        for route_id, db_route in map_db_routes.items():
            new_routes_table_csv_updater.prepare_row(db_route)
        
        new_routes_table_csv_updater.close()
        
        self._db_engine.drop_and_recreate_table(table_name)
        self._db_engine.load_csv_into_table(table_name, table_csv_file_path)
        self._db_engine.add_table_indexes(table_name)

        log_message(f"... DONE")
        print('')
        
    def _resolve_day_bits_date_range(self):
        feed_info_rows = self._db_engine.query('SELECT feed_start_date, feed_end_date FROM feed_info')
        if len(feed_info_rows) == 1:
            feed_info_row = feed_info_rows[0]
            start_date_s = feed_info_row['feed_start_date']
            end_date_s = feed_info_row['feed_end_date']
            if start_date_s and end_date_s:
                try:
                    start_date = datetime.datetime.strptime(start_date_s, '%Y%m%d')
                    end_date = datetime.datetime.strptime(end_date_s, '%Y%m%d')
                except ValueError:
                    log_message('Invalid feed_info dates; deriving the day_bits range from calendar data')
                else:
                    if start_date <= end_date:
                        self._set_calendar_data(start_date, end_date)
                        log_message(f'Day bits range from feed_info: {start_date:%Y%m%d} - {end_date:%Y%m%d}')
                        return

        date_rows = self._db_engine.query('SELECT MIN(start_date) AS start_date, MAX(end_date) AS end_date FROM calendar')
        date_row = date_rows[0]
        date_source = 'calendar'
        if date_row['start_date'] is None or date_row['end_date'] is None:
            date_rows = self._db_engine.query('SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM calendar_dates')
            date_row = date_rows[0]
            date_source = 'calendar_dates'

        if date_row['start_date'] is None or date_row['end_date'] is None:
            raise ValueError('Cannot determine day_bits dates from feed_info, calendar or calendar_dates')

        start_date = datetime.datetime.strptime(date_row['start_date'], '%Y%m%d')
        end_date = datetime.datetime.strptime(date_row['end_date'], '%Y%m%d')
        today_date = datetime.datetime.combine(datetime.datetime.today(), datetime.datetime.min.time())
        max_days_no = 366
        if (today_date - start_date).days > max_days_no:
            start_date = today_date - datetime.timedelta(days=max_days_no)
        if (end_date - today_date).days > max_days_no:
            end_date = today_date + datetime.timedelta(days=max_days_no)
        if end_date < start_date:
            raise ValueError('Calendar date range is empty after applying the 366-day limits')

        self._set_calendar_data(start_date, end_date)
        log_message(f'Day bits range from {date_source}, with 366-day limits: {start_date:%Y%m%d} - {end_date:%Y%m%d}')

    def _set_calendar_data(self, start_date: datetime.datetime, end_date: datetime.datetime):
        days_no = (end_date - start_date).days + 1
        self._calendar_data = {
            'start_date': start_date,
            'end_date': end_date,
            'days_no': days_no,
        }

    def _populate_stations(self):
        log_message('START populate stations')

        sql_path = self._map_sql_queries['select_stations']
        sql = load_sql_from_file(sql_path)

        days_no = self._calendar_data['days_no']

        table_name = 'stations'
        table_csv_writer = self._db_engine.create_csv_writer(table_name)
        empty_day_bits = '0' * days_no

        db_cursor = self._db_engine.get_cursor()
        for db_row in db_cursor.execute(sql):
            station_row = cast(StationIdRow, db_row)
            row_dict = {
                'station_id': station_row['station_id'],
                'day_bits': empty_day_bits,
            }
            table_csv_writer.prepare_row(row_dict)

        db_cursor.close()
        table_csv_writer.close()

        self._db_engine.drop_and_recreate_table(table_name)
        self._db_engine.load_csv_into_table(table_name, table_csv_writer.csv_path)
        self._db_engine.add_table_indexes(table_name)

        sql_path = self._map_sql_queries['update_stops_synthetic_station']
        sql = load_sql_from_file(sql_path)
        self._db_engine.run_sql_script(sql)

        log_message('DONE populate stations')
        print('')

    def _update_stations_day_bits(self):
        log_message('START update stations day_bits')

        sql_path = self._map_sql_queries['select_station_routes_day_bits']
        sql = load_sql_from_file(sql_path)

        db_temp_path = self._db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/stations_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['station_id', 'day_bits'])

        stations_cursor = self._db_engine.get_cursor()
        db_cursor = self._db_engine.get_cursor()
        row_id = 0
        for station_db_row in stations_cursor.execute('SELECT station_id FROM stations'):
            if row_id % 10_000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} stations')

            station_id_row = cast(StationIdRow, station_db_row)
            station_id = station_id_row['station_id']
            db_cursor.execute(sql, {'station_id': station_id})
            db_row = db_cursor.fetchone()

            if db_row is None:
                continue
            
            station_row = cast(StationRoutesDayBitsRow, db_row)
            routes_day_bits_s = station_row['routes_day_bits']
            
            if routes_day_bits_s is None:
                continue

            stop_day_bits = list(station_row['day_bits'])
            routes_day_bits = routes_day_bits_s.split(',')
            for route_day_bits in routes_day_bits:
                for idx, day_bit in enumerate(route_day_bits):
                    if day_bit == '1':
                        stop_day_bits[idx] = '1'

            stop_day_bits_s = ''.join(stop_day_bits)
            row_dict = {
                'station_id': station_row['station_id'],
                'day_bits': stop_day_bits_s,
            }
            table_csv_updater.prepare_row(row_dict)

            row_id += 1
        # loop

        stations_cursor.close()
        db_cursor.close()
        table_csv_updater.close()

        sql_template = 'UPDATE stations SET day_bits = :day_bits WHERE station_id = :station_id'
        self._db_engine.update_table_from_csv(table_csv_path, sql_template)

        log_message('DONE update stations day_bits')
        print('')

    def _update_agency_day_bits(self):
        log_message('START update link_agency day_bits')

        sql_path = self._map_sql_queries['select_agency_routes_day_bits']
        sql = load_sql_from_file(sql_path)

        db_temp_path = self._db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/link_agency_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['agency_id', 'day_bits'])

        db_cursor = self._db_engine.get_cursor()
        for db_row in db_cursor.execute(sql):
            routes_day_bits_s = db_row['routes_day_bits']
            if routes_day_bits_s is None:
                continue

            routes_day_bits = routes_day_bits_s.split(',')
            agency_day_bits = ['0'] * len(routes_day_bits[0])
            for route_day_bits in routes_day_bits:
                for idx, day_bit in enumerate(route_day_bits):
                    if day_bit == '1':
                        agency_day_bits[idx] = '1'

            agency_day_bits_s = ''.join(agency_day_bits)
            row_dict = {
                'agency_id': db_row['agency_id'],
                'day_bits': agency_day_bits_s,
            }
            table_csv_updater.prepare_row(row_dict)

        db_cursor.close()
        table_csv_updater.close()

        sql_template = 'UPDATE link_agency SET day_bits = :day_bits WHERE agency_id = :agency_id'
        self._db_engine.update_table_from_csv(table_csv_path, sql_template)

        log_message('DONE update link_agency day_bits')
        print('')

    def _update_routes_representative_trip(self):
        '''
        - UPDATE routes SET representative_trip_id
        '''
        log_message(f"START UPDATE routes-trip (representative)")
        
        sql_path = self._map_sql_queries['update_routes_representative_trip']
        sql = load_sql_from_file(sql_path)
        self._db_engine.run_sql_script(sql)
        
        log_message(f"... DONE UPDATE routes-trip (representative)")
        print('')
        
    def _create_fts_routes(self):
        '''
        - CREATE fts_routes from SQL
        '''
        log_message(f"START CREATE FTS routes ...")
        
        sql_path = self._map_sql_queries['create_fts_routes']
        sql = load_sql_from_file(sql_path)
        self._db_engine.run_sql_script(sql)
        
        log_message(f"... DONE FTS routes ...")
        print('')

    def _fill_calendar_from_calendar_dates(self):
        '''
        INSERT into calendar.txt DISTINCT rows from calendar_dates
        '''
        log_message(f'START filling calendar from calendar_dates')

        calendar_dates_rows_no = self._db_engine.count_rows_table('calendar_dates')
        if calendar_dates_rows_no == 0:
            print('ERROR - empty calendar, calendar_dates ?')
            sys.exit()
        log_message(f'... found {calendar_dates_rows_no} rows')

        sql = 'SELECT MIN(date) AS min_date FROM calendar_dates'
        min_date_s = self._db_engine.query(sql)[0]['min_date']

        sql = 'SELECT MAX(date) AS max_date FROM calendar_dates'
        max_date_s = self._db_engine.query(sql)[0]['max_date']

        sql = 'SELECT DISTINCT(service_id) AS service_id FROM calendar_dates'
        db_cursor = self._db_engine.get_cursor()

        table_name = 'calendar'
        calendar_table_writer = self._db_engine.create_csv_writer(table_name)
        
        row_idx = 0
        for db_row in db_cursor.execute(sql):
            trip_new_row = {
                'service_id': db_row['service_id'],
                'monday': 0, 
                'tuesday': 0, 
                'wednesday': 0, 
                'thursday': 0, 
                'friday': 0, 
                'saturday': 0, 
                'sunday': 0, 
                'start_date': min_date_s, 
                'end_date': max_date_s, 
                'day_bits': '',
            }
            calendar_table_writer.prepare_row(trip_new_row)

            row_idx += 1
        #end loop SQL
        db_cursor.close()

        calendar_table_writer.close()

        log_message(f'... found {row_idx} calendar entries')

        log_message(f'START populate table calendar')

        self._db_engine.drop_and_recreate_table(table_name)
        self._db_engine.load_csv_into_table(table_name, calendar_table_writer.csv_path)
        self._db_engine.add_table_indexes(table_name)

        log_message(f'DONE _fill_calendar_from_calendar_dates')
        print()

    def _cleanup(self):
        log_message('START cleaning up tmp folder, VACUUM')
        self._db_engine.cleanup()
        log_message('... DONE')
        print()

    def _update_frequencies(self):
        '''
        INSERT into trips, stop_times from frequencies.txt
        '''
        log_message(f'START parsing frequencies...')

        db_temp_path = self._db_engine.get_db_tmp_path()

        trips_table_name = 'trips'
        trips_column_names = self._db_engine.map_columns_metadata[trips_table_name]['names']
        trips_frequencies_table_csv_file_path = Path(f'{db_temp_path}/trips_frequencies.csv')
        trips_frequencies_csv_updater = CSV_Updater(trips_frequencies_table_csv_file_path, trips_column_names)

        stop_times_table_name = 'stop_times'
        stop_times_column_names = self._db_engine.map_columns_metadata[stop_times_table_name]['names']
        stop_times_frequencies_table_csv_file_path = Path(f'{db_temp_path}/stop_times_frequencies.csv')
        stop_times_frequencies_table_csv_updater = CSV_Updater(stop_times_frequencies_table_csv_file_path, stop_times_column_names)

        sql_path = self._map_sql_queries['select_trips_group_by_stop_times_frequencies']
        sql = load_sql_from_file(sql_path)

        log_message(f"... running select_stop_times_group_by + frequencies SQL")

        db_cursor = self._db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 1_000 == 0:
                log_message(f'... parsed {row_id} rows')

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

                current_seconds += headway_seconds
                freq_idx += 1
            # loop frequencies
        # loop DB trips-with-frequencies

        log_message(f'... saving CSV files')

        trips_frequencies_csv_updater.close()
        stop_times_frequencies_table_csv_updater.close()

        log_message(f'... load into DB')

        self._db_engine.load_csv_into_table(trips_table_name, trips_frequencies_table_csv_file_path)
        self._db_engine.load_csv_into_table(stop_times_table_name, stop_times_frequencies_table_csv_file_path)

        log_message(f'... DONE')
        print()
    # _update_frequencies
