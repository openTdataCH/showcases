import csv
import datetime
from contextlib import closing

from .helpers.log_helpers import log_message
from .import_context import ImportContext
from .import_types import MetadataImportRow


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

    def finish_import(self):
        import_end = datetime.datetime.now(datetime.timezone.utc)
        sql = 'UPDATE metadata_import SET import_end = :import_end WHERE id = 1'
        with closing(self._context.db_engine.get_cursor()) as db_cursor:
            db_cursor.execute(sql, {'import_end': import_end.isoformat()})
            db_cursor.connection.commit()
        # with
        log_message('Recorded import end metadata')
