import csv
import datetime
from pathlib import Path
from typing import Optional

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
    feed_start = datetime.datetime.strptime(feed_row['feed_start_date'], '%Y%m%d')
    feed_end = datetime.datetime.strptime(feed_row['feed_end_date'], '%Y%m%d')
    if feed_start > feed_end:
        raise ValueError('feed_start_date must be on or before feed_end_date')

    start_date = feed_start
    if from_date is not None:
        start_date = from_date
    end_date = feed_end
    if to_date is not None:
        end_date = to_date

    if start_date < feed_start or start_date > feed_end:
        raise ValueError(
            f'--from {start_date:%Y%m%d} must be within feed_info range {feed_start:%Y%m%d} - {feed_end:%Y%m%d}'
        )
    if end_date < feed_start or end_date > feed_end:
        raise ValueError(
            f'--to {end_date:%Y%m%d} must be within feed_info range {feed_start:%Y%m%d} - {feed_end:%Y%m%d}'
        )
    if start_date > end_date:
        raise ValueError('--from must be on or before --to')

    calendar_data: CalendarData = {
        'start_date': start_date,
        'end_date': end_date,
        'days_no': (end_date - start_date).days + 1,
    }
    return calendar_data
