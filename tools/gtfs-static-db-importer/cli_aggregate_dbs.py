import os
import sys
from pathlib import Path

from typing import Any, Dict, List
from datetime import datetime

from gtfs_db_importer.helpers.config_helpers import load_yaml_config
from gtfs_db_importer.models.gtfs_static_db_catalog import GTFS_Static_Catalog_Report, GTFS_Static_Catalog_Item
from gtfs_db_importer.models.ckan_data import CKAN_Data, CKAN_Resource
from gtfs_db_importer.helpers.json_helpers import export_json_to_file, load_json_from_file
from gtfs_db_importer.helpers.gtfs_helpers import compute_date_from_gtfs_db_filename, compute_gtfs_day_from_resource_path, compute_gtfs_dt_from_resource_path
from gtfs_db_importer.helpers.db_engine import SQLiteDBEngine

from gtfs_db_importer.helpers.log_helpers import log_message

def main():
    script_path = Path(os.path.realpath(__file__))
    script_parent_path = script_path.parent
    config_path = script_parent_path / 'gtfs_db_importer/config.yml'
    app_config = load_yaml_config(config_path, script_parent_path)

    _process(app_config)

def _scan_local_dbs(app_config: Any) -> Dict[str, Path]:
    map_local_dbs = {}
    
    gtfs_dbs_base_path = Path(app_config['gtfs_dbs_base_path'])
    gtfs_db_paths = gtfs_dbs_base_path.rglob('gtfs_*.sqlite')
    
    for gtfs_db_path in gtfs_db_paths:
        gtfs_db_lock_path = Path(f'{gtfs_db_path}.lock')
        if os.path.isfile(gtfs_db_lock_path):
            continue
        
        gtfs_db_date = compute_date_from_gtfs_db_filename(gtfs_db_path.name)
        if gtfs_db_date is None:
            print('ERROR - cant extract day from filename')
            print(gtfs_db_path.name)
            sys.exit(1)
            
        gtfs_day = gtfs_db_date.strftime('%Y-%m-%d')
        
        relative_path = gtfs_db_path.relative_to(gtfs_dbs_base_path)
        
        map_local_dbs[gtfs_day] = relative_path
        
    return map_local_dbs

def _load_ckan_data(app_config: Any) -> List[CKAN_Resource]:
    scripts_config_path = app_config['other_config_paths']['scripts_config']
    scripts_config = load_yaml_config(scripts_config_path)
    gtfs_package_id = scripts_config['current_package_ids']['gtfs']
    
    gtfs_ckan_json_path: str = app_config['gtfs_ckan_json_path']
    gtfs_ckan_json_path = gtfs_ckan_json_path.replace('[PACKAGE_ID]', gtfs_package_id)
    gtfs_ckan_json = load_json_from_file(Path(gtfs_ckan_json_path))
    gtfs_ckan = CKAN_Data.from_ckan_json(gtfs_ckan_json)
    
    return gtfs_ckan.result.resources

def _compute_map_gtfs_static_catalog(app_config) -> Dict[str, GTFS_Static_Catalog_Item]:
    gtfs_static_db_path_report_path = app_config['gtfs_dbs_json_path']
    
    map_gtfs_catalog_items = {}
    
    if not os.path.isfile(gtfs_static_db_path_report_path):
        return map_gtfs_catalog_items
    
    gtfs_static_db_path_report_json = load_json_from_file(gtfs_static_db_path_report_path)
    gtfs_static_db_path_report = GTFS_Static_Catalog_Report.from_json(gtfs_static_db_path_report_json)
    for gtfs_catalog_item in gtfs_static_db_path_report.items:
        gtfs_db_day = gtfs_catalog_item.gtfs_day
        map_gtfs_catalog_items[gtfs_db_day] = gtfs_catalog_item
    
    return map_gtfs_catalog_items
    
