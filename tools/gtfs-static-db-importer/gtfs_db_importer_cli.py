import argparse, os, sys
from pathlib import Path

from gtfs_db_importer.helpers.config_helpers import load_yaml_config
from gtfs_db_importer.db_importer import GTFS_DB_Importer
from gtfs_db_importer.helpers.gtfs_helpers import compute_gtfs_day_from_resource_path, compute_gtfs_db_filename

def main():
    script_path = Path(os.path.realpath(__file__))
    script_parent_path = script_path.parent
    config_path = Path(f'{script_parent_path}/gtfs_db_importer/config.yml')
    app_config = load_yaml_config(config_path, script_parent_path)

    parser = argparse.ArgumentParser()
    parser.add_argument('--gtfs-folder-path', '--gtfs-folder-path')
    parser.add_argument('--output-db-path', '--output-db-path')

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

    gtfs_importer = GTFS_DB_Importer(app_config, gtfs_folder_path, db_path)
    gtfs_importer.start()

if __name__ == "__main__":
    main()
