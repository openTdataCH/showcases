import csv
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Dict, TypedDict, cast

from .calendar_filter import CalendarRow
from .helpers.csv_updater import CSV_Updater
from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class CalendarDateRow(TypedDict):
    service_id: str
    date: str
    exception_type: str


class CalendarExceptionGroupRow(TypedDict):
    service_id: str
    exceptions: str


class CalendarDatesFilter:
    def filter(
        self, source_gtfs_path: Path, db_engine: SQLiteDBEngine,
        date_from: date, date_to: date,
    ) -> None:
        db_engine.drop_and_recreate_table('calendar_dates')
        source_path = source_gtfs_path / 'calendar_dates.txt'
        if not source_path.is_file():
            log_message(f'Skipping calendar_dates.txt: source file not found at {source_path}')
            return

        log_message(f'Reading {source_path}')
        parsed_rows = 0
        kept_rows = 0
        writer = db_engine.create_csv_writer('calendar_dates')
        try:
            with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
                reader = csv.DictReader(source_file)
                for row in reader:
                    if parsed_rows % 5_000_000 == 0:
                        log_message(f'Parsed {parsed_rows} calendar_dates rows; kept {kept_rows}')
                    parsed_rows += 1

                    exception_date = datetime.strptime(row['date'], '%Y%m%d').date()
                    if exception_date < date_from or exception_date > date_to:
                        continue
                    if row['exception_type'] not in ('1', '2'):
                        raise ValueError(f"Invalid calendar_dates exception_type: {row['exception_type']}")

                    calendar_date_row: CalendarDateRow = {
                        'service_id': row['service_id'],
                        'date': row['date'],
                        'exception_type': row['exception_type'],
                    }
                    writer.prepare_row(calendar_date_row)
                    kept_rows += 1
        finally:
            writer.close()

        log_message(f'Loading {kept_rows} / {parsed_rows} calendar_dates rows into the intermediate database')
        db_engine.load_csv_into_table('calendar_dates', writer.csv_path)
        db_engine.add_table_indexes('calendar_dates')
        log_message(f'Stored {kept_rows} calendar_dates rows within the filter range')

    def apply_to_calendar(self, db_engine: SQLiteDBEngine) -> None:
        log_message('Grouping calendar_dates by service_id')
        exception_groups = cast(Dict[str, CalendarExceptionGroupRow], db_engine.query_map_by_field('''
            SELECT
                service_id,
                GROUP_CONCAT(date || '|' || exception_type, ',') AS exceptions
            FROM calendar_dates
            GROUP BY service_id
        ''', 'service_id'))

        csv_path = db_engine.db_path.parent / 'calendar_new.csv'
        column_names = db_engine.map_columns_metadata['calendar']['names']
        log_message(f'Writing updated calendar rows to {csv_path}')
        writer = CSV_Updater(csv_path, column_names)
        parsed_rows = 0
        updated_rows = 0
        try:
            with closing(db_engine.get_cursor()) as cursor:
                cursor.execute('SELECT * FROM calendar')
                for db_row in cursor:
                    calendar_row = cast(CalendarRow, dict(db_row))
                    exception_group = exception_groups.get(calendar_row['service_id'])
                    if exception_group is not None:
                        self._apply_exceptions(calendar_row, exception_group['exceptions'])
                        updated_rows += 1
                    writer.prepare_row(calendar_row)
                    parsed_rows += 1
                    if parsed_rows % 50_000 == 0:
                        log_message(f'Parsed {parsed_rows} calendar rows; updated day_bits for {updated_rows}')
        finally:
            writer.close()

        log_message(f'Recreating calendar and loading {parsed_rows} rows from {csv_path}')
        db_engine.drop_and_recreate_table('calendar')
        db_engine.load_csv_into_table('calendar', csv_path)
        log_message(f'Reloaded {parsed_rows} calendar rows; updated day_bits for {updated_rows}')

    def _apply_exceptions(self, calendar_row: CalendarRow, exceptions: str) -> None:
        start_date = datetime.strptime(calendar_row['start_date'], '%Y%m%d').date()
        day_bits = list(calendar_row['day_bits'])
        for exception in exceptions.split(','):
            date_value, exception_type = exception.split('|')
            exception_date = datetime.strptime(date_value, '%Y%m%d').date()
            day_index = (exception_date - start_date).days
            if day_index < 0 or day_index >= len(day_bits):
                continue
            if exception_type == '1':
                day_bits[day_index] = '1'
            elif exception_type == '2':
                day_bits[day_index] = '0'
            else:
                raise ValueError(f'Invalid calendar_dates exception_type: {exception_type}')
        calendar_row['day_bits'] = ''.join(day_bits)
