import csv
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, TypedDict

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class CalendarRow(TypedDict):
    service_id: str
    start_date: str
    end_date: str
    day_bits: str


class CalendarFilter:
    def filter(
        self, source_gtfs_path: Path, db_engine: SQLiteDBEngine,
        date_from: date, date_to: date,
    ) -> None:
        source_path = source_gtfs_path / 'calendar.txt'
        log_message(f'Reading {source_path}')
        parsed_rows = 0
        writer = db_engine.create_csv_writer('calendar')
        try:
            with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
                reader = csv.DictReader(source_file)
                for row in reader:
                    day_bits = self._build_day_bits(row, date_from, date_to)
                    calendar_row: CalendarRow = {
                        'service_id': row['service_id'],
                        'start_date': date_from.strftime('%Y%m%d'),
                        'end_date': date_to.strftime('%Y%m%d'),
                        'day_bits': day_bits,
                    }
                    writer.prepare_row(calendar_row)
                    parsed_rows += 1
                    if parsed_rows % 50_000 == 0:
                        log_message(f'Parsed {parsed_rows} calendar rows; built day_bits')
        finally:
            writer.close()

        log_message(f'Loading {parsed_rows} calendar rows into the intermediate database')
        db_engine.drop_and_recreate_table('calendar')
        db_engine.load_csv_into_table('calendar', writer.csv_path)
        log_message(f'Stored {parsed_rows} calendar rows; keeping all rows until calendar_dates is loaded')

    def discard_inactive(self, db_engine: SQLiteDBEngine) -> None:
        with closing(db_engine.get_cursor()) as cursor:
            with cursor.connection:
                cursor.execute("DELETE FROM calendar WHERE INSTR(day_bits, '1') = 0")
                dropped_rows = cursor.rowcount
        log_message(f'Discarded {dropped_rows} calendar rows with no active days after applying calendar_dates')

    def _build_day_bits(self, row: Dict[str, str], date_from: date, date_to: date) -> str:
        days_no = (date_to - date_from).days + 1
        day_bits = ['0'] * days_no
        service_start = datetime.strptime(row['start_date'], '%Y%m%d').date()
        service_end = datetime.strptime(row['end_date'], '%Y%m%d').date()
        if service_start < date_from:
            service_start = date_from
        if service_end > date_to:
            service_end = date_to

        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_date = service_start
        while current_date <= service_end:
            weekday = weekdays[current_date.weekday()]
            if row[weekday] == '1':
                day_index = (current_date - date_from).days
                day_bits[day_index] = '1'
            if current_date == service_end:
                break
            current_date += timedelta(days=1)

        day_bits_value = ''.join(day_bits)
        return day_bits_value
