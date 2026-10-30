import csv
from pathlib import Path
from typing import Dict, List, Set

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class AgencyMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]]):
        log_message('START merge agencies')
        input_paths = [second_gtfs_path / 'agency.txt', first_gtfs_path / 'agency.txt']
        seen_agency_ids: Set[str] = set()
        output_path = output_gtfs_path / 'agency.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        try:
            for input_path in input_paths:
                log_message(f'Reading {input_path}')
                row_count = 0
                with input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for agency in csv_reader:
                        if row_count % 10_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(f'... parsed {formatted_row_count} agencies from {input_path}')

                        agency_id = agency['agency_id']
                        if agency_id not in seen_agency_ids:
                            csv_writer.prepare_row(agency)
                            seen_agency_ids.add(agency_id)
                        row_count += 1
                    # loop
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(f'Parsed {formatted_row_count} agencies from {input_path}')
            # loop
        finally:
            csv_writer.close()

        formatted_agency_count = f'{len(seen_agency_ids):,}'.replace(',', "'")
        log_message(f'Saved {formatted_agency_count} unique agencies to {output_path}')
        log_message('DONE merge agencies')
