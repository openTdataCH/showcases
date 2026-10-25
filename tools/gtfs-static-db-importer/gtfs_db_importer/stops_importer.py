from typing import cast

from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file

from .import_types import StopMissingParentRow
from .import_context import ImportContext


class StopsImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def check_stops_parent_depth(self):
        log_message('START check stops parent depth')

        sql_path = self._context.map_sql_queries['select_stops_exceeding_parent_depth']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._context.db_engine.get_cursor()
        db_cursor.execute(sql)
        invalid_stop = db_cursor.fetchone()
        db_cursor.close()

        if invalid_stop is not None:
            stop_id = invalid_stop['stop_id']
            parent_stop_id = invalid_stop['parent_stop_id']
            grandparent_stop_id = invalid_stop['grandparent_stop_id']
            raise ValueError(
                f'Stop hierarchy exceeds one parent level: '
                f'{stop_id} -> {parent_stop_id} -> {grandparent_stop_id}'
            )

        log_message('DONE check stops parent depth')
        print('')

    def check_stops_missing_parents(self):
        log_message('START check stops missing parents')

        sql_path = self._context.map_sql_queries['select_stops_missing_parents']
        sql = load_sql_from_file(sql_path)
        db_cursor = self._context.db_engine.get_cursor()
        db_cursor.execute(sql)
        db_row = db_cursor.fetchone()
        db_cursor.close()

        if db_row is not None:
            invalid_stop = cast(StopMissingParentRow, db_row)
            stop_id = invalid_stop['stop_id']
            parent_station = invalid_stop['parent_station']
            raise ValueError(f'Stop {stop_id} references missing parent stop {parent_station}')

        log_message('DONE check stops missing parents')
        print('')
