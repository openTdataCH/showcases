import csv
from pathlib import Path
from typing import Dict, List

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class TripsMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]], first_route_id_map: Dict[str, str]):
        log_message('START merge trips')
        inputs = [
            (second_gtfs_path / 'trips.txt', False),
            (first_gtfs_path / 'trips.txt', True),
        ]
        output_path = output_gtfs_path / 'trips.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        total_rows = 0
        try:
            for input_path, is_first_dataset in inputs:
                log_message(f'Reading {input_path}')
                row_count = 0
                with input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for trip_row in csv_reader:
                        if row_count % 500_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(f'... parsed {formatted_row_count} trips from {input_path}')

                        if is_first_dataset:
                            trip_row['route_id'] = first_route_id_map[trip_row['route_id']]
                            trip_row['service_id'] = f"d1.{trip_row['service_id']}"
                            trip_row['trip_id'] = f"d1.{trip_row['trip_id']}"
                        csv_writer.prepare_row(trip_row)
                        row_count += 1
                    # loop
                # with
                total_rows += row_count
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'Parsed {formatted_row_count} trips from {input_path}')
            # loop
        finally:
            csv_writer.close()

        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Saved {formatted_total_rows} trips to {output_path}')
        log_message('DONE merge trips')