def _process(app_config: Any):
    map_gtfs_static_catalog = _compute_map_gtfs_static_catalog(app_config)
    map_local_dbs = _scan_local_dbs(app_config)
    ckan_data = _load_ckan_data(app_config)
    
    gtfs_dbs_base_path = Path(app_config['gtfs_dbs_base_path'])
    
    gtfs_rt_updates_splits_dt: List[datetime] = []
    gtfs_rt_update_times: List[str] = []
    for gtfs_update_interval_config in app_config['gtfs_rt_updates']:
        to_dt = datetime.strptime(gtfs_update_interval_config['to'], '%Y-%m-%d')
        gtfs_rt_updates_splits_dt.append(to_dt)
        
        gtfs_rt_update_times.append(gtfs_update_interval_config['switch'])
    # loop app_config['gtfs_rt_updates']
    
    # loop through all CKAN resources and create new GTFS_Static_DB_Item objects if needed
    for ckan_resource in ckan_data:
        gtfs_day = compute_gtfs_day_from_resource_path(Path(ckan_resource.identifier))
        if gtfs_day is None:
            print(f'ERROR - cant extract GTFS day from resource: {ckan_resource.identifier}')
            sys.exit(1)
            
        gtfs_day_f = f'{gtfs_day}'
            
        if gtfs_day_f in map_gtfs_static_catalog:
            continue
        
        # for datasets before may 2024 try to get the datetime from the filename, i.e. GTFS_FP2024_2024-04-15_08-54.zip
        # otherwise CKAN .created and .updated are not reflecting the dataset publishing date
        resource_dt = compute_gtfs_dt_from_resource_path(Path(ckan_resource.identifier))
        if resource_dt is None:
            # if no info in the filename then rely on the CKAN .created datetime
            resource_dt = datetime.fromisoformat(ckan_resource.created_s)
        
        gtfs_db_relative_path = map_local_dbs.get(gtfs_day_f, None)
        if gtfs_db_relative_path is None:
            continue
        
        resource_dt_f = resource_dt.strftime('%Y-%m-%d %H:%M')
        resource_day_f = resource_dt.strftime('%Y-%m-%d')
        
        gtfs_rt_update_time = gtfs_day.strftime('%H:%M')
        for idx, gtfs_rt_updates_split_dt in enumerate(gtfs_rt_updates_splits_dt):
            if resource_dt.timestamp() < gtfs_rt_updates_split_dt.timestamp():
                gtfs_rt_update_time = gtfs_rt_update_times[idx]
                break
        # loop gtfs_rt_updates_splits_dt
        
        gtfs_rt_switch_datetime_s = f'{resource_day_f} {gtfs_rt_update_time}'
        
        gtfs_catalog_item = GTFS_Static_Catalog_Item(
            gtfs_datetime_s=resource_dt_f,
            gtfs_day=gtfs_day_f,
            gtfs_rt_switch_datetime_s=gtfs_rt_switch_datetime_s,
            table_stats={}, # compute them in the next loop
            db_relative_path=f'{gtfs_db_relative_path}',
        )
        
        map_gtfs_static_catalog[gtfs_day_f] = gtfs_catalog_item
    # loop ckan_resource in ckan_data
    
    # loop through all catalog items and validate if DB file is present locally
    for gtfs_day_f, gtfs_catalog_item in map_gtfs_static_catalog.items():
        gtfs_db_relative_path = map_local_dbs.get(gtfs_day_f, None)
        if gtfs_db_relative_path is None:
            gtfs_catalog_item.db_relative_path = None
        else:
            gtfs_catalog_item.db_relative_path = f'{gtfs_db_relative_path}' # format otherwise JSON encoder will scream
        
        # compute stats only if necessary
        if gtfs_catalog_item.table_stats == {} and gtfs_db_relative_path is not None:
            gtfs_db_path = Path(f'{gtfs_dbs_base_path}/{gtfs_db_relative_path}')
            gtfs_db_engine = SQLiteDBEngine(gtfs_db_path)
            gtfs_catalog_item.table_stats = gtfs_db_engine.compute_table_stats()
    
    # build a list and sort descending by gtfs_day
    gtfs_catalog_items = list(map_gtfs_static_catalog.values())
    gtfs_catalog_items = sorted(gtfs_catalog_items, key=lambda x: x.gtfs_day, reverse=True)
    
    now_f = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    metadata = f'Created at {now_f}'
    gtfs_catalog = GTFS_Static_Catalog_Report(metadata, items=gtfs_catalog_items)
    
    gtfs_catalog_path = app_config['gtfs_dbs_json_path']
    gtfs_catalog_json = gtfs_catalog.as_json()
    export_json_to_file(gtfs_catalog_json, gtfs_catalog_path, pretty_print=True)
    
    log_message(f'... saved to {gtfs_catalog_path}')    
    
if __name__ == "__main__":
    main()
