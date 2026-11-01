import csv
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class CalendarDateRow(TypedDict):
    service_id: str
    date: str
    exception_type: str


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
