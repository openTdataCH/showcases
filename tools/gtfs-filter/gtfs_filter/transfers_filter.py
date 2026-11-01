import csv
from pathlib import Path
from typing import Dict, List, Optional, Set

from .filter_context import FilterContext
from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class TransfersFilter:
    def filter(
        self, source_gtfs_path: Path, destination_gtfs_path: Path, context: FilterContext,
    ) -> None:
        source_path = source_gtfs_path / 'transfers.txt'
        if not source_path.is_file():
            log_message(f'Skipping transfers.txt: source file not found at {source_path}')
            return

        destination_path = destination_gtfs_path / 'transfers.txt'
        log_message(f'Reading {source_path}; checking active service, stop, route and trip IDs')
        parsed_rows = 0
        kept_rows = 0
        with source_path.open('r', encoding='utf-8-sig', newline='') as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise ValueError(f'Missing CSV header in {source_path}')
            column_names = list(reader.fieldnames)
            writer = CSV_Updater(destination_path, column_names)
            try:
                for row in reader:
                    parsed_rows += 1
                    if parsed_rows % 5_000_000 == 0:
                        log_message(f'Parsed {parsed_rows} transfers rows; kept {kept_rows}')
                    if not self._is_active(row, context):
                        continue
                    writer.prepare_row(row)
                    kept_rows += 1
            finally:
                writer.close()
        dropped_rows = parsed_rows - kept_rows
        log_message(f'Saved {kept_rows} transfers to {destination_path}; discarded {dropped_rows}')

    def _is_active(self, row: Dict[str, Optional[str]], context: FilterContext) -> bool:
        if self._has_inactive_reference(row, ['service_id'], context.active_service_ids):
            return False

        trip_fields = ['from_trip_id', 'to_trip_id']
        route_fields = ['from_route_id', 'to_route_id']
        has_trip = self._has_reference(row, trip_fields)
        has_route = self._has_reference(row, route_fields)

        if not has_trip:
            if has_route:
                if self._has_inactive_reference(row, route_fields, context.active_route_ids):
                    return False
            else:
                stop_fields = ['from_stop_id', 'to_stop_id']
                if self._has_inactive_reference(row, stop_fields, context.active_stop_ids):
                    return False

        if self._has_inactive_reference(row, trip_fields, context.active_trip_ids):
            return False
        return True

    def _has_reference(self, row: Dict[str, Optional[str]], fields: List[str]) -> bool:
        for field in fields:
            reference = row.get(field)
            if reference is not None and reference != '':
                return True
        return False

    def _has_inactive_reference(
        self, row: Dict[str, Optional[str]], fields: List[str], active_ids: Set[str],
    ) -> bool:
        for field in fields:
            reference = row.get(field)
            if reference is None or reference == '':
                continue
            if reference not in active_ids:
                return True
        return False
