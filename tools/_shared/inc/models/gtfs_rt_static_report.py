import os, sys

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, TypedDict

@dataclass
class GTFS_RT_Static_Report_Compare_Info:
    compare_type: str # h - holiday; w - workday; w_p - workday with problems;
    map_days: dict[str, int]
    mean_value: float
    drop_line: float
    
    @staticmethod
    def from_json(data_json):
        compare_info = GTFS_RT_Static_Report_Compare_Info(**data_json)
        return compare_info

class GTFS_TripsActiveData(TypedDict):
    gtfs_day: str
    trips_active_no: int
    trips_active_by_agency: dict[str, int]

@dataclass
class GTFS_RT_Static_Report_Metadata:
    report_dt: datetime
    gtfs_db_filename: str
    gtfs_db_age: float
    gtfs_rt_filename: str
    gtfs_rt_ts: int
    gtfs_rt_dt: datetime
    gtfs_rt_age: int
    
    total_rows_no: int
    total_active_rows_no: int
    # Trip/Route matched with GTFS
    tripOK_routeOK_no: int
    
    # Count Issues
    # Trip matched / Route not matched against GTFS         - should be 0 items
    tripOK_routeNOK_no: int
    # Trip NOT matched / Route matched against GTFS         - usually with tripId starts with ojp:
    tripNOK_routeOK_no: int
    # Trip NOT matched / Route NOT matched against GTFS     - usually with tripId, routeId starts with ojp:
    tripNOK_routeNOK_no: int
    # Trip NOT matched, TripId DOESNT start with ojp:       - should be 0 items
    tripNOK_NOJP_no: int
    
    @staticmethod
    def from_json(data_json: dict[str, Any]):
        if data_json.get('total_active_rows_no') is None:
            data_json['total_active_rows_no'] = -1
        
        metadata = GTFS_RT_Static_Report_Metadata(**data_json)
        metadata.report_dt = datetime.strptime(data_json['report_dt'], '%Y-%m-%d %H:%M:%S')
        metadata.gtfs_rt_dt = datetime.strptime(data_json['gtfs_rt_dt'], '%Y-%m-%d %H:%M:%S')
        
        return metadata
    
    def as_json(self):
        data_json = asdict(self)
        for metadata_key in ['report_dt', 'gtfs_rt_dt']:
            metadata_dt: datetime = data_json[metadata_key]
            data_json[metadata_key] = metadata_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return data_json

@dataclass
class GTFS_RT_Static_Report:
    metadata: GTFS_RT_Static_Report_Metadata
    
    tripOK_routeNOK: list[str]
    tripNOK_routeOK: list[str]
    tripNOK_routeNOK: list[str]

    gtfs_rt_by_agency: dict[str, int]
    gtfs_rt_active_by_agency: dict[str, int]
    gtfs_trips_active_data: GTFS_TripsActiveData
    
    @staticmethod
    def init_with_metadata(metdata: GTFS_RT_Static_Report_Metadata, gtfs_rt_by_agency: dict[str, int], gtfs_rt_active_by_agency: dict[str, int], gtfs_trips_active_data: GTFS_TripsActiveData):
        report = GTFS_RT_Static_Report(metdata, [], [], [], gtfs_rt_by_agency=gtfs_rt_by_agency, gtfs_trips_active_data=gtfs_trips_active_data, gtfs_rt_active_by_agency=gtfs_rt_active_by_agency)
        return report
    
    @staticmethod
    def from_json(report_json: dict[str, Any]):
        report = GTFS_RT_Static_Report(**report_json)
        
        report.metadata = GTFS_RT_Static_Report_Metadata.from_json(report_json['metadata'])
        
        entity_group_keys = ['tripOK_routeNOK', 'tripNOK_routeOK', 'tripNOK_routeNOK']
        for entity_group_key in entity_group_keys:
            entity_ids = []
            for entity_id in report_json[entity_group_key]:
                entity_ids.append(entity_id)
            
            setattr(report, entity_group_key, entity_ids)
        # entity_group_keys
        
        return report
    
    def as_json(self):
        data_json = asdict(self)
        data_json['metadata'] = self.metadata.as_json()
        
        return data_json
    
@dataclass
class GTFS_RT_Static_Monthly_Report:
    comments: str
    last_update_dt: str
    report_days: dict[str, dict[str, GTFS_RT_Static_Report_Metadata]]
    compare_days: dict[str, dict[str, GTFS_RT_Static_Report_Compare_Info]]
    gtfs_rt_by_agency: dict[str, dict[str, dict[str, int]]]
    gtfs_rt_active_by_agency: dict[str, dict[str, dict[str, int]]]
    trips_active_by_agency: dict[str, dict[str, dict[str, int]]]
    
    def as_json(self):
        data_json = asdict(self)
        
        for report_day, day_data in self.report_days.items():
            for report_hr, hr_data_o in day_data.items():
                hr_data: GTFS_RT_Static_Report_Metadata = hr_data_o
                data_json['report_days'][report_day][report_hr] = hr_data.as_json()
        # for
        
        return data_json
