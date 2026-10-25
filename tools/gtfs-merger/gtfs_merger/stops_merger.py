import csv
from pathlib import Path
from typing import Dict, List, Set

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class StopsMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]]):
        log_message('START merge stops')
        input_paths = [second_gtfs_path / 'stops.txt', first_gtfs_path / 'stops.txt']
        seen_stop_ids: Set[str] = set()
        output_path = output_gtfs_path / 'stops.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        try:
            for input_path in input_paths:
                log_message(f'Reading {input_path}')
                row_count = 0
                with input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for stop_row in csv_reader:
                        if row_count % 50_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(f'... parsed {formatted_row_count} stops from {input_path}')

                        stop_id = stop_row['stop_id']
                        if stop_id not in seen_stop_ids:
                            csv_writer.prepare_row(stop_row)
                            seen_stop_ids.add(stop_id)
                        row_count += 1
                    # loop
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'Parsed {formatted_row_count} stops from {input_path}')
            # loop
        finally:
            csv_writer.close()

        formatted_stop_count = f'{len(seen_stop_ids):,}'.replace(',', "'")
        log_message(f'Saved {formatted_stop_count} unique stops to {output_path}')
        log_message('DONE merge stops')
