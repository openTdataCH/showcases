import csv
from pathlib import Path
from typing import Dict, List

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class CalendarMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]]):
        log_message('START merge calendar')
        inputs = [
            (second_gtfs_path / 'calendar.txt', ''),
            (first_gtfs_path / 'calendar.txt', 'd1.'),
        ]
        output_path = output_gtfs_path / 'calendar.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        total_rows = 0
        try:
            for input_path, service_id_prefix in inputs:
                log_message(f'Reading {input_path}')
                row_count = 0
                with input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for calendar_row in csv_reader:
                        if row_count % 50_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(f'... parsed {formatted_row_count} calendar rows from {input_path}')

                        calendar_row['service_id'] = f"{service_id_prefix}{calendar_row['service_id']}"
                        csv_writer.prepare_row(calendar_row)
                        row_count += 1
                    # loop
                # with
                total_rows += row_count
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'Parsed {formatted_row_count} calendar rows from {input_path}')
            # loop
        finally:
            csv_writer.close()

        formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
        log_message(f'Saved {formatted_total_rows} calendar rows to {output_path}')
        log_message('DONE merge calendar')
