import os, sys

from pathlib import Path

from typing import TypedDict, Union

from datetime import datetime, date

import gzip
import shutil

from .helpers.config_helpers import load_yaml_config
from .helpers.gtfs_helpers import compute_gtfs_db_filename
from .helpers.json_helpers import load_json_from_file, export_json_to_file
from .helpers.log_helpers import format_path, log_message
from .gtfs_db import GTFS_DB, DayTripData

from .models.gtfs_static_db_catalog import GTFS_Static_Catalog_Report, GTFS_Static_Catalog_Item
from .models.gtfs_rt import GTFS_RT_Response
from .models.gtfs_rt_static_report import GTFS_RT_Static_Report, GTFS_RT_Static_Report_Metadata, GTFS_TripsActiveData

from .fetch import fetch_latest, compute_resource_snapshot_path

gtfs_rt_static_report_file_regexp = r"gtfs_rt_static_report-([0-9]{4})-([0-9]{2})-([0-9]{2})-([0-9]{2})([0-9]{2})"
header_separator_s = '-' * 60

class GTFS_ActiveTripsData(TypedDict):
    trips_no: int
    map_trip_ids: dict[str, bool]
    map_by_agency: dict[str, int]

class GTFS_Controller:
    gtfs_dbs_report: GTFS_Static_Catalog_Report

    def __init__(self, app_path: Path):
        config_path = Path(f'{app_path}/config/config.yml')
        self.app_config = load_yaml_config(config_path, app_path=app_path)
        
        gtfs_dbs_report_path = self.app_config['resource_paths']['gtfs_dbs_json_path']
        gtfs_dbs_report_json = load_json_from_file(gtfs_dbs_report_path)
        self.gtfs_dbs_report = GTFS_Static_Catalog_Report.from_json(gtfs_dbs_report_json)
        
    def compare_latest_gtfs_rt_static(self):
        self._compare_compare_latest_gtfs_rt_static()
        
    def load_gtfs_db(self, gtfs_catalog_item: GTFS_Static_Catalog_Item):
        return self._load_gtfs_db(gtfs_catalog_item)
    
    def compare_gtfs_rt_from_file(self, gtfs_rt_response: GTFS_RT_Response, gtfs_rt_file_dt: datetime, gtfs_rt_path: Path, gtfs_catalog_item: GTFS_Static_Catalog_Item, map_day_data_trips: dict[str, DayTripData]):
        self._compare_gtfs_rt_from_file(gtfs_rt_response, gtfs_rt_file_dt, gtfs_rt_path, gtfs_catalog_item, map_day_data_trips)
        
    def compute_gtfs_db_dt(self, dt: datetime):
        return self._compute_gtfs_db_catalog_item(dt)
    
    def fetch_latest_gtfs_rt(self):
        self._fetch_latest_gtfs_rt()
        
    # PRIVATE
    def _compare_compare_latest_gtfs_rt_static(self):
        app_path: str = self.app_config['resource_paths']['app_path']
        
        print(header_separator_s)
        log_message(f'START COMPARE GTFS -RT GTFS STATIC')
        print(header_separator_s)
        
        fetch_dt = datetime.now()
        
        log_message(f'... START fetch GTFS-RT')
        log_message(f'... TS REQUEST    : {fetch_dt}')
        
        resource_path = self.app_config['resource_paths']['gtfs_rt_snapshot']
        gtfs_rt_snapshot_path = compute_resource_snapshot_path(resource_path, fetch_dt)
        
        gtfs_rt_response = fetch_latest(self.app_config, gtfs_rt_snapshot_path)
        log_message(f'... DONE fetch')
        gtfs_rt_snapshot_path_s = format_path(f'{gtfs_rt_snapshot_path}', app_path)
        print(f'saved to {gtfs_rt_snapshot_path_s}')
        print(header_separator_s)
        
        gtfs_catalog_item = self.gtfs_dbs_report.lookup_by_feed_verson(gtfs_rt_response.header.feedVersion)
        if gtfs_catalog_item is None:
            raise ValueError(
                f"Cannot find a GTFS-static database catalog item for "
                f"GTFS-RT feedVersion {gtfs_rt_response.header.feedVersion!r}"
            )
            
        log_message(f'... LOAD DB GTFS-DAY: {gtfs_catalog_item.gtfs_day} - {gtfs_catalog_item.db_relative_path}')
            
        gtfs_db = self._load_gtfs_db(gtfs_catalog_item)
        
        log_message(f'... DONE LOAD DB')
        print(header_separator_s)

        map_day_data_trips = self.compute_day_data_by_start_date(gtfs_db, gtfs_rt_response, fetch_dt.date())
        
        report = self._compare_file_gtfs_rt_static(
            fetch_dt,  
            gtfs_rt_snapshot_path, gtfs_rt_response, 
            gtfs_catalog_item, 
            map_day_data_trips,
        )
        
        print()
        print(header_separator_s)
        log_message('GTFS-RT <-> GTFS-STATIC Report')
        print(header_separator_s)
        print(f'GTFS-RT age         : {report.metadata.gtfs_rt_age} seconds')
        print(f'GTFS-static DB age  : {report.metadata.gtfs_db_age} days')
        print()
        print(f'rows no             : {report.metadata.total_rows_no}')
        print(f'rows active no      : {report.metadata.total_active_rows_no}')
        print(f'trips OK            : {report.metadata.tripOK_routeOK_no}')
        print()
        print(f'tripOK_routeNOK_no  : {report.metadata.tripOK_routeNOK_no}')
        print(f'tripNOK_routeOK_no  : {report.metadata.tripNOK_routeOK_no}')
        print(f'tripNOK_routeNOK_no : {report.metadata.tripNOK_routeNOK_no}')
        print(f'tripNOK_NOJP_no     : {report.metadata.tripNOK_NOJP_no}')
        print()
        
        report_path = self.app_config['resource_paths']['gtfs_rt_static_report']
        report_path = compute_resource_snapshot_path(report_path, fetch_dt)
        
        dt_year = fetch_dt.strftime('%Y')
        dt_month = fetch_dt.strftime('%m')
        dt_day = fetch_dt.strftime('%d')
        report_url = f'https://tools.opentransportdata.swiss/atlas-route-compare-gtfs/gtfs-rt-static-compare-report/{dt_year}/{dt_month}/{dt_day}/{report_path.name}';
        print(f'Report URL          : {report_url}')
        print(header_separator_s)
        
        log_message('... cleaning up, archive(gzip) resource')
        self._cleanup_resource(gtfs_rt_snapshot_path)
        
        log_message('... DONE')
        print(header_separator_s)
        print()
        
    def _load_gtfs_db(self, gtfs_catalog_item: GTFS_Static_Catalog_Item):
        gtfs_dbs_basepath = Path(self.app_config['resource_paths']['gtfs_db']).parent
        gtfs_db_path = Path(f'{gtfs_dbs_basepath}/{gtfs_catalog_item.db_relative_path}')
            
        if not os.path.isfile(gtfs_db_path):
            raise FileNotFoundError(
                f'Cannot find GTFS-static database at {gtfs_db_path}'
            )
        
        gtfs_db = GTFS_DB(db_path=gtfs_db_path, map_resource_paths=self.app_config['resource_paths'])
        gtfs_db.init_lookups()

        return gtfs_db
    
    def _compare_gtfs_rt_from_file(self, gtfs_rt_response: GTFS_RT_Response, gtfs_rt_file_dt: datetime, gtfs_rt_path: Path, gtfs_catalog_item: GTFS_Static_Catalog_Item, map_day_data_trips: dict[str, DayTripData]):
        self._compare_file_gtfs_rt_static(
            gtfs_rt_file_dt, gtfs_rt_path, gtfs_rt_response,
            gtfs_catalog_item,
            map_day_data_trips,
        )

    @staticmethod
    def parse_trip_start_date(start_date: str) -> date:
        try:
            return datetime.strptime(start_date, '%Y%m%d').date()
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid GTFS-RT trip startDate {start_date!r}; expected YYYYMMDD"
            ) from error

    def compute_day_data_by_start_date(self, gtfs_db: GTFS_DB, gtfs_rt_response: GTFS_RT_Response, fallback_date: date) -> dict[str, DayTripData]:
        start_dates = {fallback_date}
        for entity in gtfs_rt_response.entity:
            start_dates.add(self.parse_trip_start_date(entity.tripUpdate.trip.startDate))

        day_data_by_start_date: dict[str, DayTripData] = {}
        for start_date in start_dates:
            start_date_key = start_date.isoformat()
            day_data = gtfs_db.compute_day_data(start_date)
            day_data_by_start_date[start_date_key] = day_data

        return day_data_by_start_date
        
    def _compute_gtfs_db_catalog_item(self, dt: datetime) -> Union[GTFS_Static_Catalog_Item, None]:
        found_gtfs_db_item: Union[GTFS_Static_Catalog_Item, None] = None
        for gtfs_db_item in self.gtfs_dbs_report.items:
            # because the GTFS-RT is switch later, we need to use the switch time
            gtfs_rt_switch_dt = datetime.strptime(gtfs_db_item.gtfs_rt_switch_datetime_s, '%Y-%m-%d %H:%M')
            
            # the request is for an older DB, ignore the DBs in the future
            if gtfs_rt_switch_dt.timestamp() > dt.timestamp():
                continue
            
            # ignore DBs that are not on disk
            if gtfs_db_item.db_relative_path is None:
                continue
            
            found_gtfs_db_item = gtfs_db_item
            break # on first item
        # loop GTFS DB catalog items
        
        return found_gtfs_db_item
    
    def _compute_gtfs_active_trips_data(self, day_data_trips: DayTripData, for_dt: datetime) -> GTFS_ActiveTripsData:
        for_dt_minutes = for_dt.hour * 60 + for_dt.minute
        if for_dt.hour < 4:
            for_dt_minutes += 24 * 60

        gtfs_active_trips_data: GTFS_ActiveTripsData = {
            'trips_no': 0,
            'map_trip_ids': {},
            'map_by_agency': {},
        }

        for trip_id, trip_data in day_data_trips['map_trips'].items():
            # trip ended in the past
            if trip_data['arr_mins'] < for_dt_minutes:
                continue
            # trip starts in the future
            if trip_data['dep_mins'] > for_dt_minutes:
                continue
            
            gtfs_active_trips_data['trips_no'] += 1
            gtfs_active_trips_data['map_trip_ids'][trip_id] = True

            route_id = trip_data['route_id']
            agency_id = day_data_trips['map_route_agency'][route_id] or None
            if agency_id is None:
                raise ValueError(f'cant find agency for trip_id:{trip_id} + route_id:{route_id}')
            
            if agency_id not in gtfs_active_trips_data['map_by_agency']:
                gtfs_active_trips_data['map_by_agency'][agency_id] = 0
            gtfs_active_trips_data['map_by_agency'][agency_id] += 1
        # loop trips
        
        return gtfs_active_trips_data
    
    def _compare_file_gtfs_rt_static(self, 
            report_dt: datetime, gtfs_rt_path: Path, gtfs_rt_response: GTFS_RT_Response, 
            gtfs_catalog_item: GTFS_Static_Catalog_Item,
            map_day_data_trips: dict[str, DayTripData],
        ):
        gtfs_rt_dt = datetime.fromtimestamp(gtfs_rt_response.header.timestamp)

        report_day_key = report_dt.date().isoformat()
        report_day_data_trips = map_day_data_trips[report_day_key]
        gtfs_active_trips_data = self._compute_gtfs_active_trips_data(report_day_data_trips, for_dt=report_dt)
        
        gtfs_static_day = gtfs_catalog_item.gtfs_day
        gtfs_rt_age = round(gtfs_rt_dt.timestamp() - report_dt.timestamp())
        
        gtfs_db_dt = datetime.strptime(gtfs_catalog_item.gtfs_datetime_s, '%Y-%m-%d %H:%M')
        gtfs_db_age = round((gtfs_rt_dt.timestamp() - gtfs_db_dt.timestamp()) / (3600 * 24), 2)

        report_gtfs_active_trips_data: GTFS_TripsActiveData = {
            'gtfs_day': gtfs_catalog_item.gtfs_day,
            'trips_active_no': gtfs_active_trips_data['trips_no'],
            'trips_active_by_agency': gtfs_active_trips_data['map_by_agency'],
        }

        report_metdata = GTFS_RT_Static_Report_Metadata(
            report_dt=report_dt,
            gtfs_db_filename=compute_gtfs_db_filename(gtfs_static_day),
            gtfs_db_age=gtfs_db_age,
            
            gtfs_rt_filename=gtfs_rt_path.name,
            gtfs_rt_ts=round(gtfs_rt_dt.timestamp()),
            gtfs_rt_dt=gtfs_rt_dt,
            gtfs_rt_age=gtfs_rt_age,
    
            total_rows_no=0,
            total_active_rows_no=0,
            
            tripOK_routeOK_no=0,
            tripOK_routeNOK_no=0,
            tripNOK_routeOK_no=0,
            tripNOK_routeNOK_no=0,
            tripNOK_NOJP_no=0,
        )

        report_stats = GTFS_RT_Static_Report.init_with_metadata(
            report_metdata, 
            gtfs_rt_by_agency={},
            gtfs_rt_active_by_agency={},
            gtfs_trips_active_data=report_gtfs_active_trips_data
        )
        
        for entity in gtfs_rt_response.entity:
            report_stats.metadata.total_rows_no += 1
            
            trip_id = entity.tripUpdate.trip.tripId
            route_id = entity.tripUpdate.trip.routeId

            trip_start_date = self.parse_trip_start_date(
                entity.tripUpdate.trip.startDate,
            )
            day_data_trips = map_day_data_trips[trip_start_date.isoformat()]
            
            # is the trip in the GTFS day trips?
            trip_OK = trip_id in day_data_trips['map_trips']
            
            # is the route present in actual GTFS?
            route_OK = route_id in day_data_trips['map_route_agency']

            agency_id = 'n_a'
            if route_OK:
                agency_id = day_data_trips['map_route_agency'][route_id]

            if agency_id not in report_stats.gtfs_rt_by_agency:
                report_stats.gtfs_rt_by_agency[agency_id] = 0
            report_stats.gtfs_rt_by_agency[agency_id] += 1

            is_trip_active = trip_id in gtfs_active_trips_data['map_trip_ids']
            if is_trip_active:
                report_stats.metadata.total_active_rows_no += 1

                if agency_id not in report_stats.gtfs_rt_active_by_agency:
                    report_stats.gtfs_rt_active_by_agency[agency_id] = 0
                report_stats.gtfs_rt_active_by_agency[agency_id] += 1
            # endif is_trip_active
            
            if trip_OK and route_OK:
                report_stats.metadata.tripOK_routeOK_no += 1
                
            if trip_OK and not route_OK:
                report_stats.tripOK_routeNOK.append(entity.id)
                report_stats.metadata.tripOK_routeNOK_no += 1
                
            if not trip_OK and route_OK:
                report_stats.tripNOK_routeOK.append(entity.id)
                report_stats.metadata.tripNOK_routeOK_no += 1
                
            if not trip_OK and not route_OK:
                report_stats.tripNOK_routeNOK.append(entity.id)
                report_stats.metadata.tripNOK_routeNOK_no += 1
            
            # match tripId that DOESNT start with 'ojp:' 'atv:'
            special_trip_id_matches = trip_id.startswith('ojp') or trip_id.startswith('atv')
            if not trip_OK and not special_trip_id_matches:
                report_stats.metadata.tripNOK_NOJP_no += 1
        # loop entity

        report_path = self.app_config['resource_paths']['gtfs_rt_static_report']
        report_path = compute_resource_snapshot_path(report_path, report_dt)
        report_json = report_stats.as_json()
        export_json_to_file(report_json, report_path, pretty_print=True)

        return report_stats
    # _compare_file_gtfs_rt_static
    
    # keep a GZIP version of the snapshot
    def _cleanup_resource(self, resource_path):
        gzip_path = f'{resource_path}.gz'
        
        with open(resource_path, 'rb') as f_in:
            with gzip.open(gzip_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        # with
        
        os.remove(resource_path)
        
    def _fetch_latest_gtfs_rt(self):
        print(header_separator_s)
        log_message(f'START FETCH LATEST GTFS-RT')
        print(header_separator_s)
        
        fetch_dt = datetime.now()
        
        log_message(f'... START fetch GTFS-RT')
        log_message(f'... TS REQUEST    : {fetch_dt}')
        
        resource_path = self.app_config['resource_paths']['gtfs_rt_snapshot']
        gtfs_rt_snapshot_path = compute_resource_snapshot_path(resource_path, fetch_dt)
        
        fetch_latest(self.app_config, gtfs_rt_snapshot_path)
        log_message(f'... DONE fetch')
        
        app_path = self.app_config['resource_paths']['app_path']
        
        print()
        gtfs_rt_snapshot_path_s = format_path(f'{gtfs_rt_snapshot_path}', app_path)
        print(f'... saved to {gtfs_rt_snapshot_path_s}')
        print(header_separator_s)
