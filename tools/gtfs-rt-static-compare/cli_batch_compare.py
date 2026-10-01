import os, sys

import re
import argparse

from pathlib import Path
from typing import List
from datetime import datetime

from compare_gtfs_rt_static.gtfs_controller import GTFS_Controller
from compare_gtfs_rt_static.gtfs_db import GTFS_DB, DayTripData
from compare_gtfs_rt_static.helpers.json_helpers import load_json_from_file
from compare_gtfs_rt_static.models.gtfs_rt import GTFS_RT_Response
from compare_gtfs_rt_static.helpers.log_helpers import format_path, log_message

file_match_regexp = r"GTFS_RT-([0-9]{4}-[0-9]{2}-[0-9]{2})-([0-9]{4})\."

def main():
    app_path = Path(os.path.realpath(__file__)).parent
    
    report_now = datetime.now()
    # default is current day
    report_date_filter = report_now.strftime('%Y-%m-%d')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--filter', '--filter', default=report_date_filter)
    args = parser.parse_args()
    
    report_date_filter = args.filter

    gtfs_rt_snapshot_files_path = Path(f'{app_path}/data/gtfs-rt-snapshot')
    log_message(f"START batch processing snapshots")
    log_message(f"path                  : {format_path(f'{gtfs_rt_snapshot_files_path}', f'{app_path}')}")
    log_message(f'filter (starts with)  : GTFS_RT-{report_date_filter}')
    print()

    map_gtfs_rt_file_paths: dict[str, List[Path]] = {}
    for gtfs_rt_file_path in gtfs_rt_snapshot_files_path.rglob('*.json*'):
        keep_file = False
        if gtfs_rt_file_path.name.startswith(f'GTFS_RT-{report_date_filter}'):
            keep_file = True
        if not keep_file:
            continue
        
        file_matches = re.match(file_match_regexp, gtfs_rt_file_path.name)
        if file_matches is None:
            continue

        file_day_f: str = file_matches[1]
        if file_day_f not in map_gtfs_rt_file_paths:
            map_gtfs_rt_file_paths[file_day_f] = []
        
        map_gtfs_rt_file_paths[file_day_f].append(gtfs_rt_file_path)
    #

    sorted_days = sorted(map_gtfs_rt_file_paths.keys())
    sorted_map_gtfs_rt_file_paths: dict[str, List[Path]] = {}
    files_no = 0
    for file_day_f in sorted_days:
        gtfs_rt_file_paths = map_gtfs_rt_file_paths[file_day_f]
        sorted_map_gtfs_rt_file_paths[file_day_f] = sorted(gtfs_rt_file_paths)
        files_no += len(gtfs_rt_file_paths)
    # end for days - sort
    map_gtfs_rt_file_paths = sorted_map_gtfs_rt_file_paths

    log_message(f'... found {files_no} files')
    print()

    gtfs_controller = GTFS_Controller(app_path)

    map_gtfs_dbs: dict[str, GTFS_DB] = {}
    map_day_data_trips: dict[str, DayTripData] = {}
    for file_day_f, gtfs_rt_file_paths in map_gtfs_rt_file_paths.items():
        log_message(f'... DAY {file_day_f} -> {len(gtfs_rt_file_paths)} files')

        for gtfs_rt_file_path in gtfs_rt_file_paths:
            file_matches = re.match(file_match_regexp, gtfs_rt_file_path.name)
            if file_matches is None:
                continue
        
            file_date_f = file_matches[1]
            file_hhmm = file_matches[2]
            file_dt = datetime.strptime(f'{file_date_f} {file_hhmm}', '%Y-%m-%d %H%M')

            gtfs_rt_json = load_json_from_file(gtfs_rt_file_path)
            gtfs_rt_response = GTFS_RT_Response.from_gtfs_rt_json(gtfs_rt_json)

            feed_version = gtfs_rt_response.header.feedVersion
            gtfs_catalog_item = gtfs_controller.gtfs_dbs_report.lookup_by_feed_verson(feed_version)

            if gtfs_catalog_item is None:
                print(f'file: {gtfs_rt_file_path.name} => cant find GTFS DB for {feed_version}')
                continue

            gtfs_day = gtfs_catalog_item.gtfs_day
            if gtfs_day not in map_gtfs_dbs:
                log_message(f'... loading GTFS DB for {gtfs_day}')
                gtfs_db = gtfs_controller.load_gtfs_db(gtfs_catalog_item)
                map_gtfs_dbs[gtfs_day] = gtfs_db
            # 
            gtfs_db = map_gtfs_dbs[gtfs_day]

            file_day = datetime.strptime(file_day_f, '%Y-%m-%d').date()
            start_dates = {file_day}
            for entity in gtfs_rt_response.entity:
                start_dates.add(gtfs_controller.parse_trip_start_date(entity.tripUpdate.trip.startDate))

            file_map_day_data_trips: dict[str, DayTripData] = {}
            for start_date in start_dates:
                start_date_f = start_date.isoformat()
                day_data_key = f'{gtfs_day}-{start_date_f}'
                if day_data_key not in map_day_data_trips:
                    log_message(f'... loading GTFS day trips for DB:{gtfs_day} in day:{start_date_f}')
                    map_day_data_trips[day_data_key] = gtfs_db.compute_day_data(start_date)
                file_map_day_data_trips[start_date_f] = map_day_data_trips[day_data_key]

            gtfs_controller.compare_gtfs_rt_from_file(
                gtfs_rt_response, file_dt, gtfs_rt_file_path, 
                gtfs_catalog_item, 
                file_map_day_data_trips,
            )
        # loop files
        log_message('... done day')
        print()
    # loop days
    print()

    log_message('DONE LOOP')

if __name__ == "__main__":
    main()
