import csv
from typing import Dict

from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .import_context import ImportContext


class TransfersImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_transfers(self):
        log_message('START import transfers')
        transfers_path = self._context.gtfs_folder_path / 'transfers.txt'
        transfers_writer = self._context.db_engine.create_csv_writer('transfers')
        row_count = 0
        kept_rows = 0
        try:
            if transfers_path.is_file():
                log_message(f'Reading {transfers_path}')
                total_rows = compute_file_rows_no(transfers_path) - 1
                if total_rows < 0:
                    total_rows = 0
                formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
                log_message(f'Found {formatted_total_rows} transfers rows')
                with transfers_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for transfer_row in csv_reader:
                        if row_count % 500_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                            log_message(
                                f'... parsed {formatted_row_count} / {formatted_total_rows} transfers rows; '
                                f'kept {formatted_kept_rows}'
                            )

                        # Require every supplied service, trip, and route reference to be active.
                        # Transfers with only stop references are kept.
                        if self._is_active_transfer(transfer_row):
                            transfers_writer.prepare_row(transfer_row)
                            kept_rows += 1
                        row_count += 1
                    # loop transfers.txt CSV rows
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
                log_message(
                    f'Parsed {formatted_row_count} / {formatted_total_rows} transfers rows; '
                    f'kept {formatted_kept_rows}'
                )
            else:
                log_message('No transfers.txt present; creating an empty transfers table')
        finally:
            transfers_writer.close()

        self._context.db_engine.drop_and_recreate_table('transfers')
        self._context.db_engine.load_csv_into_table('transfers', transfers_writer.csv_path)
        self._context.db_engine.add_table_indexes('transfers')
        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        formatted_kept_rows = f'{kept_rows:,}'.replace(',', "'")
        log_message(f'Imported {formatted_kept_rows} / {formatted_row_count} transfers rows')
        log_message('DONE import transfers')
        print()

    def _is_active_transfer(self, transfer_row: Dict[str, str]) -> bool:
        service_id = transfer_row.get('service_id')
        if service_id is not None:
            service_id = service_id.strip()
            if service_id != '':
                if service_id not in self._context.active_service_ids:
                    return False

        for field in ['from_trip_id', 'to_trip_id']:
            trip_id = transfer_row.get(field)
            if trip_id is not None:
                trip_id = trip_id.strip()
                if trip_id != '':
                    if trip_id not in self._context.active_trip_ids:
                        return False
        # loop trip references

        for field in ['from_route_id', 'to_route_id']:
            route_id = transfer_row.get(field)
            if route_id is not None:
                route_id = route_id.strip()
                if route_id != '':
                    if route_id not in self._context.active_route_ids:
                        return False
        # loop route references
        return True
