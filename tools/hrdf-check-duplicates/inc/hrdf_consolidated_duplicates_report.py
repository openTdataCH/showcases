import os, sys
import time
import json

from datetime import datetime

import urllib.request

from .shared.inc.helpers.log_helpers import log_message
from .shared.inc.helpers.json_helpers import load_json_from_file, export_json_to_file
from .shared.inc.helpers.csv_updater import CSV_Updater

class HRDF_Consolidated_Duplicates_Report:
    def __init__(self, app_config):
        log_message('HRDF_Consolidated_Duplicates_Report - START INIT')
        self.duplicates_url = app_config['report_urls']['duplicate_days']
        self.duplicates_url_cache_path = app_config['report_paths']['duplicate_days_json_path']
        self.duplicates_report_path_template = app_config['report_paths']['hrdf_duplicates_report_path']
        self.consolidate_hrdf_duplicates_report_path_template = app_config['report_paths']['consolidate_hrdf_duplicates_report_path']

    def compute_consolidated_report(self):
        duplicates_list_json = self.fetch_report_duplicates_list()
        
        report_year = datetime.now().year
        last_year = report_year - 1

        map_data = {}
        
        hrdf_days = duplicates_list_json['hrdf_duplicates_available_days']
        for (idx, hrdf_day) in enumerate(hrdf_days):
            hrdf_day_year = int(hrdf_day[0:4])
            if hrdf_day_year < last_year:
                continue
            
            duplicates_report_path: str = f'{self.duplicates_report_path_template}'
            duplicates_report_path = duplicates_report_path.replace('[HRDF_YMD]', hrdf_day)

            if not os.path.isfile(duplicates_report_path):
                # print(f'ERROR - skiping {duplicates_report_path} - not found')
                continue
            
            if idx % 10 == 0:
                log_message(f'Day {idx}/{len(hrdf_days)} => {hrdf_day}')
            
            duplicates_report = load_json_from_file(duplicates_report_path)
            for (agency_id, agency_data) in duplicates_report['agency_data'].items():
                if agency_id not in map_data:
                    map_data[agency_id] = {}

                if hrdf_day not in map_data[agency_id]:
                    map_data[agency_id][hrdf_day] = []

                for (fplan_trip_id, hrdf_trip_ids) in agency_data.items():
                    hrdf_trip_id = hrdf_trip_ids[0]
                    hrdf_trip = duplicates_report['map_hrdf_trips'][hrdf_trip_id]
                    vehicle_type = hrdf_trip['vehicle_type']
                    service_line = hrdf_trip['service_line']
                    vehicle_type_line = f'{vehicle_type}{service_line}'.strip()

                    report_row = {
                        'fplan_trip_id': fplan_trip_id,
                        'vehicle_type': vehicle_type_line,
                        'duplicates_no': len(hrdf_trip_ids)
                    }

                    map_data[agency_id][hrdf_day].append(report_row)
            # agency_data

        # loop hrdf_day

        filter_agency_ids = []
        
        self.compute_consolidated_report_for_agency(map_data, filter_agency_ids)

    def compute_consolidated_report_for_agency(self, map_data, agency_ids):
        csv_path = f'{self.consolidate_hrdf_duplicates_report_path_template}'

        agency_ids_s = ','.join(agency_ids)
        if len(agency_ids) == 0:
            agency_ids_s = 'ALL'

        csv_path = csv_path.replace('[AGENCY_ID]', agency_ids_s)

        column_names = ['day', 'agency_id', 'type', 'fplan_trip_id', 'duplicates_no']
        csv_updater = CSV_Updater(csv_path, column_names)

        row_idx = 0
        for agency_id, agency_data in map_data.items():
            if (len(agency_ids) > 0) and (agency_id not in agency_ids):
                continue

            for hrdf_day, duplicate_rows in agency_data.items():
                for duplicate_row in duplicate_rows:
                    csv_row_dict = {
                        'day': hrdf_day,
                        'agency_id': agency_id,
                        'type': duplicate_row['vehicle_type'],
                        'fplan_trip_id': duplicate_row['fplan_trip_id'],
                        'duplicates_no': duplicate_row['duplicates_no'],
                    }
                    csv_updater.prepare_row(csv_row_dict)
                    row_idx += 1
                # duplicates
            # hrdf_day
        # agency_id

        csv_updater.close()

        log_message(f'saved {row_idx} rows to {csv_path}')

    # TODO - extract me in a helper
    def fetch_report_duplicates_list(self):
        if os.path.isfile(self.duplicates_url_cache_path):
            file_ttl = 60
            file_ts = os.path.getmtime(self.duplicates_url_cache_path)
            
            now_ts = time.time()
            cache_age = now_ts - file_ts
            if cache_age < file_ttl:
                log_message(f'... load duplicates list JSON from {self.duplicates_url_cache_path}')
                data_json = load_json_from_file(self.duplicates_url_cache_path)
                return data_json

        log_message(f'... fetching duplicates list JSON from {self.duplicates_url}')

        url_request = urllib.request.Request(self.duplicates_url)
        response = urllib.request.urlopen(url_request).read()
        response_json = json.loads(response.decode('utf-8'))

        export_json_to_file(response_json, self.duplicates_url_cache_path, pretty_print=True)
        return response_json
