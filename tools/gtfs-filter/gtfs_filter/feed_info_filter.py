import csv
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class FeedInfoFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path,
        date_from: Optional[date], date_to: Optional[date],
    ) -> None:
        source_path = source_gtfs_path / 'feed_info.txt'
        if not source_path.is_file():
            log_message(f'Skipping feed_info.txt: source file not found at {source_path}')
            return

        log_message(f'Reading {source_path}')
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            rows = list(reader)

        for row in rows:
            self._filter_dates(row, date_from, date_to)

        log_message(f'Filtered feed dates for {len(rows)} rows; keeping input columns and other values')
        destination_gtfs_path.mkdir(exist_ok=True)
        destination_path = destination_gtfs_path / 'feed_info.txt'
        log_message(f'Writing {destination_path}')
        column_names = list(fieldnames)
        csv_updater = CSV_Updater(destination_path, column_names)
        try:
            for row in rows:
                csv_updater.prepare_row(row)
        finally:
            csv_updater.close()
        log_message(f'Saved filtered feed_info to {destination_path}')

    def _filter_dates(
        self, row: Dict[str, str], date_from: Optional[date], date_to: Optional[date],
    ) -> None:
        start_date = None
        end_date = None
        if row.get('feed_start_date'):
            start_date = datetime.strptime(row['feed_start_date'], '%Y%m%d').date()
        if row.get('feed_end_date'):
            end_date = datetime.strptime(row['feed_end_date'], '%Y%m%d').date()

        if date_from is not None:
            if start_date is None:
                start_date = date_from
            elif date_from > start_date:
                start_date = date_from

        if date_to is not None:
            if end_date is None:
                end_date = date_to
            elif date_to < end_date:
                end_date = date_to

        if start_date is not None and end_date is not None:
            if start_date > end_date:
                raise ValueError('Requested date range does not overlap the feed_info date range')

        if date_from is not None and 'feed_start_date' in row:
            row['feed_start_date'] = start_date.strftime('%Y%m%d')
        if date_to is not None and 'feed_end_date' in row:
            row['feed_end_date'] = end_date.strftime('%Y%m%d')
