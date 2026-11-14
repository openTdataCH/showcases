from contextlib import closing
from pathlib import Path
from typing import List, Literal, Optional, TypedDict, Union, cast

from gtfs_db_importer.helpers.gtfs_helpers import parse_gtfs_day

from .helpers.config_helpers import load_yaml_config
from .helpers.db_engine import SQLiteDBEngine
from .helpers.json_helpers import export_json_to_file
from .helpers.log_helpers import log_message


class AgencyRow(TypedDict):
    rowid: int
    agency_id: str
    agency_name: str
    agency_url: Optional[str]
    agency_timezone: Optional[str]
    agency_lang: Optional[str]
    agency_phone: Optional[str]


class RouteRow(TypedDict):
    rowid: int
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: Optional[str]
    route_desc: Optional[str]
    route_type: int
    day_bits: Optional[str]
    representative_trip_id: Optional[str]


class StopRow(TypedDict):
    rowid: int
    stop_id: str
    stop_name: str
    stop_lon: float
    stop_lat: float
    location_type: int
    parent_station: Optional[str]
    platform_code: Optional[str]
    original_stop_id: Optional[str]


class FTSRouteRow(TypedDict):
    rowid: int
    route_id: str
    trip_stop_ids: str


class CalendarRow(TypedDict):
    rowid: int
    service_id: str
    monday: Optional[int]
    tuesday: Optional[int]
    wednesday: Optional[int]
    thursday: Optional[int]
    friday: Optional[int]
    saturday: Optional[int]
    sunday: Optional[int]
    start_date: str
    end_date: str
    day_bits: Optional[str]


class StationRow(TypedDict):
    rowid: int
    station_id: str
    day_bits: Optional[str]


LookupRow = Union[AgencyRow, RouteRow, StopRow, FTSRouteRow, CalendarRow, StationRow]
LookupTableName = Literal['agency', 'routes', 'stops', 'fts_routes', 'calendar', 'stations']


class TableLookup(TypedDict):
    lookup_name: str
    data_source: str
    rows_no: int
    rows: List[LookupRow]


class GTFS_StaticLookupsController:
    def __init__(self, gtfs_db_path: Path):
        self._gtfs_db_path = gtfs_db_path
        module_path = Path(__file__).resolve().parent
        config_path = module_path / 'config.yml'
        self._app_config = load_yaml_config(config_path, module_path.parent)
        gtfs_day = parse_gtfs_day(gtfs_db_path.name)
        self._gtfs_day = gtfs_day.strftime('%Y-%m-%d')

    def create_table_lookups(self):
        db_engine = SQLiteDBEngine(db_path=self._gtfs_db_path)
        self._create_table_lookup(db_engine, 'agency')
        self._create_table_lookup(db_engine, 'routes')
        self._create_table_lookup(db_engine, 'stops')
        self._create_table_lookup(db_engine, 'fts_routes')
        self._create_table_lookup(db_engine, 'calendar')
        self._create_table_lookup(db_engine, 'stations')

    def _create_table_lookup(self, db_engine: SQLiteDBEngine, table_name: LookupTableName):
        log_message(f'Creating {table_name} lookup')
        path_template = self._app_config['gtfs_static_path_templates']['gtfs_table']
        output_path_s = path_template.replace('${GTFS_DAY}', self._gtfs_day)
        output_path_s = output_path_s.replace('${TABLE_NAME}', table_name)
        output_path = Path(output_path_s)

        rows: List[LookupRow] = []
        with closing(db_engine.get_cursor()) as cursor:
            cursor.execute(f'SELECT ROWID, * FROM {table_name}')
            for database_row in cursor:
                lookup_row = cast(LookupRow, dict(database_row))
                rows.append(lookup_row)

        lookup: TableLookup = {
            'lookup_name': table_name,
            'data_source': str(self._gtfs_db_path),
            'rows_no': len(rows),
            'rows': rows,
        }
        export_json_to_file(lookup, output_path, pretty_print=True)

        log_message(f'Created {table_name} lookup with {len(rows)} rows: {output_path}')
