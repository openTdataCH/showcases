import sys
from pathlib import Path

import math
import calendar, datetime

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .helpers.file_helpers import compute_file_rows_no
from .import_context import ImportContext
from .import_types import CalendarDateServiceRow


class CalendarImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def log_date_range(self):
        start_date = self._context.calendar_data['start_date']
        end_date = self._context.calendar_data['end_date']
        log_message(f'Import date range (inclusive): {start_date:%Y-%m-%d} - {end_date:%Y-%m-%d}')

    def update_calendar(self):
        '''
        - add services defined only in calendar_dates
        - UPDATE calendar SET day_bits, start_date, end_date
        '''
        log_message('START update calendar')
        
        rows_no = self._context.db_engine.count_rows_table('calendar')
        formatted_rows_no = f'{rows_no:,}'.replace(',', "'")
        log_message(f'... found {formatted_rows_no} rows in calendar')
        print()

        calendar_dates_rows_no = self._context.db_engine.count_rows_table('calendar_dates')
        if rows_no == 0 and calendar_dates_rows_no == 0:
            raise ValueError('Cannot resolve services: calendar and calendar_dates are both empty')
        if calendar_dates_rows_no > 0:
            self._fill_calendar_from_calendar_dates()

        db_temp_path = self._context.db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/calendar_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['service_id', 'day_bits', 'start_date', 'end_date'])

        calendar_start_date = self._context.calendar_data['start_date']
        calendar_end_date = self._context.calendar_data['end_date']

        log_message('CALENDAR DATES:')

        calendar_days_no = self._context.calendar_data['days_no']
        calendar_weeks_no = math.ceil(calendar_days_no / 7)
        
        log_message(f'   START      : {calendar_start_date}')
        log_message(f'   END        : {calendar_end_date}')
        log_message(f'   DAYS NO    : {calendar_days_no}')
        log_message(f'   WEEKS NO   : {calendar_weeks_no}')
        print('')

        log_message(f"... running calendar + GROUP_CONCAT(calendar_dates) SQL")

        self._context.db_engine.run_sql("UPDATE calendar SET day_bits = ''")

        sql_path = self._context.map_sql_queries['select_calendar_dates_group_by']
        sql = load_sql_from_file(sql_path)

        calendar_days = list(calendar.day_name)

        db_cursor = self._context.db_engine.get_cursor()
        self._context.active_service_ids.clear()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 50_000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')

            service_id = db_row['service_id']
            day_bits = self._compute_calendar_day_bits(db_row, calendar_days, calendar_start_date, calendar_end_date)
            if '1' in day_bits:
                self._context.active_service_ids.add(service_id)

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
        self._context.db_engine.update_table_from_csv(table_csv_updater.csv_path, sql_template)

        active_services_no = len(self._context.active_service_ids)
        formatted_active_services_no = f'{active_services_no:,}'.replace(',', "'")
        log_message(f'Resolved {formatted_active_services_no} services active in the import date range')
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

    def _fill_calendar_from_calendar_dates(self):
        '''
        Add calendar rows for services defined only in calendar_dates.
        '''
        log_message(f'START filling calendar from calendar_dates')

        calendar_dates_rows_no = self._context.db_engine.count_rows_table('calendar_dates')
        if calendar_dates_rows_no == 0:
            print('ERROR - empty calendar, calendar_dates ?')
            sys.exit()
        log_message(f'... found {calendar_dates_rows_no} rows')

        sql = 'SELECT MIN(date) AS min_date FROM calendar_dates'
        min_date_s = self._context.db_engine.query(sql)[0]['min_date']

        sql = 'SELECT MAX(date) AS max_date FROM calendar_dates'
        max_date_s = self._context.db_engine.query(sql)[0]['max_date']

        sql = 'SELECT DISTINCT(service_id) AS service_id FROM calendar_dates'
        db_cursor = self._context.db_engine.get_cursor()

        table_name = 'calendar'
        calendar_table_writer = self._context.db_engine.create_csv_writer(table_name)
        
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

        self._context.db_engine.drop_and_recreate_table(table_name)
        self._context.db_engine.load_csv_into_table(table_name, calendar_table_writer.csv_path)
        self._context.db_engine.add_table_indexes(table_name)

        log_message(f'DONE _fill_calendar_from_calendar_dates')
        print()
