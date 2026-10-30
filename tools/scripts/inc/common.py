import os, sys

import shlex
import subprocess

from pathlib import Path
from .shared.inc.helpers.json_helpers import load_json_from_file
from .shared.inc.models.ckan_data import CKAN_Data

ROW_DELIMITER_S = '='*70

def fetch_latest_resource(script_path: Path, package_id: str):
    # fetch latest archive
    python_path = f'{script_path.parent}/../ckan-utils/.venv/bin/python3'
    ckan_fetch_cli_path = f'{script_path.parent}/../ckan-utils/fetch_package_cli.py'
    fetch_command = [python_path, ckan_fetch_cli_path, '--package_id', package_id]
    fetch_command_s = shlex.join(fetch_command)
    
    print('STEP 1 - FETCH LATEST ARCHIVE')
    print(fetch_command_s, flush=True)
    subprocess.run(fetch_command, check=True)
    
def compute_ckan_data(app_config, package_id: str):
    ckan_metadata_path: str = app_config['resource_paths']['ckan_metadata_path']
    ckan_metadata_path = ckan_metadata_path.replace('[PACKAGE_ID]', package_id)
    ckan_metadata_json = load_json_from_file(Path(ckan_metadata_path))
    ckan_data = CKAN_Data.from_ckan_json(ckan_metadata_json)
    
    return ckan_data

def check_latest_data_folder(app_config, package_id: str):
    # check latest folder
    print('')
    print(f'STEP 2 - CHECK LATEST DATASET {package_id}')
    
    ckan_data = compute_ckan_data(app_config, package_id)
    
    # convention: first resource is the latest published
    ckan_resource = ckan_data.result.resources[0]
    
    resources_base_folder_path_s: str = app_config['data_paths']['opentransportdata']
    resources_base_folder_path = f'{resources_base_folder_path_s}/{package_id}'
    
    if ckan_resource.extension != '.zip':
        print(f'ERROR: expected ZIP archive for {package_id}')
        print(ckan_resource)
        sys.exit(1)
    
    # zip resources are unzipped in fetch, use the unzipped folder name
    resource_folder_name = ckan_resource.filename[0:-4]
    
    resource_path = Path(f'{resources_base_folder_path}/{resource_folder_name}')
    
    if not os.path.isdir(resource_path):
        print()
        print(ROW_DELIMITER_S)
        print('ERROR - latest resource not found at path')
        print(resource_path)
        print(ROW_DELIMITER_S)
        sys.exit(1)
    
    print(f'... use following resource: {resource_path}')
    
    return resource_path

def compute_ckan_resource_by_prefix(app_config, package_id: str, resource_prefix: str):
    ckan_data = compute_ckan_data(app_config, package_id)
    
    ckan_resource = None
    for ckan_resource_item in ckan_data.result.resources:
        if not ckan_resource_item.filename.startswith(resource_prefix):
            continue
        
        ckan_resource = ckan_resource_item
        break
    # loop resources
    
    if ckan_resource is None:
        print()
        print(ROW_DELIMITER_S)
        print('ERROR - ckan resource cant be found')
        print()
        print(ckan_data.result.resources)
        print()
        print(ROW_DELIMITER_S)
        sys.exit(1)
    #
        
    return ckan_resource
