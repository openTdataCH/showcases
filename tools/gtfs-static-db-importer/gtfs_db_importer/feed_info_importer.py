import csv

from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .import_context import ImportContext


class FeedInfoImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_feed_info(self):
        log_message('START import feed_info')
        feed_info_path = self._context.gtfs_folder_path / 'feed_info.txt'
        log_message(f'Reading {feed_info_path}')
        total_rows = compute_file_rows_no(feed_info_path) - 1
        if total_rows < 0:
            total_rows = 0
        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Found {formatted_total_rows} feed_info rows')

        feed_info_writer = self._context.db_engine.create_csv_writer('feed_info')
        row_count = 0
        try:
            with feed_info_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for feed_info_row in csv_reader:
                    if row_count % 10_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        log_message(
                            f'... parsed {formatted_row_count} / {formatted_total_rows} feed_info rows; '
                            f'kept {formatted_row_count}'
                        )

                    feed_info_writer.prepare_row(feed_info_row)
                    row_count += 1
                # loop feed_info.txt CSV rows
            # with
        finally:
            feed_info_writer.close()

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        log_message(
            f'Parsed {formatted_row_count} / {formatted_total_rows} feed_info rows; '
            f'kept {formatted_row_count}'
        )
        self._context.db_engine.drop_and_recreate_table('feed_info')
        self._context.db_engine.load_csv_into_table('feed_info', feed_info_writer.csv_path)
        self._context.db_engine.add_table_indexes('feed_info')
        log_message(f'Imported {formatted_row_count} / {formatted_total_rows} feed_info rows')
        log_message('DONE import feed_info')
        print()
