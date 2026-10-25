from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .helpers.db_engine import SQLiteDBEngine
from .import_types import CalendarData


@dataclass
class ImportContext:
    db_engine: SQLiteDBEngine
    map_sql_queries: Dict[str, str]
    gtfs_folder_path: Path
    bo_realtime_csv_path: Path
    calendar_data: CalendarData
