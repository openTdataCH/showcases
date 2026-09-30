import os, sys

import re
import argparse
from datetime import datetime, date, timedelta

from pathlib import Path

from typing import Any, List, Optional

from statistics import mean, median

from compare_gtfs_rt_static.helpers.config_helpers import load_yaml_config
from compare_gtfs_rt_static.helpers.json_helpers import load_json_from_file, export_json_to_file
from compare_gtfs_rt_static.helpers.log_helpers import log_message

from compare_gtfs_rt_static.models.gtfs_rt_static_report import GTFS_RT_Static_Report, GTFS_RT_Static_Monthly_Report, GTFS_RT_Static_Report_Compare_Info, GTFS_RT_Static_Report_Metadata
from compare_gtfs_rt_static.gtfs_controller import gtfs_rt_static_report_file_regexp, header_separator_s

is_verbose_mode = False

def _compute_compare(app_config: Any, report_key: str, map_hr_report: dict[str, GTFS_RT_Static_Report_Metadata], map_compare: dict[str, GTFS_RT_Static_Report_Compare_Info]):
    compare_info = GTFS_RT_Static_Report_Compare_Info(
        compare_type='h',
        mean_value=-1,
        drop_line=-1,
        map_days={},
    )
    
    report_ymd_f = report_key[0:10]
    report_hr_f = report_key[-2:]
    
    if report_ymd_f in app_config['map_holidays']:
        return compare_info
    
    report_ymd = date.fromisoformat(report_ymd_f)
    
    # Monday == 0 ... Sunday == 6
    report_weekday = report_ymd.weekday()
    report_hr = int(report_hr_f)
    # GTFS day starts at 4:00, everything earlier belongs to the previous day
    if report_hr < 4:
        report_weekday -= 1
        if report_weekday == -1:
            report_weekday = 6
            
    if report_weekday > 4:
        return compare_info
    
    compare_info.compare_type = 'w'
    
    prev_report_day = date.fromisoformat(report_ymd_f)
    days_back_idx = 0
    days_back_max = 100
    days_compare_max = 10
    while days_back_idx < days_back_max:
        prev_report_day -= timedelta(days=1)
        
        prev_report_day_f = f'{prev_report_day}'
        ignore_dropline_error = prev_report_day_f in app_config['map_days_ignore_dropline_error']
        
        prev_report_key = f'{prev_report_day_f}-{report_hr_f}'
        if prev_report_key in map_hr_report:
            prev_compare = map_compare.get(prev_report_key, None)
        
            include_dropline_computation = False
            if prev_compare is not None:
                if prev_compare.compare_type == 'w':
                    include_dropline_computation = True
                if (prev_compare.compare_type == 'w_p') and ignore_dropline_error:
                    include_dropline_computation = True
            # check if prev compare is working day
            
            if include_dropline_computation:
                prev_day_value = map_hr_report[prev_report_key].total_active_rows_no
                compare_info.map_days[f'{prev_report_day}'] = prev_day_value
            # if
        # check if we have report
        
        if len(compare_info.map_days.keys()) >= days_compare_max:
            break
            
        days_back_idx += 1
    # while days back
    
    is_relevant = (6 <= report_hr <= 20)
    has_prev_data = len(compare_info.map_days.keys()) == days_compare_max
    if has_prev_data and is_relevant:
        prev_values = compare_info.map_days.values()
        measure_mean = median(prev_values)
        drop_line = measure_mean * (1 - 0.05)
        
        report = map_hr_report[report_key]
        report_value = report.total_active_rows_no
        
        compare_info.drop_line = drop_line
        compare_info.mean_value = measure_mean
        
        if report_value < drop_line:
            compare_info.compare_type = 'w_p'
            
            if is_verbose_mode:
                print(f'possible issue:')
                print(f'  {report_ymd_f} {report_hr_f}:00')
                print(f'  rows      : {report_value}')
                print(f'  drop_line : {drop_line}')
                print()
                
                for prev_day, prev_day_no in  compare_info.map_days.items():
                    print(f'    {prev_day}: {prev_day_no}')
                    
                print()
            # verbose
        # if drop line was reached
            
    # check if we should analyse
    
    return compare_info

