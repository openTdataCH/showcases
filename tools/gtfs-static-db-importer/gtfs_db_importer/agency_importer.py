import csv
from pathlib import Path
from typing import cast

from .controllers.bo_controller import BusinessOrganisationGtfsRtCsvRow
from .models.gtfs.agency import AgencyDB
from .helpers.csv_helpers import read_csv_rows
from .helpers.csv_updater import CSV_Updater
from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .helpers.db_helpers import load_sql_from_file
from .import_context import ImportContext


class AgencyImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_agency(self):
        log_message('START import agency')
        agency_path = self._context.gtfs_folder_path / 'agency.txt'
        log_message(f'Reading {agency_path}')
        total_rows = compute_file_rows_no(agency_path) - 1
        if total_rows < 0:
            total_rows = 0
        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Found {formatted_total_rows} agency rows')

        agency_writer = self._context.db_engine.create_csv_writer('agency')
        row_count = 0
        kept_rows = 0
        try:
            with agency_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for agency_row in csv_reader:
                    if row_count % 10_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                        log_message(
                            f'... parsed {formatted_row_count} / {formatted_total_rows} agency rows; '
                            f'kept {formatted_kept_rows}'
                        )

                    agency_writer.prepare_row(agency_row)
                    kept_rows += 1
                    row_count += 1
                # loop agency.txt CSV rows
            # with
        finally:
            agency_writer.close()

        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        log_message(
            f'Parsed {formatted_row_count} / {formatted_total_rows} agency rows; '
            f'kept {formatted_kept_rows}'
        )
        self._context.db_engine.drop_and_recreate_table('agency')
        self._context.db_engine.load_csv_into_table('agency', agency_writer.csv_path)
        self._context.db_engine.add_table_indexes('agency')
        log_message(f'Imported {formatted_kept_rows} / {formatted_row_count} agency rows')

        # Create one link_agency row per agency, then combine its routes' day bits.
        self._populate_agency_gtfs_rt()
        log_message('DONE import agency')
        print()

    def _populate_agency_gtfs_rt(self):
        log_message(f'START populate GTFS-RT status')

        map_gtfs_agency = cast(dict[str, AgencyDB], self._context.db_engine.query_table_map_by_field('agency', 'agency_id'))
        
        map_gtfs_rt_agency_ids: dict[str, bool] = {}
        for csv_row in read_csv_rows(self._context.bo_realtime_csv_path, delimiter=';'):
            bo_csv_row = cast(BusinessOrganisationGtfsRtCsvRow, csv_row)

            agency_lookup_id = bo_csv_row['vdvBetreiberId']
            agency_id_parts = agency_lookup_id.split(':')
            if len(agency_id_parts) != 2:
                raise ValueError(f'Unexpected delimiter for vdvBetreiberId: {agency_lookup_id}')
            
            agency_id = agency_id_parts[1]
            if agency_id not in map_gtfs_agency:
                continue

            map_gtfs_rt_agency_ids[agency_id] = True
        # loop csv rows

        table_name = 'link_agency'
        self._context.db_engine.drop_and_recreate_table(table_name)
        table_csv_writer = self._context.db_engine.create_csv_writer(table_name)
        empty_day_bits = '0' * self._context.calendar_data['days_no']

        for agency_id, agency in map_gtfs_agency.items():
            has_gtfs_rt = 0
            if agency_id in map_gtfs_rt_agency_ids:
                has_gtfs_rt = 1

            row_dict = {
                'agency_id': agency_id,
                'has_gtfs_rt': has_gtfs_rt,
                'day_bits': empty_day_bits,
            }
            table_csv_writer.prepare_row(row_dict)
        # loop agencies

        table_csv_writer.close()

        self._context.db_engine.load_csv_into_table(table_name, table_csv_writer.csv_path)
        self._context.db_engine.add_table_indexes(table_name)

        log_message(f'... DONE')
        print()

    def update_agency_day_bits(self):
        log_message('START update link_agency day_bits')

        sql_path = self._context.map_sql_queries['select_agency_routes_day_bits']
        sql = load_sql_from_file(sql_path)

        db_temp_path = self._context.db_engine.get_db_tmp_path()
        table_csv_path = Path(f'{db_temp_path}/link_agency_update_day_bits.csv')
        table_csv_updater = CSV_Updater(table_csv_path, ['agency_id', 'day_bits'])

        db_cursor = self._context.db_engine.get_cursor()
        for db_row in db_cursor.execute(sql):
            routes_day_bits_s = db_row['routes_day_bits']
            if routes_day_bits_s is None:
                continue

            routes_day_bits = routes_day_bits_s.split(',')
            agency_day_bits = ['0'] * len(routes_day_bits[0])
            for route_day_bits in routes_day_bits:
                for idx, day_bit in enumerate(route_day_bits):
                    if day_bit == '1':
                        agency_day_bits[idx] = '1'

            agency_day_bits_s = ''.join(agency_day_bits)
            row_dict = {
                'agency_id': db_row['agency_id'],
                'day_bits': agency_day_bits_s,
            }
            table_csv_updater.prepare_row(row_dict)

        db_cursor.close()
        table_csv_updater.close()

        sql_template = 'UPDATE link_agency SET day_bits = :day_bits WHERE agency_id = :agency_id'
        self._context.db_engine.update_table_from_csv(table_csv_path, sql_template)

        log_message('DONE update link_agency day_bits')
        print('')
