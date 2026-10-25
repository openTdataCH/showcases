import csv
from pathlib import Path
from typing import Dict, List

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class StopTimesMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]]):
        log_message('START merge stop_times')
        inputs = [
            (second_gtfs_path / 'stop_times.txt', ''),
            (first_gtfs_path / 'stop_times.txt', 'd1.'),
        ]
        output_path = output_gtfs_path / 'stop_times.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        total_rows = 0
        try:
            for input_path, trip_id_prefix in inputs:
                log_message(f'Reading {input_path}')
                row_count = 0
                with input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for stop_time_row in csv_reader:
                        if row_count % 5_000_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(f'... parsed {formatted_row_count} stop_times rows from {input_path}')

                        stop_time_row['trip_id'] = f"{trip_id_prefix}{stop_time_row['trip_id']}"
                        csv_writer.prepare_row(stop_time_row)
                        row_count += 1
                    # loop
                # with
                total_rows += row_count
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'Parsed {formatted_row_count} stop_times rows from {input_path}')
            # loop
        finally:
            csv_writer.close()

        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Saved {formatted_total_rows} stop_times rows to {output_path}')
        log_message('DONE merge stop_times')
