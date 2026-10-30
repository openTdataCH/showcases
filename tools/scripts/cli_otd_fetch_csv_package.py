import os, sys

from pathlib import Path

from typing import Any, List

import argparse
import shlex
import subprocess

from inc.shared.inc.helpers.config_helpers import load_convenience_config

from inc.common import compute_ckan_resource_by_prefix

def main():
    script_path = Path(os.path.realpath(__file__))
    app_config = load_convenience_config(script_path)
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--package_id', '--package_id')
    parser.add_argument('--overwrite', '--overwrite', action='store_true')
    args = parser.parse_args()
    
    package_id = args.package_id
    if package_id is None:
        print('--package_id is required')
        
        package_ids = list(app_config['csv_latest_data'].keys())
        print(f"possible: values: {', '.join(package_ids)}" )
        sys.exit(1)
        
    if package_id not in app_config['csv_latest_data']:
        print(f'unknown --package_id value: {package_id}')
        
        package_ids = list(app_config['csv_latest_data'].keys())
        print(f"possible: values: {', '.join(package_ids)}" )
        sys.exit(1)
        
    overwrite = args.overwrite
        
    package_config = app_config['csv_latest_data'][package_id]
    package_info_url = package_config['info_url']
    
    print('START ./tools/scripts/cli_otd_fetch_csv_package.py')
    print()
    print(f'Package_id: {package_id}')
    print('Resources:')
    print(f'  - {package_info_url}')
    print()
    
    _run_package(script_path, app_config, package_id, overwrite)
    
    print()
    print('... DONE')
    
def _run_package(script_path: Path, app_config: Any, package_id: str, overwrite: bool):
    _fetch_metadata(script_path, package_id)
    _fetch_resource(script_path, app_config, package_id, overwrite)
    
def _fetch_metadata(script_path: Path, package_id: str):
    ckan_fetch_cli_path = f'{script_path.parent}/../ckan-utils/fetch_metadata_cli.py'
    python_path = f'{script_path.parent}/../ckan-utils/.venv/bin/python3'
    fetch_command = [python_path, ckan_fetch_cli_path, '--package_id', package_id]
    fetch_command_s = shlex.join(fetch_command)
    
    print('')
    print(f'STEP {package_id}.1 - FETCH METADATA')
    print(fetch_command_s, flush=True)
    subprocess.run(fetch_command, check=True)
    
    print()
    
def _fetch_resource(script_path: Path, app_config, package_id: str, overwrite: bool):
    file_prefix_config = app_config['csv_latest_data'][package_id].get('file_prefix', None)
    if file_prefix_config is None:
        _fetch_latest_resource(script_path, package_id, overwrite)
    else:
        if isinstance(file_prefix_config, list):
            file_prefixes = file_prefix_config
        else:
            file_prefixes = [file_prefix_config]
        _fetch_resource_by_prefix(app_config, script_path, package_id, file_prefixes, overwrite)
    #

def _fetch_latest_resource(script_path: Path, package_id: str, overwrite: bool):
    # fetch latest archive
    ckan_fetch_cli_path = f'{script_path.parent}/../ckan-utils/fetch_package_cli.py'
    python_path = f'{script_path.parent}/../ckan-utils/.venv/bin/python3'
    fetch_command = [python_path, ckan_fetch_cli_path, '--package_id', package_id]
    if overwrite:
        fetch_command.append('--overwrite')
    fetch_command_s = shlex.join(fetch_command)
    
    print(f'STEP {package_id}.2 - FETCH LATEST RESOURCE')
    print(fetch_command_s, flush=True)
    subprocess.run(fetch_command, check=True)
    
def _fetch_resource_by_prefix(app_config: Any, script_path: Path, package_id: str, resource_prefixes: List[str], overwrite: bool):
    for resource_prefix in resource_prefixes:
        ckan_resource = compute_ckan_resource_by_prefix(app_config, package_id, resource_prefix)
    
        # fetch latest archive
        ckan_fetch_cli_path = f'{script_path.parent}/../ckan-utils/fetch_package_cli.py'
        python_path = f'{script_path.parent}/../ckan-utils/.venv/bin/python3'
        fetch_command = [
            python_path, ckan_fetch_cli_path, '--package_id', package_id,
            '--resource_title', ckan_resource.identifier,
        ]
        if overwrite:
            fetch_command.append('--overwrite')
        fetch_command_s = shlex.join(fetch_command)
    
        print(f'STEP {package_id}.2 - FETCH RESOURCE by PREFIX {ckan_resource.identifier}')
        print(fetch_command_s, flush=True)
        subprocess.run(fetch_command, check=True)
    # loop

    print()

if __name__ == "__main__":
    main()
