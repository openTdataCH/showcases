from contextlib import closing
from typing import Set, TypedDict, cast

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message


class ServiceIdRow(TypedDict):
    service_id: str


class RouteIdRow(TypedDict):
    route_id: str


class FilterContext:
    def __init__(self):
        self.active_service_ids: Set[str] = set()

    def load_active_service_ids(self, db_engine: SQLiteDBEngine) -> None:
        self.active_service_ids.clear()
        with closing(db_engine.get_cursor()) as cursor:
            cursor.execute('SELECT service_id FROM calendar')
            for db_row in cursor:
                service_row = cast(ServiceIdRow, db_row)
                self.active_service_ids.add(service_row['service_id'])
        log_message(f'Loaded {len(self.active_service_ids)} active service IDs into context')
