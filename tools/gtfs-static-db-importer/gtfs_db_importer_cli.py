import os, sys

import argparse
from datetime import datetime
from pathlib import Path

from gtfs_db_importer.helpers.config_helpers import load_yaml_config
from gtfs_db_importer.db_importer import GTFS_DB_Importer
from gtfs_db_importer.helpers.gtfs_helpers import compute_gtfs_day_from_resource_path, compute_gtfs_db_filename

def parse_date(value: str) -> datetime:
    normalized_value = value.replace('-', '')
    try:
        parsed_date = datetime.strptime(normalized_value, '%Y%m%d')
    except ValueError as error:
        raise argparse.ArgumentTypeError('Expected a valid date in YYYYMMDD or YYYY-MM-DD format') from error
    if parsed_date.strftime('%Y%m%d') != normalized_value:
        raise argparse.ArgumentTypeError('Expected a valid date in YYYYMMDD or YYYY-MM-DD format')
    return parsed_date

def main():
    script_path = Path(os.path.realpath(__file__))
    script_parent_path = script_path.parent
    config_path = Path(f'{script_parent_path}/gtfs_db_importer/config.yml')
    app_config = load_yaml_config(config_path, script_parent_path)

    parser = argparse.ArgumentParser()
    parser.add_argument('--gtfs-folder-path', '--gtfs-folder-path')
    parser.add_argument('--output-db-path', '--output-db-path')
    parser.add_argument('--from', dest='from_date', type=parse_date, metavar='DATE',
                        help='Inclusive start date (YYYYMMDD or YYYY-MM-DD); defaults to feed_start_date')
    parser.add_argument('--to', dest='to_date', type=parse_date, metavar='DATE',
                        help='Inclusive end date (YYYYMMDD or YYYY-MM-DD); defaults to feed_end_date')

    args = parser.parse_args()
    input_path = args.gtfs_folder_path

    if input_path is None:
        print("ERROR, use with --gtfs-folder-path")
        sys.exit(1)

    gtfs_folder_path = Path(os.path.abspath(input_path))

    db_path = None
    if args.output_db_path:
        db_path = Path(args.output_db_path)
    else:
        gtfs_date = compute_gtfs_day_from_resource_path(gtfs_folder_path)  
        if gtfs_date is None:
            print(f"CANT read date from GTFS path: '{gtfs_folder_path}' to build the output_db_path param")
            print(f"Use --output-db-path to use a custom name")
            sys.exit(1)

        gtfs_day_f = f'{gtfs_date}'
        db_filename = compute_gtfs_db_filename(gtfs_day_f)

        db_base_path = app_config['gtfs_dbs_base_path']
        db_path = f'{db_base_path}/{db_filename}'
        db_path = Path(db_path)

    if os.path.exists(db_path):
        print(f'ERROR - db already exists at path. Remove it or use --output-db-path for a custom name')
        print(f' {db_path}')
        sys.exit(1)
    #

    os.makedirs(db_path.parent, exist_ok=True)

    gtfs_importer = GTFS_DB_Importer(
        app_config, gtfs_folder_path, db_path, from_date=args.from_date, to_date=args.to_date,
    )
    gtfs_importer.start()

if __name__ == "__main__":
    main()
