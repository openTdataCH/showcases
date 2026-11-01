import csv
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from .feed_info_filter import FeedInfoFilter
from .calendar_filter import CalendarFilter
from .calendar_dates_filter import CalendarDatesFilter
from .helpers.config_helpers import load_yaml_config
from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class GTFS_Filter:
    def __init__(
        self, source_gtfs_path: Path, destination_gtfs_path: Path,
        date_from: Optional[date], date_to: Optional[date],
    ):
        self._source_gtfs_path = source_gtfs_path
        self._destination_gtfs_path = destination_gtfs_path
        self._date_from = date_from
        self._date_to = date_to

    def filter(self) -> None:
        log_message('START GTFS folder filter')
        log_message(f'Source GTFS folder: {self._source_gtfs_path.resolve()}')
        log_message(f'Destination GTFS folder: {self._destination_gtfs_path.resolve()}')

        feed_info = self._read_feed_info()
        self._resolve_date_range(feed_info)
        log_message(f'From: {self._date_from.isoformat()}')
        log_message(f'To: {self._date_to.isoformat()}')
        log_message(f"feed_start_date: {feed_info.get('feed_start_date', '')}")
        log_message(f"feed_end_date: {feed_info.get('feed_end_date', '')}")
        db_path = self._destination_gtfs_path / 'temp_db' / 'filter.db'
        log_message(f'Intermediate database: {db_path.resolve()}')
        print()

        log_message('Step 1: Filter feed_info.txt')
        feed_info_filter = FeedInfoFilter()
        feed_info_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path,
            self._date_from, self._date_to,
        )
        print()

        log_message('Step 2: Populate calendar database with day_bits')
        filter_path = Path(__file__).resolve().parent
        config = load_yaml_config(filter_path / 'config.yml')
        schema_path = filter_path / config['temp_db_schema_path']
        db_engine = SQLiteDBEngine.init_read_write(db_path, schema_path)
        calendar_filter = CalendarFilter()
        calendar_filter.filter(
            self._source_gtfs_path, db_engine, self._date_from, self._date_to,
        )
        print()

        log_message('Step 3: Apply calendar_dates to calendar day_bits')
        calendar_dates_filter = CalendarDatesFilter()
        calendar_dates_filter.filter(
            self._source_gtfs_path, db_engine, self._date_from, self._date_to,
        )
        print()
        log_message('DONE GTFS folder filter')

    def _read_feed_info(self) -> Dict[str, str]:
        source_path = self._source_gtfs_path / 'feed_info.txt'
        if not source_path.is_file():
            return {}

        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            feed_info = next(reader, {})
        return feed_info

    def _resolve_date_range(self, feed_info: Dict[str, str]) -> None:
        if self._date_from is None or self._date_to is None:
            if self._date_from is None:
                start_date = feed_info.get('feed_start_date')
                if not start_date:
                    raise ValueError('Provide --from: source feed_start_date is missing')
                self._date_from = datetime.strptime(start_date, '%Y%m%d').date()

            if self._date_to is None:
                end_date = feed_info.get('feed_end_date')
                if not end_date:
                    raise ValueError('Provide --to: source feed_end_date is missing')
                self._date_to = datetime.strptime(end_date, '%Y%m%d').date()

        if self._date_from > self._date_to:
            raise ValueError('Resolved start date must be on or before the end date')