def _fetch_map_reports(app_config: Any, report_filter_ym: str) -> dict[str, GTFS_RT_Static_Report_Metadata]:
    report_template_path: str = app_config['resource_paths']['gtfs_rt_static_report']
    report_base_path = Path(report_template_path.split('[YEAR]/[MONTH]/[DAY]')[0])
    
    report_filter_months: Optional[List[str]] = None
    if report_filter_ym != 'ALL':
        report_filter_ym_parts = report_filter_ym.split('-')
        dir_y_s = report_filter_ym_parts[0]
        dir_m_s = report_filter_ym_parts[1]
        dir_ym = f'{dir_y_s}-{dir_m_s}'
        
        prev_dir_y = int(dir_y_s)
        prev_dir_m = int(dir_m_s) - 1
        if prev_dir_m == 0:
            prev_dir_y -= 1
            prev_dir_m = 12
        prev_dir_y_s = f'{prev_dir_y}'.zfill(2)
        prev_dir_m_s = f'{prev_dir_m}'.zfill(2)
        prev_dir_ym = f'{prev_dir_y_s}-{prev_dir_m_s}'
        
        report_filter_months = [prev_dir_ym, dir_ym]
    # end build yyyy-mm filter
    
    report_subdirs: List[Path] = []
    for report_subdir in report_base_path.glob('*/*'):
        if not report_subdir.is_dir():
            continue
        
        if report_filter_months is not None:
            report_subdir_paths = f'{report_subdir}'.split('/')
            report_subdir_ym = f'{report_subdir_paths[-2]}-{report_subdir_paths[-1]}'
            if report_subdir_ym not in report_filter_months:
                continue
        # check if filter YYYY-MM is active and matches subdir
        
        report_subdirs.append(report_subdir)
    # loop subdirs
    report_subdirs.sort()
    
    report_file_paths: List[Path] = []
    for report_subdir in report_subdirs:
        report_subdir_paths = f'{report_subdir}'.split('/')
        report_year_f = report_subdir_paths[-2]
        report_month_f = report_subdir_paths[-1]
        report_month_path = Path(f'{report_base_path}/{report_year_f}/{report_month_f}')
        for gtfs_rt_report_path in report_month_path.rglob('*.json'):
            report_file_paths.append(gtfs_rt_report_path)
        # loop subdir JSON files
    # loop subdirs
    report_file_paths.sort()
    log_message(f'... found {len(report_file_paths)} files')
    
    map_reports: dict[str, GTFS_RT_Static_Report_Metadata] = {}
    for report_path in report_file_paths:
        file_matches = re.match(gtfs_rt_static_report_file_regexp, report_path.name)
        if file_matches is None:
            print('ERROR - unknown file pattern')
            print(report_path)
            sys.exit(1)
        
        report_json = load_json_from_file(report_path)
        report = GTFS_RT_Static_Report.from_json(report_json)
        
        report_year_f = file_matches[1]
        report_month_f = file_matches[2]
        report_day_f = file_matches[3]
        report_hour_f = file_matches[4]
        report_min_f = file_matches[5]
        
        # Discard reports that are not run on cronjob basis (every hour)
        if report_min_f != '00':
            continue
        
        report_key = f'{report_year_f}-{report_month_f}-{report_day_f}-{report_hour_f}'
        
        map_reports[report_key] = report.metadata
    # loop report_file_paths
    
    return map_reports

def _compute_and_save_monthly_report(app_config: Any, report_filter_ym: str, map_reports: dict[str, GTFS_RT_Static_Report_Metadata], map_compare: dict[str, GTFS_RT_Static_Report_Compare_Info]): 
    #                   YYYY-MM  >    DD    >   HH > GTFS_RT_Static_Report_Metadata
    map_reports_by_hr: dict[str, dict[str, dict[str, GTFS_RT_Static_Report_Metadata]]] = {}
    map_compare_by_hr: dict[str, dict[str, dict[str, GTFS_RT_Static_Report_Compare_Info]]] = {}
    for report_key, report in map_reports.items():
        # 2025-07-01-00
        report_key_parts = report_key.split('-')
        report_ym = '-'.join(report_key_parts[0:2])
        report_day_f = report_key_parts[2]
        report_hour_f = f'{report_key_parts[3]}00'
        
        if report_filter_ym != 'ALL':
            if report_ym != report_filter_ym:
                continue
        
        if report_ym not in map_reports_by_hr:
            map_reports_by_hr[report_ym] = {}
            map_compare_by_hr[report_ym] = {}
        
        if report_day_f not in map_reports_by_hr[report_ym]:
            map_reports_by_hr[report_ym][report_day_f] = {}
            map_compare_by_hr[report_ym][report_day_f] = {}
            
        map_reports_by_hr[report_ym][report_day_f][report_hour_f] = report
        if report_key in map_compare:
            map_compare_by_hr[report_ym][report_day_f][report_hour_f] = map_compare[report_key]
    # loop reports
    
    report_now = datetime.now()
    report_now_f = report_now.strftime('%Y-%m-%d %H:%M:%S')
    report_comments = f'generated {report_now_f} with {Path(__file__).name}'
    
    for report_ym, report_data in map_reports_by_hr.items():
        report_year_f, _, report_month_f = report_ym.partition('-')
        report_compare_data = map_compare_by_hr[report_ym]
        
        monthly_report = GTFS_RT_Static_Monthly_Report(
            last_update_dt=report_now_f,
            comments=report_comments,
            report_days=report_data,
            compare_days=report_compare_data,
        )
        monthly_report_json = monthly_report.as_json()
        
        monthly_report_path_s: str = app_config['resource_paths']['gtfs_rt_static_mo_json']
        monthly_report_path_s = monthly_report_path_s.replace('[YEAR]', report_year_f)
        monthly_report_path_s = monthly_report_path_s.replace('[MONTH]', report_month_f)
        monthly_report_path = Path(monthly_report_path_s)
        
        export_json_to_file(monthly_report_json, json_path=monthly_report_path, pretty_print=True)
        log_message(f'... saved {report_ym} to {monthly_report_path.name}')
    # loop months

