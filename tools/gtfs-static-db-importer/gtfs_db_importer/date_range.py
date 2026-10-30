import csv
import datetime
from pathlib import Path
from typing import Optional

from .helpers.log_helpers import log_message
from .import_types import CalendarData


def resolve_import_date_range(gtfs_folder_path: Path, from_date: Optional[datetime.datetime],
                              to_date: Optional[datetime.datetime]) -> CalendarData:
    feed_info_path = gtfs_folder_path / 'feed_info.txt'
    with feed_info_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
        feed_rows = list(csv.DictReader(csv_file))
    # with
    if len(feed_rows) != 1:
        raise ValueError(f'Expected exactly one feed_info row in {feed_info_path}, found {len(feed_rows)}')

    feed_row = feed_rows[0]
    feed_start = _parse_optional_date(feed_row.get('feed_start_date'))
    feed_end = _parse_optional_date(feed_row.get('feed_end_date'))
    if feed_start is None or feed_end is None:
        calendar_start, calendar_end = _read_calendar_date_range(gtfs_folder_path)
        if feed_start is None:
            feed_start = calendar_start
        if feed_end is None:
            feed_end = calendar_end
        log_message('Missing feed_info dates: deriving bounds from calendar and calendar_dates')
    if feed_start is None or feed_end is None:
        raise ValueError('Cannot determine feed date range from feed_info, calendar, or calendar_dates')
    if feed_start > feed_end:
        raise ValueError('feed_start_date must be on or before feed_end_date')
    feed_range_days = (feed_end - feed_start).days
    if feed_range_days > 500:
        raise ValueError(
            f'Feed date range exceeds 500 days: {feed_start:%Y-%m-%d} - {feed_end:%Y-%m-%d} '
            f'({feed_range_days} days)'
        )

    start_date = feed_start
    if from_date is not None:
        start_date = from_date
    end_date = feed_end
    if to_date is not None:
        end_date = to_date

    if start_date < feed_start or start_date > feed_end:
        raise ValueError(
            f'--from {start_date:%Y%m%d} must be within feed range {feed_start:%Y%m%d} - {feed_end:%Y%m%d}'
        )
    if end_date < feed_start or end_date > feed_end:
        raise ValueError(
            f'--to {end_date:%Y%m%d} must be within feed range {feed_start:%Y%m%d} - {feed_end:%Y%m%d}'
        )
    if start_date > end_date:
        raise ValueError('--from must be on or before --to')

    calendar_data: CalendarData = {
        'start_date': start_date,
        'end_date': end_date,
        'days_no': (end_date - start_date).days + 1,
    }
    return calendar_data


def _parse_optional_date(value: Optional[str]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    value = value.strip()
    if value == '':
        return None
    parsed_date = datetime.datetime.strptime(value, '%Y%m%d')
    return parsed_date


def _read_calendar_date_range(gtfs_folder_path: Path):
    earliest_date = None
    latest_date = None
    for table_name in ['calendar', 'calendar_dates']:
        csv_path = gtfs_folder_path / f'{table_name}.txt'
        if csv_path.is_file():
            with csv_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for row in csv_reader:
                    if table_name == 'calendar':
                        row_start = _parse_optional_date(row.get('start_date'))
                        row_end = _parse_optional_date(row.get('end_date'))
                    else:
                        row_start = _parse_optional_date(row.get('date'))
                        row_end = row_start
                    if row_start is not None:
                        if earliest_date is None or row_start < earliest_date:
                            earliest_date = row_start
                    if row_end is not None:
                        if latest_date is None or row_end > latest_date:
                            latest_date = row_end
                # loop calendar CSV rows
            # with
        # if file exists
    # loop calendar files
    date_range = (earliest_date, latest_date)
    return date_range
