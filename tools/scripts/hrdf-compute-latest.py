import os, sys

import shlex
import subprocess

from pathlib import Path

import time

from inc.shared.inc.helpers.config_helpers import load_convenience_config
from inc.shared.inc.helpers.hrdf_helpers import compute_formatted_date_from_hrdf_folder_path, compute_hrdf_db_filename, compute_formatted_date_from_hrdf_db_path

from inc.common import fetch_latest_resource, check_latest_data_folder

def main():
    script_path = Path(os.path.realpath(__file__))
    app_config = load_convenience_config(script_path)
    
    package_id = app_config['current_package_ids']['hrdf']
    
    print('START ./tools/scripts/hrdf-compute-latest.py')
    print()
    print('Resources:')
    print(f'    - https://data.opentransportdata.swiss/en/dataset/{package_id}')
    print('  - https://tools.opentransportdata.swiss/hrdf-dbs/hrdf-dbs.json')
    print('')

    fetch_latest_resource(script_path, package_id)
    hrdf_data_path = check_latest_data_folder(app_config, package_id)

    hrdf_db_path = _db_import(app_config, script_path, hrdf_data_path)
    _dbs_aggregate(script_path)
    _hrdf_check_duplicates(script_path, hrdf_db_path)
    _hrdf_build_aggregated_duplicates(script_path)
    _hrdf_generate_lookups(script_path, hrdf_db_path)

def _db_import(app_config, script_path, hrdf_data_path):
    hrdf_day = compute_formatted_date_from_hrdf_folder_path(hrdf_data_path)
    if hrdf_day is None:
        print(f'ERROR - cant compute HRDF day from {hrdf_data_path}')
        sys.exit(1)

    hrdf_dbs_path = app_config['data_paths']['hrdf-dbs']
    hrdf_db_filename = compute_hrdf_db_filename(hrdf_day)
    hrdf_db_path = f'{hrdf_dbs_path}/{hrdf_db_filename}'

    print(f'')
    print(f'STEP 3 - IMPORT HRDF into DB')
    print(f'HRDF PATH       : {hrdf_data_path}')
    print(f'HRDF DB PATH    : {hrdf_db_path}')

    if os.path.isfile(hrdf_db_path):
        print(f'DB already present at path')
        print(f'=> {hrdf_db_path}')
    else:
        python_path = f'{script_path.parent}/../hrdf-db-importer/.venv/bin/python3'
        hrdf_import_cli_path = f'{script_path.parent}/../hrdf-db-importer/hrdf_db_importer_cli.py'
        import_command = [python_path, hrdf_import_cli_path, '--hrdf-folder-path', str(hrdf_data_path)]
        import_command_s = shlex.join(import_command)
        print()
        print(f'$ {import_command_s}', flush=True)
        print()
        subprocess.run(import_command, check=True)

    return hrdf_db_path

def _dbs_aggregate(script_path):
    print(f'')
    print(f'STEP 4 - BUILD HRDF DB catalog')
    
    python_path = f'{script_path.parent}/../hrdf-db-importer/.venv/bin/python3'
    cli_path = f'{script_path.parent}/../hrdf-db-importer/cli_aggregate_dbs.py'
    catalog_command = [python_path, cli_path]
    catalog_command_s = shlex.join(catalog_command)
    print()
    print(f'$ {catalog_command_s}', flush=True)
    print()
    subprocess.run(catalog_command, check=True)

def _hrdf_check_duplicates(script_path, hrdf_db_path):
    hrdf_day = compute_formatted_date_from_hrdf_db_path(hrdf_db_path)
    if hrdf_day is None:
        print(f'ERROR - cant compute HRDF day from {hrdf_db_path}')
        sys.exit(1)
    
    hrdf_duplicates_tool_folder_path = Path(f'{script_path.parent}/../hrdf-check-duplicates')
    hrdf_duplicates_config = load_convenience_config(hrdf_duplicates_tool_folder_path)

    hrdf_duplicates_report_path: str = hrdf_duplicates_config['report_paths']['hrdf_duplicates_report_path']
    hrdf_duplicates_report_path = hrdf_duplicates_report_path.replace('[HRDF_YMD]', hrdf_day)

    print(f'')
    print(f'STEP 5 - CHECK HRDF duplicates')
    print(f'HRDF DB PATH            : {hrdf_db_path}')
    print(f'DUPLICATES JSON PATH    : {hrdf_duplicates_report_path}')

    if os.path.isfile(hrdf_duplicates_report_path):
        print(f'Report already present at path')
        print(f'=> {hrdf_duplicates_report_path}')
    else:
        python_path = f'{script_path.parent}/../hrdf-check-duplicates/.venv/bin/python3'
        tool_cli_path = f'{hrdf_duplicates_tool_folder_path}/hrdf_check_duplicates_cli.py'
        tool_command = [python_path, tool_cli_path, '--hrdf-db-path', str(hrdf_db_path)]
        tool_command_s = shlex.join(tool_command)
        print()
        print(f'$ {tool_command_s}', flush=True)
        print()
        subprocess.run(tool_command, check=True)

def _hrdf_build_aggregated_duplicates(script_path):
    print(f'')
    print(f'STEP 6 - BUILD HRDF CSV duplicates report')

    hrdf_duplicates_tool_folder_path = Path(f'{script_path.parent}/../hrdf-check-duplicates')
    hrdf_duplicates_config = load_convenience_config(hrdf_duplicates_tool_folder_path)

    report_csv_all_path = hrdf_duplicates_config['report_paths']['consolidate_hrdf_duplicates_report_path']
    report_csv_all_path = report_csv_all_path.replace('[AGENCY_ID]', 'ALL')

    run_cli = True
    if os.path.isfile(report_csv_all_path):
        report_csv_all_mtime = os.path.getmtime(report_csv_all_path)
        now_ts = time.time()
        
        # 60 minutes
        if (now_ts - report_csv_all_mtime) < (60 * 60):
            run_cli = False

    if run_cli:
        python_path = f'{script_path.parent}/../hrdf-check-duplicates/.venv/bin/python3'
        tool_cli_path = f'{hrdf_duplicates_tool_folder_path}/hrdf_build_consolidated_report_cli.py'
        tool_command = [python_path, tool_cli_path]
        tool_command_s = shlex.join(tool_command)
        print()
        print(f'$ {tool_command_s}', flush=True)
        print()
        subprocess.run(tool_command, check=True)
    else:
        print(f'Report already present at path and not too old')
        print(f'=> {report_csv_all_path}')

def _hrdf_generate_lookups(script_path, hrdf_db_path):
    tool_cli_folder_path = f'{script_path.parent}/../hrdf-db-importer'

    print(f'')
    print(f'STEP 7 - GENERATE HRDF DB lookups')
    print(f'HRDF DB PATH            : {hrdf_db_path}')

    # No need to do extra checks for the file existance because the generation is fast

    python_path = f'{script_path.parent}/../hrdf-db-importer/.venv/bin/python3'
    tool_cli_path = f'{tool_cli_folder_path}/hrdf_db_lookups_generator_cli.py'
    tool_command = [python_path, tool_cli_path, '--hrdf-db-path', str(hrdf_db_path)]
    tool_command_s = shlex.join(tool_command)
    print()
    print(f'$ {tool_command_s}', flush=True)
    print()
    subprocess.run(tool_command, check=True)
    
if __name__ == "__main__":
    main()
