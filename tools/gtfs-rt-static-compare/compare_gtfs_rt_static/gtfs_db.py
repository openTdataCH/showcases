import os, sys

from pathlib import Path

from typing import Any, Dict, TypedDict
from datetime import date

from .helpers.json_helpers import load_json_from_file, export_json_to_file
from .helpers.db_engine import SQLiteDBEngine
from .helpers.gtfs_helpers import parse_gtfs_day
from .helpers import json_helpers

from .models.gtfs_static_db import Route as RouteDB

class TripRow(TypedDict):
    trip_id: str
    route_id: str
    dep_mins: int
    arr_mins: int

class DayTripData(TypedDict):
    map_trips: Dict[str, TripRow]
    map_route_agency: Dict[str, str]
    map_agency_ids: Dict[str, bool]

def format_day(day: date) -> str:
    day_f = day.strftime('%Y-%m-%d')
    return day_f

class GTFS_DB:
    _db: SQLiteDBEngine
    map_routes: Dict[str, RouteDB]

    _gtfs_static_query_cache_path: Path
    _map_sql_paths: Dict[str, Path]

    start_day: date
    gtfs_day: date
    
    def __init__(self, db_path: Path, map_resource_paths: Dict[str, Any] = {}):
        self._db = SQLiteDBEngine(db_path)
        
        self.map_routes = {}
        self.start_day = self._compute_start_date()
        self.gtfs_day = parse_gtfs_day(db_path.name)

        gtfs_static_query_cache_path_s = map_resource_paths.get('gtfs_static_query_cache_path', None)
        if gtfs_static_query_cache_path_s is None:
            raise ValueError(f'expected gtfs_static_query_cache_path path is not defined in config')
        self._gtfs_static_query_cache_path = Path(gtfs_static_query_cache_path_s)

        self._map_sql_paths = {}
        map_sql_paths = map_resource_paths.get('sql', {})
        for key, path_s in map_sql_paths.items():
            self._map_sql_paths[key] = Path(path_s)

    def _compute_start_date(self):
        sql = 'SELECT start_date FROM calendar LIMIT 1'
        rows = self._db.query(sql)
        start_date_s = rows[0]['start_date']
        start_date = parse_gtfs_day(start_date_s)

        return start_date
            
    def init_lookups(self):
        gtfs_routes_db = self._load_gtfs_table('routes', map_by_field='route_id')
        self.map_routes = {}
        for route_id, route_db_json in gtfs_routes_db.items():
            route_db_json_cleaned = {k: v for k, v in route_db_json.items() if k in RouteDB.__annotations__}
            self.map_routes[route_id] = RouteDB(**route_db_json_cleaned)        
        
    def _load_gtfs_table(self, table_name: str, map_by_field: str):
        res_cache_path = None
        if self._gtfs_static_query_cache_path is not None:
            db_day_f = format_day(self.gtfs_day)
            res_cache_path_s = f'{self._gtfs_static_query_cache_path}/db_{db_day_f}__table_{table_name}.json'
            res_cache_path = Path(res_cache_path_s)
        
            if os.path.isfile(res_cache_path):
                res_json = load_json_from_file(res_cache_path)
                return res_json
        # check cache
        
        sql = None
        if table_name == 'trips':
            sql = 'SELECT trip_id, route_id, service_id FROM trips'
        if sql is None:
            sql = f'SELECT * FROM {table_name}'
            
        res_json = self._db.query_map_by_field(sql, map_by_field=map_by_field)
        
        if res_cache_path is not None:
            export_json_to_file(res_json, res_cache_path, pretty_print=True)
        
        return res_json

    def compute_day_data(self, day: date) -> DayTripData:
        db_day_f = format_day(self.gtfs_day)
        gtfs_day_f = format_day(day)
        data_cache_filename = f'trip_day_data__v2__db_{db_day_f}__day_{gtfs_day_f}.json'
        data_cache_path = Path(f'{self._gtfs_static_query_cache_path}/{data_cache_filename}')
        if data_cache_path.exists():
            data_json = json_helpers.load_json_from_file(data_cache_path)
            return data_json

        day_idx = (day - self.start_day).days

        sql = self._map_sql_paths['select_active_trips_agency_rt_mode_light'].read_text()
        sql = sql.replace('[DAY_IDX]', f'{day_idx}')

        day_trip_data: DayTripData = {
            'map_trips': {},
            'map_route_agency': {},
            'map_agency_ids': {},
        }

        cursor = self._db.get_cursor()
        cursor.execute(sql)
        for db_row in cursor:
            trip_id = db_row['trip_id']
            route_id = db_row['route_id']
            agency_id = db_row['agency_id']
            
            trip_row: TripRow = {
                'trip_id': trip_id,
                'route_id': route_id,
                'dep_mins': db_row['departure_day_minutes'],
                'arr_mins': db_row['arrival_day_minutes'],
            }

            day_trip_data['map_trips'][trip_id] = trip_row
            day_trip_data['map_route_agency'][route_id] = agency_id
            day_trip_data['map_agency_ids'][agency_id] = True
        # loop db_rows
        cursor.close()

        json_helpers.export_json_to_file(day_trip_data, data_cache_path, pretty_print=True)

        return day_trip_data
