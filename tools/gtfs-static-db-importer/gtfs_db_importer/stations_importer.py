from pathlib import Path
from typing import cast

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .import_types import StationCountRow, StationIdRow, StationTripsDayBitsRow
from .import_context import ImportContext


class StationsImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def populate_stations(self):
        log_message('START populate stations')

        sql_path = self._context.map_sql_queries['select_stations']
        sql = load_sql_from_file(sql_path)

        days_no = self._context.calendar_data['days_no']

        table_name = 'stations'
        table_csv_writer = self._context.db_engine.create_csv_writer(table_name)
        empty_day_bits = '0' * days_no

        count_rows = self._context.db_engine.query(
            'SELECT COUNT(*) AS stations_count FROM stops WHERE parent_station IS NULL'
        )
        count_row = cast(StationCountRow, count_rows[0])
        formatted_total_rows = f"{count_row['stations_count']:,}".replace(',', "'")
        db_cursor = self._context.db_engine.get_cursor()
        row_count = 0
        for db_row in db_cursor.execute(sql):
            if row_count % 10_000 == 0:
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'... populated {formatted_row_count} / {formatted_total_rows} stations')

            station_row = cast(StationIdRow, db_row)
            row_dict = {
                'station_id': station_row['station_id'],
                'day_bits': empty_day_bits,
            }
            table_csv_writer.prepare_row(row_dict)
            row_count += 1
        # loop stations

        db_cursor.close()
        table_csv_writer.close()

        self._context.db_engine.drop_and_recreate_table(table_name)
        self._context.db_engine.load_csv_into_table(table_name, table_csv_writer.csv_path)
        self._context.db_engine.add_table_indexes(table_name)

        sql_path = self._context.map_sql_queries['update_stops_synthetic_station']
        sql = load_sql_from_file(sql_path)
        self._context.db_engine.run_sql_script(sql)

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        log_message(f'Populated {formatted_row_count} / {formatted_total_rows} stations')
        log_message('DONE populate stations')
        print('')

    def update_stations_day_bits(self):
        log_message('START update stations day_bits')

        sql_path = self._context.map_sql_queries['select_station_trips_day_bits']
        sql = load_sql_from_file(sql_path)

        db_temp_path = self._context.db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/stations_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['station_id', 'day_bits'])

        count_rows = self._context.db_engine.query('SELECT COUNT(*) AS stations_count FROM stations')
        count_row = cast(StationCountRow, count_rows[0])
        formatted_total_rows = f"{count_row['stations_count']:,}".replace(',', "'")
        stations_cursor = self._context.db_engine.get_cursor()
        db_cursor = self._context.db_engine.get_cursor()
        row_id = 0
        for station_db_row in stations_cursor.execute('SELECT station_id FROM stations'):
            if row_id % 10_000 == 0:
                formatted_row_id = f'{row_id:,}'.replace(',', "'")
                log_message(f'... parsed {formatted_row_id} / {formatted_total_rows} stations')

            station_id_row = cast(StationIdRow, station_db_row)
            station_id = station_id_row['station_id']
            db_cursor.execute(sql, {'station_id': station_id})
            db_row = db_cursor.fetchone()

            if db_row is not None:
                station_row = cast(StationTripsDayBitsRow, db_row)
                trips_day_bits_s = station_row['trips_day_bits']
                if trips_day_bits_s is not None:
                    stop_day_bits = list(station_row['day_bits'])
                    trips_day_bits = trips_day_bits_s.split(',')
                    for trip_day_bits in trips_day_bits:
                        for idx, day_bit in enumerate(trip_day_bits):
                            if day_bit == '1':
                                stop_day_bits[idx] = '1'
                        # loop trip day bits
                    # loop trip calendars

                    stop_day_bits_s = ''.join(stop_day_bits)
                    row_dict = {
                        'station_id': station_row['station_id'],
                        'day_bits': stop_day_bits_s,
                    }
                    table_csv_updater.prepare_row(row_dict)
                #
            # 

            row_id += 1
        # loop

        stations_cursor.close()
        db_cursor.close()
        table_csv_updater.close()

        sql_template = 'UPDATE stations SET day_bits = :day_bits WHERE station_id = :station_id'
        self._context.db_engine.update_table_from_csv(table_csv_path, sql_template)

        formatted_row_id = f'{row_id:,}'.replace(',', "'")
        log_message(f'Parsed {formatted_row_id} / {formatted_total_rows} stations')
        log_message('DONE update stations day_bits')
        print('')