def _analyse_last_report(map_reports: dict[str, GTFS_RT_Static_Report_Metadata], map_compare: dict[str, GTFS_RT_Static_Report_Compare_Info]):
    report_now = datetime.now()
    report_now_f = report_now.strftime('%Y-%m-%d-%H')
    
    # ignore outside of normal hours
    report_hr = int(report_now_f[-2:])
    if (report_hr < 6) or (report_hr > 18):
        return
    
    # compare report is not available, dont throw an error
    if report_now_f not in map_compare:
        return
    
    report_compare = map_compare[report_now_f]
    
    # ignore holidays
    if report_compare.compare_type == 'h':
        return
    
    error_message = None
    
    if report_now_f not in map_reports:
        error_message = f'ERROR - cant find {report_now_f} report, is GTFS-RT endpoint working?'
        
    if error_message is not None:
        raise Exception(error_message)
    
    report = map_reports[report_now_f]
    
    if report_compare.compare_type == 'w_p':
        error_message = f'ERROR - DROP detected in number of GTFS-RT items'

    # temp turn off notifications until a proper fix for cases when we have tripUpdate for trips from next day(s)
    #   - check the TripUpdate.startDate if is different than today
    #   - if yes, compare against that day (not current day)
    # if report.tripNOK_NOJP_no > 0:
    #     error_message = f'ERROR - GTFS-RT / -static is out of sync, discovered {report.tripNOK_NOJP_no} items not in GTFS-static'
        
    if abs(report.gtfs_rt_age) > 60:
        error_message = f'ERROR - GTFS-RT age is greater than 60 seconds: {report.gtfs_rt_age}'
                
    if error_message is not None:
        raise Exception(error_message)

def main():
    app_path = Path(os.path.realpath(__file__)).parent
    config_path = Path(f'{app_path}/config/config.yml')
    app_config = load_yaml_config(config_path, app_path)
    
    report_now = datetime.now()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--month', '--month')
    parser.add_argument('--check-errors', '--check-errors', action='store_true')
    
    args = parser.parse_args()
    user_report_filter_ym = args.month
    user_check_errors = args.check_errors

    report_filter_ym = user_report_filter_ym
    if report_filter_ym is None:
        default_filter_ym = report_now.strftime('%Y-%m')
        report_filter_ym = default_filter_ym
    
    print(header_separator_s)
    log_message(f'START cli_aggregate_monthly_reports_json with --month={report_filter_ym}')
    print(header_separator_s)
    
    map_reports = _fetch_map_reports(app_config, report_filter_ym)
    log_message(f'... done parsing {len(map_reports.keys())} reports')
    
    map_compare: dict[str, GTFS_RT_Static_Report_Compare_Info] = {}
    for report_key, _ in map_reports.items():
        report_compare = _compute_compare(app_config, report_key, map_reports, map_compare)
        map_compare[report_key] = report_compare
    # loop compare
    log_message('... finished compare files')
    
    _compute_and_save_monthly_report(app_config, report_filter_ym, map_reports, map_compare)
    
    log_message('... DONE')
    print(header_separator_s)
    
    if user_check_errors:
        _analyse_last_report(map_reports, map_compare)

if __name__ == "__main__":
    main()
