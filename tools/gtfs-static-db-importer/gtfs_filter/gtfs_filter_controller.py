import os, sys

from pathlib import Path
from typing import Any, List

from datetime import datetime
import re

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message

class GTFS_FilterController:
    _app_config: Any
    _gtfs_db_engine: SQLiteDBEngine
    _where_filters: List[str]
    _gtfs_output_path: Path

    def __init__(self, app_config: Any, db_path: Path, gtfs_output_path: Path):
        log_message(f'GTFS Filter: {db_path.name}')

        self._app_config = app_config

        db_schema_path = app_config['gtfs_filter']['gtfs_db_schema_path']
        self._gtfs_db_engine = SQLiteDBEngine.init_read_write(db_path, db_schema_path=db_schema_path)
        self._where_filters = []
        
        if not os.path.isdir(gtfs_output_path):
            os.makedirs(gtfs_output_path)
        
        self._gtfs_output_path = gtfs_output_path

    def reset_filters(self):
        self._reset_filters()

    def set_filter_by_bbox(self, bbox_s: str):
        self._set_filter_by_bbox(bbox_s)

    def set_filter_by_agencies(self, agency_ids: List[str]):
        self._set_filter_by_agency_ids(agency_ids)

    def set_filter_by_day(self, day_s: str):
        self._set_filter_by_day(day_s)

    def filter(self):
        self._filter()

    # private below
    def _reset_filters(self):
        self._where_filters = []

        table_name = 'link_filter_trips'

        log_message(f'SQL: drop/create {table_name}')
        self._gtfs_db_engine.drop_and_recreate_table(table_name)
        log_message(f'... done')
        print()

    def _set_filter_by_bbox(self, bbox_s: str):
        bbox_coords = [float(x) for x in bbox_s.split(',')]

        if len(bbox_coords) != 4:
            raise ValueError('ERROR - expected 4 coords from bbox param: {bbox_s}')
        
        min_lng, min_lat, max_lng, max_lat = bbox_coords
        self._where_filters.append(f'stop_lon > {min_lng}')
        self._where_filters.append(f'stop_lat > {min_lat}')
        self._where_filters.append(f'stop_lon < {max_lng}')
        self._where_filters.append(f'stop_lat < {max_lat}')

    def _set_filter_by_agency_ids(self, agency_ids: List[str]):
        filter_in_s = ', '.join([f"'{agency_id}'" for agency_id in agency_ids])
        self._where_filters.append(f'routes.agency_id IN ({filter_in_s})')

    def _set_filter_by_day(self, day_s: str):
        day_matches = re.match(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$", day_s)
        if day_matches is None:
            raise ValueError(f'Expected day YYYY-MM-DD for from_day, got {day_s}')
        
        day_date = datetime.strptime(day_s, '%Y-%m-%d')

        day0_rows = self._gtfs_db_engine.query('SELECT start_date FROM calendar LIMIT 1')
        if len(day0_rows) == 0:
            raise ValueError(f'No calendar SQL rows found?')
        day0_s = day0_rows[0]['start_date']
        day0_date = datetime.strptime(day0_s, '%Y%m%d')
        
        days_diff = (day_date - day0_date).days

        if days_diff < 0:
            raise ValueError(f'Given date {day_s} is behind start date: {day0_s}')
        
        # SUBSTR(col_name, index, count) - index is 1-based, therefore = days_diff + 1
        self._where_filters.append(f"trips.service_id IN (SELECT calendar.service_id FROM calendar WHERE SUBSTR(day_bits, {days_diff} + 1, 1) = '1')")
    
    def _populate_link_filter(self):
        if len(self._where_filters) == 0:
            raise ValueError('ERROR - no filters defined')

        sql_path = Path(self._app_config['gtfs_filter']['sql']['populate-link_filter'])
        sql = sql_path.read_text(encoding='utf-8')

        sql_filters: List[str] = []
        for where_filter in self._where_filters:
            sql_filters.append(f'AND {where_filter}')
        sql_filters_s = '\n'.join(sql_filters)

        sql = sql.replace('[WHERE_FILTERS]', sql_filters_s)

        table_name = 'link_filter_trips'
        log_message(f'SQL: INSERT into {table_name}')
        print()
        print(sql)
        print()
        log_message(f'... start insert')
        self._gtfs_db_engine.run_sql(sql)
        trips_no = self._gtfs_db_engine.count_rows_table(table_name)
        log_message(f'... done, {trips_no} trips inserted')
        print()

    def _export_table(self, csv_path: Path, table_name: str, column_names: List[str]):
        sql_path_s: str = self._app_config['gtfs_filter']['sql']['select_table_template']
        sql_path_s = sql_path_s.replace('[TABLE_NAME]', table_name)
        sql_path = Path(sql_path_s)
        sql = sql_path.read_text(encoding='utf-8')

        self._gtfs_db_engine.export_sql_to_csv(sql, csv_path, column_names=column_names)

    def _export_csv(self):
        gtfs_export_config_path = Path(self._app_config['gtfs_filter']['gtfs_export_profile'])
        gtfs_export = SQLiteDBEngine.init_memory(db_schema_path=gtfs_export_config_path)

        log_message(f'START export CSV tables to {self._gtfs_output_path}')
        table_names = ['agency', 'stops', 'routes', 'calendar', 'calendar_dates', 'stop_times', 'trips']
        for table_name in table_names:
            log_message(f'... export {table_name}')
            csv_path = Path(f'{self._gtfs_output_path}/{table_name}.txt')
            column_names = gtfs_export.map_columns_metadata[table_name]['names']
            self._export_table(csv_path, table_name, column_names)
        # loop tables

        log_message('... DONE CSV export')
        
    def _filter(self):
        self._populate_link_filter()
        self._export_csv()
        