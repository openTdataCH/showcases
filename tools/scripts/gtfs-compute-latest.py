import os, sys

import shlex
import subprocess

from datetime import timedelta
from pathlib import Path

from inc.shared.inc.helpers.config_helpers import load_convenience_config
from inc.shared.inc.helpers.gtfs_helpers import compute_gtfs_day_from_resource_path, compute_gtfs_db_filename

from inc.common import fetch_latest_resource, check_latest_data_folder

def main():
    script_path = Path(os.path.realpath(__file__))
    app_config = load_convenience_config(script_path)
    
    package_id = app_config['current_package_ids']['gtfs']
    
    print('START ./tools/scripts/gtfs-compute-latest.py')
    print()
    print('Resources:')
    print(f'    - https://data.opentransportdata.swiss/en/dataset/{package_id}')
    print('     - https://tools.opentransportdata.swiss/gtfs-static-dbs/gtfs-static-dbs.json')
    print('')
    
    fetch_latest_resource(script_path, package_id) 
    gtfs_data_path = check_latest_data_folder(app_config, package_id)
    gtfs_db_path = _db_import(app_config, script_path, gtfs_data_path)

    _db_create_lookups(script_path, gtfs_db_path)
    
    _dbs_aggregate(script_path)

def _db_import(app_config, script_path: Path, gtfs_data_path):
    gtfs_day = compute_gtfs_day_from_resource_path(gtfs_data_path)
    if gtfs_day is None:
        print(f'ERROR - cant compute GTFS day from {gtfs_data_path}')
        sys.exit(1)

    gtfs_day_s = gtfs_day.strftime('%Y-%m-%d')

    gtfs_dbs_path = app_config['data_paths']['gtfs-static-dbs']
    gtfs_db_filename = compute_gtfs_db_filename(f'{gtfs_day}')
    gtfs_db_path = f'{gtfs_dbs_path}/{gtfs_db_filename}'

    from_day = gtfs_day - timedelta(days=7)
    from_date_s = from_day.strftime('%Y-%m-%d')

    print(f'')
    print(f'STEP 3 - IMPORT GTFS into DB')
    print(f'GTFS DATA PATH  : {gtfs_data_path}')
    print(f'GTFS DB PATH    : {gtfs_db_path}')
    print(f'GTFS DAY        : {gtfs_day_s}')
    print(f'GTFS DAY FROM   : {from_date_s}')

    if os.path.isfile(gtfs_db_path):
        print(f'DB already present at path')
        print(f'=> {gtfs_db_path}')
    else:
        python_path = f'{script_path.parent}/../gtfs-static-db-importer/.venv/bin/python3'
        import_cli_path = f'{script_path.parent}/../gtfs-static-db-importer/gtfs_db_importer_cli.py'
        import_command = [
            python_path, import_cli_path, 
            '--gtfs-folder-path', str(gtfs_data_path),
            '--from', from_date_s,
        ]
        import_command_s = shlex.join(import_command)
        print()
        print(f'$ {import_command_s}', flush=True)
        print()
        subprocess.run(import_command, check=True)
    # else

    return gtfs_db_path

def _db_create_lookups(script_path: Path, gtfs_db_path: str):
    print()
    print('STEP 4 - CREATE GTFS DB lookups')

    python_path = f'{script_path.parent}/../gtfs-static-db-importer/.venv/bin/python3'
    cli_path = f'{script_path.parent}/../gtfs-static-db-importer/cli_create_db_lookups.py'
    lookups_command = [python_path, cli_path, '--gtfs_db', gtfs_db_path]
    lookups_command_s = shlex.join(lookups_command)
    print()
    print(f'$ {lookups_command_s}', flush=True)
    print()
    subprocess.run(lookups_command, check=True)

def _dbs_aggregate(script_path):
    print(f'')
    print(f'STEP 5 - BUILD GTFS DB catalog')
    
    python_path = f'{script_path.parent}/../gtfs-static-db-importer/.venv/bin/python3'
    cli_path = f'{script_path.parent}/../gtfs-static-db-importer/cli_aggregate_dbs.py'
    catalog_command = [python_path, cli_path]
    catalog_command_s = shlex.join(catalog_command)
    print()
    print(f'$ {catalog_command_s}', flush=True)
    print()
    subprocess.run(catalog_command, check=True)

if __name__ == "__main__":
    main()
