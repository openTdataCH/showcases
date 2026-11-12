import os, sys

from pathlib import Path
from typing import Optional

import json
import urllib.request

from .shared.inc.helpers.config_helpers import load_env_vars
from .shared.inc.helpers.json_helpers import export_json_to_file
from .shared.inc.helpers.log_helpers import log_message
from .shared.inc.helpers.http_helpers import download_file
from .shared.inc.helpers.zip_helpers import unzip_file

from .shared.inc.models.ckan_data import CKAN_Data

USER_AGENT = 'swiss.opentransportdata.tools.ckan-utils/1.0'
class CKAN_Controller:
    def __init__(self, app_config):
        self.app_config = app_config
        
        dotenv_path = app_config['resource_paths']['dotenv_path']
        load_env_vars(dotenv_path)

    def fetch_latest(self, 
                     package_id: str, 
                     resource_title: Optional[str], 
                     has_partial_match: bool = False,
                     overwrite: bool = False, 
                     output_dir_path: Optional[Path] = None
    ):
        log_message(f'CKAN - FETCH PACKAGE {package_id}')
        log_message(f'  PACKAGE_ID      : {package_id}')
        log_message(f'  RESOURCE_TITLE  : {resource_title}')

        ds_resource = self._fetch_package_resource(package_id, resource_title, has_partial_match)
        ds_res_filename = ds_resource.url.split('/')[-1]

        if output_dir_path is None:
            output_dir_s: str = self.app_config['resource_paths']['package_base_path']
            output_dir_s = output_dir_s.replace('[PACKAGE_ID]', package_id)
            output_dir_path = Path(output_dir_s)
        
        ds_resource_path = output_dir_path / ds_res_filename
        if overwrite or (not os.path.isfile(ds_resource_path)):
            ds_url = ds_resource.url
            
            download_ok = download_file(ds_url, ds_resource_path)
            if not download_ok:
                raise ValueError(f'ERROR while downloading {ds_url}')
        #
        
        print()
        log_message(f'... downloaded to {ds_resource_path}')
            
        ds_res_extension = Path(ds_res_filename.lower()).suffix
        if ds_res_extension == '.zip':
            ds_zip_folder = ds_res_filename[0:-4]
            ds_zip_folder_path = output_dir_path / ds_zip_folder
            if overwrite or (not os.path.isdir(ds_zip_folder_path)):
                unzip_file(ds_resource_path, ds_zip_folder_path)
                
            print()
            log_message(f'... extracted to {ds_zip_folder_path}')
        # end ds_mimetype == 'zip'
        
        print()
        log_message(f'CKAN - DONE')
        
    def fetch_metadata(self, package_id: str):
        log_message(f'CKAN - FETCH METADATA')
        log_message(f'  PACKAGE_ID      : {package_id}')
        print()
        
        ckan_data = self._fetch_ckan_metadata(package_id)
        print('- resources:')
        for ckan_resource in ckan_data.result.resources:
            print(f'  - {ckan_resource.identifier} -> {ckan_resource.url}')
            
        log_message(f'END')

    def _fetch_package_resource(self, package_id: str, filter_resource_title: Optional[str], has_partial_match: bool = False):
        ckan_data = self._fetch_ckan_metadata(package_id)
        
        if filter_resource_title is None:
            # return latest resource if filter_resource_title is missing
            return ckan_data.result.resources[0]
        
        filter_resource_title = filter_resource_title.strip().lower()
        
        for ds_resource in ckan_data.result.resources:
            ds_res_f = ds_resource.filename.lower()
            
            if ds_res_f == filter_resource_title:
                return ds_resource
            
            if has_partial_match and ds_res_f.startswith(filter_resource_title):
                return ds_resource
            
        row_delimiter_s = '='*70
        
        error_message = f'ERROR - cant find resource with title "{filter_resource_title}" with partial match={has_partial_match}'
        
        print()
        print(row_delimiter_s)
        print(error_message)
        print(row_delimiter_s)
        print(f'Available resources:                        - Last modified')
        print(row_delimiter_s)

        for ds_resource in ckan_data.result.resources:
            resource_filename: str = ds_resource.filename
            
            last_modified_day = ds_resource.modified_s[0:10]
            last_modified_hh_mm = ds_resource.modified_s[11:16]
            last_modified_s = f'{last_modified_day} {last_modified_hh_mm}'

            print(f'-- {resource_filename.ljust(40)} - {last_modified_s}')
        # loop resources
        
        raise ValueError(error_message)
        
    def _fetch_ckan_metadata(self, package_id):
        ckan_json_path: str = f"{self.app_config['resource_paths']['ckan_metadata_path']}"
        ckan_json_path = ckan_json_path.replace('[PACKAGE_ID]', package_id)

        ckan_api_url = f"{self.app_config['ckan_data']['package_show_url_template']}"
        ckan_api_url = ckan_api_url.replace('[PACKAGE_ID]', package_id)
        
        api_key = os.environ.get('OTD_KEY') or None
            
        log_message(f'... fetching package JSON from {ckan_api_url}')

        package_data_json = _fetch_latest_ckan_json(ckan_api_url, api_key)
        export_json_to_file(package_data_json, Path(ckan_json_path), pretty_print=True)
        
        ckan_data = CKAN_Data.from_ckan_json(package_data_json)

        return ckan_data

def _fetch_latest_ckan_json(ckan_api_url, ckan_api_authorization):
    if ckan_api_authorization is None:
        raise ValueError('ERROR - OTD_KEY env not defined')
    if ckan_api_authorization == 'PLACEHOLDER':
        raise ValueError('ERROR - OTD_KEY is still a placeholder, please update ./.env file with a proper value')
    
    request_headers = {
        'Authorization': ckan_api_authorization,
        'User-Agent': USER_AGENT,
    }

    ckan_api_request = urllib.request.Request(ckan_api_url, headers=request_headers)
    response = urllib.request.urlopen(ckan_api_request).read()
    response_json = json.loads(response.decode('utf-8'))

    api_status = response_json.get('success', False)
    if not api_status:
        print(f'ERROR connecting to CKAN API - {ckan_api_url}')
        sys.exit(1)
        
    # CKAN might return wrong order of the results, override this
    response_json['result']['resources'] = sorted(response_json['result']['resources'], key=lambda x: x['created'], reverse=True)
        
    return response_json
