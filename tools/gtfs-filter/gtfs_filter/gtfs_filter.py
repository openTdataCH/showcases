import csv
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from .feed_info_filter import FeedInfoFilter
from .calendar_filter import CalendarFilter
from .calendar_dates_filter import CalendarDatesFilter
from .calendar_exporter import CalendarExporter
from .filter_context import FilterContext
from .trips_filter import TripsFilter
from .routes_filter import RoutesFilter
from .agency_filter import AgencyFilter
from .frequencies_filter import FrequenciesFilter
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
        self._context = FilterContext()

    def filter(self) -> None:
        log_message('START GTFS folder filter')
        log_message(f'Source GTFS folder: {self._source_gtfs_path.resolve()}')
        log_message(f'Destination GTFS folder: {self._destination_gtfs_path.resolve()}')

        feed_info = self._read_feed_info()
        date_from, date_to = self._resolve_date_range(feed_info)
        log_message(f'From: {date_from.isoformat()}')
        log_message(f'To: {date_to.isoformat()}')
        log_message(f"feed_start_date: {feed_info.get('feed_start_date', '')}")
        log_message(f"feed_end_date: {feed_info.get('feed_end_date', '')}")
        db_path = self._destination_gtfs_path / 'temp_db' / 'filter.db'
        log_message(f'Intermediate database: {db_path.resolve()}')
        print()

        log_message('Step 1: Filter feed_info.txt')
        feed_info_filter = FeedInfoFilter()
        feed_info_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path,
            date_from, date_to,
        )
        print()

        filter_path = Path(__file__).resolve().parent
        config = load_yaml_config(filter_path / 'config.yml')
        schema_path = filter_path / config['temp_db_schema_path']
        db_engine = SQLiteDBEngine.init_read_write(db_path, schema_path)

        log_message('Step 2: Populate calendar database with day_bits')
        calendar_filter = CalendarFilter()
        calendar_filter.filter(
            self._source_gtfs_path, db_engine, date_from, date_to,
        )
        print()

        log_message('Step 3: Populate calendar_dates database with exceptions within the filter range')
        calendar_dates_filter = CalendarDatesFilter()
        calendar_dates_filter.filter(
            self._source_gtfs_path, db_engine, date_from, date_to,
        )
        print()

        log_message('Step 4: Apply grouped calendar_dates and reload calendar from CSV')
        calendar_dates_filter.apply_to_calendar(db_engine)
        print()

        log_message('Step 5: Discard calendar rows with no active days')
        calendar_filter.discard_inactive(db_engine)
        print()

        log_message('Step 6: Load active service IDs into context')
        self._context.load_active_service_ids(db_engine)
        print()

        log_message('Step 7: Export calendar and calendar_dates for active service IDs')
        calendar_exporter = CalendarExporter()
        calendar_exporter.export(
            self._source_gtfs_path, self._destination_gtfs_path, self._context,
        )
        print()

        log_message('Step 8: Filter trips by active service IDs and store retained trip IDs')
        trips_filter = TripsFilter()
        trips_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path, db_engine, self._context,
        )
        print()

        log_message('Step 9: Load active route IDs from trips into context')
        self._context.load_active_route_ids(db_engine)
        print()

        log_message('Step 10: Filter routes by active route IDs')
        routes_filter = RoutesFilter()
        routes_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path, self._context,
        )
        print()

        log_message('Step 11: Filter agencies referenced by retained routes')
        agency_filter = AgencyFilter()
        agency_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path, self._context,
        )
        print()

        log_message('Step 12: Load active trip IDs into context')
        self._context.load_active_trip_ids(db_engine)
        print()

        log_message('Step 13: Filter frequencies by active trip IDs, if present')
        frequencies_filter = FrequenciesFilter()
        frequencies_filter.filter(
            self._source_gtfs_path, self._destination_gtfs_path, self._context,
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

    def _resolve_date_range(self, feed_info: Dict[str, str]) -> tuple[date, date]:
        date_from = self._date_from
        date_to = self._date_to
        if date_from is None:
            start_date = feed_info.get('feed_start_date')
            if not start_date:
                raise ValueError('Provide --from: source feed_start_date is missing')
            date_from = datetime.strptime(start_date, '%Y%m%d').date()

        if date_to is None:
            end_date = feed_info.get('feed_end_date')
            if not end_date:
                raise ValueError('Provide --to: source feed_end_date is missing')
            date_to = datetime.strptime(end_date, '%Y%m%d').date()

        if date_from > date_to:
            raise ValueError('Resolved start date must be on or before the end date')

        resolved_date_range = (date_from, date_to)
        return resolved_date_range
