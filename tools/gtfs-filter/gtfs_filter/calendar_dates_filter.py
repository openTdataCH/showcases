import csv
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class CalendarDateUpdate(TypedDict):
    service_id: str
    start_date: str
    end_date: str
    day_bits: str
    day_index: int
    day_bit: str


class CalendarDatesFilter:
    def filter(
        self, source_gtfs_path: Path, db_engine: SQLiteDBEngine,
        date_from: date, date_to: date,
    ) -> None:
        source_path = source_gtfs_path / 'calendar_dates.txt'
        if not source_path.is_file():
            log_message(f'Skipping calendar_dates.txt: source file not found at {source_path}')
            return

        log_message(f'Reading {source_path}')
        days_no = (date_to - date_from).days + 1
        empty_day_bits = '0' * days_no
        parsed_rows = 0
        updated_rows = 0
        with closing(db_engine.get_cursor()) as cursor:
            with cursor.connection:
                with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
                    reader = csv.DictReader(source_file)
                    for row in reader:
                        parsed_rows += 1
                        if parsed_rows % 100_000 == 0:
                            log_message(f'Parsed {parsed_rows} calendar_dates rows; applied {updated_rows}')

                        exception_date = datetime.strptime(row['date'], '%Y%m%d').date()
                        if exception_date < date_from or exception_date > date_to:
                            continue

                        if row['exception_type'] == '1':
                            day_bit = '1'
                        elif row['exception_type'] == '2':
                            day_bit = '0'
                        else:
                            raise ValueError(f"Invalid calendar_dates exception_type: {row['exception_type']}")

                        update: CalendarDateUpdate = {
                            'service_id': row['service_id'],
                            'start_date': date_from.strftime('%Y%m%d'),
                            'end_date': date_to.strftime('%Y%m%d'),
                            'day_bits': empty_day_bits,
                            'day_index': (exception_date - date_from).days,
                            'day_bit': day_bit,
                        }
                        if day_bit == '1':
                            cursor.execute('''
                                INSERT INTO calendar (service_id, start_date, end_date, day_bits)
                                VALUES (:service_id, :start_date, :end_date, :day_bits)
                                ON CONFLICT(service_id) DO NOTHING
                            ''', update)

                        cursor.execute('''
                            UPDATE calendar
                            SET day_bits = SUBSTR(day_bits, 1, :day_index)
                                || :day_bit || SUBSTR(day_bits, :day_index + 2)
                            WHERE service_id = :service_id
                        ''', update)
                        updated_rows += cursor.rowcount

        log_message(f'Applied {updated_rows} / {parsed_rows} calendar_dates rows to calendar day_bits')
