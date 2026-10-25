import os, sys
from pathlib import Path
from typing import List, Optional

from .helpers.log_helpers import log_message

from .import_context import ImportContext


class CSVImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_csv_tables(self, table_names: Optional[List[str]] = None):
        '''
        Batch TRUNCATE / INSERT csv rows from GTFS in db.
        '''
        if table_names is None:
            table_names = ['agency', 'feed_info', 'frequencies', 'routes', 'shapes', 'stop_times', 'stops', 'transfers', 'trips']

        log_message(f'START BATCH IMPORT')

        for table_name in table_names:
            log_message(f'... TABLE: {table_name}')
            if not table_name in self._context.db_engine.map_columns_metadata:
                print(f'ERROR - missing config for table {table_name}')
                sys.exit(1)

            self._context.db_engine.drop_and_recreate_table(table_name)

            gtfs_file_path = Path(f'{self._context.gtfs_folder_path}/{table_name}.txt')
            if not os.path.isfile(gtfs_file_path):
                is_skip_ok = False

                if table_name in ['feed_info', 'frequencies', 'shapes', 'transfers']:
                    is_skip_ok = True

                if table_name == 'calendar':
                    calendar_dates_path = f'{self._context.gtfs_folder_path}/calendar_dates.txt'
                    if os.path.isfile(calendar_dates_path):
                        log_message('... no calendar found, using calendar_dates instead')
                        is_skip_ok = True
                
                if is_skip_ok:
                    continue
                else:
                    print(f'ERROR = required table "{table_name}" not found {gtfs_file_path}')
                    sys.exit()
            # endif check if file exists

            self._context.db_engine.load_csv_into_table(table_name, gtfs_file_path)
            self._context.db_engine.add_table_indexes(table_name)
        # loop table names
        print()
        
        log_message(f'... DONE BATCH IMPORT')
        print('')
