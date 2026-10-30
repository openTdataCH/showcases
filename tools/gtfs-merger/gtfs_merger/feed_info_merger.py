import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class FeedInfoMerger:
    def prepare(self, first_gtfs_path: Path, second_gtfs_path: Path) -> Dict[str, str]:
        first_feed = self._read_feed_info(first_gtfs_path)
        second_feed = self._read_feed_info(second_gtfs_path)
        first_start = datetime.strptime(first_feed['feed_start_date'], '%Y%m%d').date()
        second_start = datetime.strptime(second_feed['feed_start_date'], '%Y%m%d').date()
        first_end = datetime.strptime(first_feed['feed_end_date'], '%Y%m%d').date()
        second_end = datetime.strptime(second_feed['feed_end_date'], '%Y%m%d').date()

        if first_start >= second_start:
            raise ValueError('GTFS1 feed_start_date must be earlier than GTFS2 feed_start_date')
        if first_end >= second_end:
            raise ValueError('GTFS1 feed_end_date must be earlier than GTFS2 feed_end_date')

        merged_feed = dict(first_feed)
        merged_feed['feed_start_date'] = first_feed['feed_start_date']
        merged_feed['feed_end_date'] = second_feed['feed_end_date']
        merged_feed['feed_version'] = f"db1:{first_feed['feed_version']}+gtfs2:{second_feed['feed_version']}"
        log_message(f"Merged feed dates: {merged_feed['feed_start_date']} - {merged_feed['feed_end_date']}")
        log_message(f"Merged feed version: {merged_feed['feed_version']}")
        return merged_feed

    def write(self, output_gtfs_path: Path, merged_feed: Dict[str, str], table_config: Dict[str, List[str]]):
        output_path = output_gtfs_path / 'feed_info.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        try:
            csv_writer.prepare_row(merged_feed)
        finally:
            csv_writer.close()
        log_message(f'Saved merged feed_info to {output_path}')

    def _read_feed_info(self, gtfs_path: Path) -> Dict[str, str]:
        feed_info_path = gtfs_path / 'feed_info.txt'
        log_message(f'Reading {feed_info_path}')
        with feed_info_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            feed_info = next(csv_reader)
        # with
        return feed_info
