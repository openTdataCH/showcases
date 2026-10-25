from pathlib import Path

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .import_context import ImportContext


class RoutesImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def update_routes(self):
        '''
        - DROP routes
        - batch INSERT routes with new columns (day_bits)
        '''
        log_message('START update routes')

        map_db_routes = self._context.db_engine.query_table_map_by_field('routes', 'route_id')
        
        sql_path = self._context.map_sql_queries['select_route_trips_calendar_day_bits']
        sql = load_sql_from_file(sql_path)
        
        log_message(f"... running select_route_trips_calendar_day_bits SQL")

        db_cursor = self._context.db_engine.get_cursor()
        row_id = 1
        for db_row in db_cursor.execute(sql):
            if row_id % 1000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} rows')
                
            trips_day_bits_s: str = db_row['trips_day_bits']
            if trips_day_bits_s is None:
                print(db_row)
                raise ValueError('calendar.day_bits is not computed')
            trips_day_bits = trips_day_bits_s.split(',')
            
            route_day_bits = ['0'] * len(trips_day_bits[0])
            for trip_day_bits in trips_day_bits:
                for idx, day_bit in enumerate(trip_day_bits):
                    if day_bit == '1':
                        route_day_bits[idx] = '1'
                        
            route_day_bits_s = ''.join(route_day_bits)
            
            route_id = db_row['route_id']
            map_db_routes[route_id]['day_bits'] = route_day_bits_s

            row_id += 1
        # loop SQL

        log_message(f"... INSERT new routes ...")

        db_temp_path = self._context.db_engine.get_db_tmp_path()

        table_name = 'routes'
        table_csv_file_path = Path(f'{db_temp_path}/new_routes.csv')
        table_column_names = self._context.db_engine.map_columns_metadata[table_name]['names']
        new_routes_table_csv_updater = CSV_Updater(table_csv_file_path, table_column_names)
        
        for route_id, db_route in map_db_routes.items():
            new_routes_table_csv_updater.prepare_row(db_route)
        
        new_routes_table_csv_updater.close()
        
        self._context.db_engine.drop_and_recreate_table(table_name)
        self._context.db_engine.load_csv_into_table(table_name, table_csv_file_path)
        self._context.db_engine.add_table_indexes(table_name)

        log_message(f"... DONE")
        print('')

    def update_routes_representative_trip(self):
        '''
        - UPDATE routes SET representative_trip_id
        '''
        log_message(f"START UPDATE routes-trip (representative)")
        
        sql_path = self._context.map_sql_queries['update_routes_representative_trip']
        sql = load_sql_from_file(sql_path)
        self._context.db_engine.run_sql_script(sql)
        
        log_message(f"... DONE UPDATE routes-trip (representative)")
        print('')

    def create_fts_routes(self):
        '''
        - CREATE fts_routes from SQL
        '''
        log_message(f"START CREATE FTS routes ...")
        
        sql_path = self._context.map_sql_queries['create_fts_routes']
        sql = load_sql_from_file(sql_path)
        self._context.db_engine.run_sql_script(sql)
        
        log_message(f"... DONE FTS routes ...")
        print('')
