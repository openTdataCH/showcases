import csv
import datetime
from contextlib import closing
from typing import cast

from .helpers.log_helpers import log_message
from .import_context import ImportContext
from .import_types import MetadataImportRow, MetadataTableRow, TableRowCountRow


class ImportMetadata:
    def __init__(self, context: ImportContext):
        self._context = context

    def start_import(self, import_start: datetime.datetime):
        log_message('Recording import start metadata')
        feed_info_path = self._context.gtfs_folder_path / 'feed_info.txt'
        with feed_info_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            feed_info_row = next(csv.DictReader(csv_file))
        # with

        metadata_row: MetadataImportRow = {
            'id': 1,
            'source_folder': str(self._context.gtfs_folder_path.resolve()),
            'source_feed_start_date': feed_info_row['feed_start_date'],
            'source_feed_end_date': feed_info_row['feed_end_date'],
            'import_start': import_start.isoformat(),
            'import_end': None,
        }
        self._context.db_engine.drop_and_recreate_table('metadata_import')
        sql = '''
            INSERT INTO metadata_import (
                id, source_folder, source_feed_start_date, source_feed_end_date, import_start, import_end
            ) VALUES (
                :id, :source_folder, :source_feed_start_date, :source_feed_end_date, :import_start, :import_end
            )
        '''
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            db_cursor.execute(sql, metadata_row)
            db_cursor.connection.commit()
        # with

    def write_table_stats(self):
        log_message('START write metadata_tables')
        table_names = [
            'agency', 'calendar', 'calendar_dates', 'feed_info', 'frequencies',
            'routes', 'shapes', 'stop_times', 'stops', 'transfers', 'trips',
        ]
        self._context.db_engine.drop_and_recreate_table('metadata_tables')
        insert_sql = '''
            INSERT INTO metadata_tables (table_name, source_file_present, source_rows, retained_rows)
            VALUES (:table_name, :source_file_present, :source_rows, :retained_rows)
        '''
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            for table_name in table_names:
                source_path = self._context.gtfs_folder_path / f'{table_name}.txt'
                source_file_present = 0
                if source_path.is_file():
                    source_file_present = 1

                # Names come from the fixed list above; count final rows after all generated data.
                db_cursor.execute(f'SELECT COUNT(*) AS row_count FROM {table_name}')
                count_row = cast(TableRowCountRow, db_cursor.fetchone())
                metadata_row: MetadataTableRow = {
                    'table_name': table_name,
                    'source_file_present': source_file_present,
                    'source_rows': self._context.source_table_rows.get(table_name, 0),
                    'retained_rows': count_row['row_count'],
                }
                db_cursor.execute(insert_sql, metadata_row)
                formatted_source_rows = f"{metadata_row['source_rows']:,}".replace(',', "'")
                formatted_retained_rows = f"{metadata_row['retained_rows']:,}".replace(',', "'")
                log_message(f'{table_name}: source {formatted_source_rows}; retained {formatted_retained_rows}')
            # loop source tables
            db_cursor.connection.commit()
        # with
        log_message('DONE write metadata_tables')
        print()

    def finish_import(self):
        import_end = datetime.datetime.now(datetime.timezone.utc)
        sql = 'UPDATE metadata_import SET import_end = :import_end WHERE id = 1'
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            db_cursor.execute(sql, {'import_end': import_end.isoformat()})
            db_cursor.connection.commit()
        # with
        log_message('Recorded import end metadata')
