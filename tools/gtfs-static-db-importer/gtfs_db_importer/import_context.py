from pathlib import Path
from typing import Dict, Set

from .helpers.db_engine import SQLiteDBEngine
from .import_types import CalendarData


class ImportContext:
    def __init__(self, db_engine: SQLiteDBEngine, map_sql_queries: Dict[str, str],
                 gtfs_folder_path: Path, bo_realtime_csv_path: Path, calendar_data: CalendarData):
        self.db_engine = db_engine
        self.map_sql_queries = map_sql_queries
        self.gtfs_folder_path = gtfs_folder_path
        self.bo_realtime_csv_path = bo_realtime_csv_path
        self.calendar_data = calendar_data
        self.active_service_ids: Set[str] = set()
        self.active_trip_ids: Set[str] = set()
