import csv
import datetime
from contextlib import closing
from pathlib import Path
from typing import Dict, Set, cast

from .helpers.csv_updater import CSV_Updater
from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .import_context import ImportContext
from .import_types import CalendarExceptionGroupRow, ServiceIdRow


class CalendarImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def log_date_range(self):
        start_date = self._context.calendar_data['start_date']
        end_date = self._context.calendar_data['end_date']
        log_message(f'Import date range (inclusive): {start_date:%Y-%m-%d} - {end_date:%Y-%m-%d}')
    
    def load_active_service_ids(self):
        log_message('Development shortcut: load_active_service_ids should not be called in the final import flow')
        self._context.active_service_ids.clear()
        sql = 'SELECT service_id FROM calendar'
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            for db_row in db_cursor.execute(sql):
                calendar_row = cast(ServiceIdRow, db_row)
                self._context.active_service_ids.add(calendar_row['service_id'])
            # loop calendar DB rows
        # with
        formatted_service_count = f'{len(self._context.active_service_ids):,}'.replace(',', "'")
        log_message(f'Loaded {formatted_service_count} active service IDs from existing calendar')
        print()

    def import_calendar(self):
        log_message('START import calendar')
        calendar_path = self._context.gtfs_folder_path / 'calendar.txt'
        calendar_dates_path = self._context.gtfs_folder_path / 'calendar_dates.txt'
        if not calendar_path.is_file() and not calendar_dates_path.is_file():
            raise ValueError('At least one of calendar.txt or calendar_dates.txt is required')

        # Load only exceptions within the inclusive import range into calendar_dates.
        self._import_calendar_dates(calendar_dates_path)
        print()

        calendar_writer = self._context.db_engine.create_csv_writer('calendar')
        seen_service_ids: Set[str] = set()
        self._context.active_service_ids.clear()
        try:
            if calendar_path.is_file():
                log_message(f'Reading {calendar_path}')
                total_rows = compute_file_rows_no(calendar_path) - 1
                if total_rows < 0:
                    total_rows = 0
                formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
                log_message(f'Found {formatted_total_rows} calendar rows')
                row_count = 0
                with calendar_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for calendar_row in csv_reader:
                        if row_count % 50_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            formatted_kept_rows = f'{len(self._context.active_service_ids):,}'.replace(',', "'")
                            log_message(
                                f'... parsed {formatted_row_count} / {formatted_total_rows} rows; '
                                f'kept {formatted_kept_rows}'
                            )

                        service_id = calendar_row['service_id']
                        # Fetch this service's exceptions; keep only one service's mapping in memory.
                        exceptions = self._read_service_exceptions(service_id)
                        
                        # Build the weekday pattern, apply exceptions, and write only active services.
                        self._write_active_service(calendar_row, exceptions, calendar_writer)
                        
                        # Mark inactive services too, so they are not processed again as exception-only services.
                        seen_service_ids.add(service_id)
                        row_count += 1
                    # loop calendar.txt CSV rows
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                formatted_kept_rows = f'{len(self._context.active_service_ids):,}'.replace(',', "'")
                log_message(
                    f'Parsed {formatted_row_count} / {formatted_total_rows} calendar rows; '
                    f'kept {formatted_kept_rows}'
                )

            # Handle services absent from calendar.txt, including feeds with only calendar_dates.txt.
            # Start with weekdays off, apply exceptions, and write only services with active days.
            self._write_exception_only_services(seen_service_ids, calendar_writer)
        finally:
            calendar_writer.close()

        # Load the retained calendar rows, then remove exceptions for discarded services.
        self._context.db_engine.drop_and_recreate_table('calendar')
        self._context.db_engine.load_csv_into_table('calendar', calendar_writer.csv_path)
        self._context.db_engine.add_table_indexes('calendar')
        self._context.db_engine.run_sql("""
            DELETE FROM calendar_dates
            WHERE NOT EXISTS (
                SELECT 1 FROM calendar
                WHERE calendar.service_id = calendar_dates.service_id
            )
        """)
        formatted_service_count = f'{len(self._context.active_service_ids):,}'.replace(',', "'")
        log_message(f'Imported {formatted_service_count} active services; inactive services were discarded')
        log_message('DONE import calendar')
        print()

    def _import_calendar_dates(self, calendar_dates_path: Path):
        start_date = self._context.calendar_data['start_date']
        end_date = self._context.calendar_data['end_date']
        calendar_dates_writer = self._context.db_engine.create_csv_writer('calendar_dates')
        kept_rows = 0
        row_count = 0
        try:
            if calendar_dates_path.is_file():
                log_message(f'START parse calendar_dates.txt from {calendar_dates_path}')
                total_rows = compute_file_rows_no(calendar_dates_path) - 1
                if total_rows < 0:
                    total_rows = 0
                formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
                log_message(f'... found {formatted_total_rows} calendar_dates rows')
                with calendar_dates_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for exception_row in csv_reader:
                        if row_count % 2_000_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                            log_message(
                                f'... parsed {formatted_row_count} / {formatted_total_rows} rows; '
                                f'kept {formatted_kept_rows}'
                            )

                        exception_date = datetime.datetime.strptime(exception_row['date'], '%Y%m%d')
                        if start_date <= exception_date <= end_date:
                            exception_type = exception_row['exception_type']
                            if exception_type != '1' and exception_type != '2':
                                raise ValueError(f'Invalid calendar_dates exception_type: {exception_type}')
                            calendar_dates_writer.prepare_row(exception_row)
                            kept_rows += 1
                        row_count += 1
                    # loop
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                log_message(f'Kept {formatted_kept_rows} / {formatted_row_count} rows (kept/parsed)')
        finally:
            calendar_dates_writer.close()

        self._context.db_engine.drop_and_recreate_table('calendar_dates')
        self._context.db_engine.load_csv_into_table('calendar_dates', calendar_dates_writer.csv_path)
        self._context.db_engine.add_table_indexes('calendar_dates')
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        log_message(f'DONE INSERT calendar_dates.txt')

    def _read_service_exceptions(self, service_id: str) -> Dict[int, str]:
        sql = """
            SELECT service_id, GROUP_CONCAT(date || '|' || exception_type) AS exception_dates
            FROM calendar_dates
            WHERE service_id = :service_id
            GROUP BY service_id
        """
        exceptions: Dict[int, str] = {}
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            db_cursor.execute(sql, {'service_id': service_id})
            db_row = db_cursor.fetchone()
            if db_row is not None:
                exception_group = cast(CalendarExceptionGroupRow, db_row)
                exceptions = self._parse_exceptions(exception_group['exception_dates'])
        # with
        return exceptions

    def _write_exception_only_services(self, seen_service_ids: Set[str], calendar_writer: CSV_Updater):
        sql = """
            SELECT service_id, GROUP_CONCAT(date || '|' || exception_type) AS exception_dates
            FROM calendar_dates
            GROUP BY service_id
        """
        start_date = self._context.calendar_data['start_date']
        end_date = self._context.calendar_data['end_date']
        row_count = 0
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            for db_row in db_cursor.execute(sql):
                if row_count % 50_000 == 0:
                    formatted_row_count = f'{row_count:,}'.replace(',', "'")
                    log_message(f'... checked {formatted_row_count} calendar_dates service groups')

                exception_group = cast(CalendarExceptionGroupRow, db_row)
                service_id = exception_group['service_id']
                if service_id not in seen_service_ids:
                    exceptions = self._parse_exceptions(exception_group['exception_dates'])
                    calendar_row = {
                        'service_id': service_id,
                        'monday': '0',
                        'tuesday': '0',
                        'wednesday': '0',
                        'thursday': '0',
                        'friday': '0',
                        'saturday': '0',
                        'sunday': '0',
                        'start_date': start_date.strftime('%Y%m%d'),
                        'end_date': end_date.strftime('%Y%m%d'),
                    }
                    self._write_active_service(calendar_row, exceptions, calendar_writer)
                row_count += 1
            # loop
        # with

    def _parse_exceptions(self, exception_dates: str) -> Dict[int, str]:
        exceptions: Dict[int, str] = {}
        start_date = self._context.calendar_data['start_date']
        for exception in exception_dates.split(','):
            date_s, exception_type = exception.split('|')
            exception_date = datetime.datetime.strptime(date_s, '%Y%m%d')
            day_index = (exception_date - start_date).days
            if exception_type == '1':
                day_bit = '1'
            else:
                day_bit = '0'
            exceptions[day_index] = day_bit
        # loop
        return exceptions

    def _write_active_service(self, calendar_row: Dict[str, str], exceptions: Dict[int, str],
                              calendar_writer: CSV_Updater):
        start_date = self._context.calendar_data['start_date']
        end_date = self._context.calendar_data['end_date']
        service_start = datetime.datetime.strptime(calendar_row['start_date'], '%Y%m%d')
        service_end = datetime.datetime.strptime(calendar_row['end_date'], '%Y%m%d')
        if service_start < start_date:
            service_start = start_date
        if service_end > end_date:
            service_end = end_date

        day_bits = ['0'] * self._context.calendar_data['days_no']
        weekday_columns = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_date = service_start
        while current_date <= service_end:
            weekday_column = weekday_columns[current_date.weekday()]
            if int(calendar_row[weekday_column]) == 1:
                day_index = (current_date - start_date).days
                day_bits[day_index] = '1'
            current_date += datetime.timedelta(days=1)
        # loop
        for day_index, day_bit in exceptions.items():
            day_bits[day_index] = day_bit
        # loop
        
        # discard calendars out of from/to range
        if '1' not in day_bits:
            return

        service_id = calendar_row['service_id']
        calendar_row['day_bits'] = ''.join(day_bits)
        calendar_row['start_date'] = start_date.strftime('%Y%m%d')
        calendar_row['end_date'] = end_date.strftime('%Y%m%d')
        calendar_writer.prepare_row(calendar_row)
        self._context.active_service_ids.add(service_id)
