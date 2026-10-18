import sys
import sqlite3
from typing import List, Union

from .agency import Agency
from ..gtfs_static.calendar import Calendar as GTFS_Calendar
from ..gtfs_static.stop import Stop as GTFS_Stop
from ..gtfs_static.stop_time import Stop_Time as GTFS_Stop_Time
from ..gtfs_static.helpers import Helpers as GTFS_Helpers

class Trip_Variant:
    def __init__(self, fplan_row_idx, agency: Agency, service: GTFS_Calendar, vehicle_type, service_line, fplan_trip_id, fplan_content, from_stop: GTFS_Stop, to_stop: GTFS_Stop, stop_times: List[GTFS_Stop_Time]):
        self.fplan_row_idx = fplan_row_idx
        self.agency = agency
        self.service = service
        self.vehicle_type = vehicle_type
        self.service_line = service_line
        self.fplan_trip_id = fplan_trip_id
        self.fplan_content = fplan_content
        self.from_stop = from_stop
        self.to_stop = to_stop

        self.stop_times = stop_times

    def vehicle_type_key(self):
        key_parts = []
        
        key_parts.append(self.vehicle_type)
        key_parts.append(self.service_line or '')

        key = ''.join(key_parts)
        
        return key

    def from_stop_time(self) -> Union[GTFS_Stop_Time, None]:
        if len(self.stop_times) == 0:
            return None

        return self.stop_times[0]

    def to_stop_time(self) -> Union[GTFS_Stop_Time, None]:
        if len(self.stop_times) == 0:
            return None

        return self.stop_times[len(self.stop_times) - 1]

    def trip_departure_time(self) -> Union[str, None]:
        from_stop_time = self.from_stop_time()
        if from_stop_time is None:
            return None
        
        return from_stop_time.departure_time

    def trip_arrival_time(self) -> Union[str, None]:
        to_stop_time = self.to_stop_time()
        if to_stop_time is None:
            return None
        
        return to_stop_time.arrival_time

    def pretty_print(self):
        header_separator_s = '-' * 60
        print(f'{header_separator_s}')

        print(f'FPLAN row_idx       : {self.fplan_row_idx}')

        agency_id_s = self.agency.agency_id.ljust(10, ' ')
        print(f'agency              : {agency_id_s} {self.agency.long_name} - {self.agency.full_name_de}')

        print(f'FPLAN vehicle_type  : {self.vehicle_type}')
        print(f'FPLAN service_line  : {self.service_line}')
        print(f'FPLAN trip_id       : {self.fplan_trip_id}')
        print(f'FPLAN service_id    : {self.service.service_id}')
        
        from_stop_id_s = self.from_stop.stop_id.ljust(12, ' ')
        print(f'FPLAN from_stop     : {from_stop_id_s} - {self.from_stop.stop_name}')

        to_stop_id_s = self.to_stop.stop_id.ljust(12, ' ')
        print(f'FPLAN to_stop       : {to_stop_id_s} - {self.to_stop.stop_name}')

        print(f'{header_separator_s}')
        print(f'Stops: ')
        for stop_time in self.stop_times:
            stop_id_s = stop_time.stop.stop_id.ljust(12, ' ')
            stop_name_s = f'{stop_time.stop.stop_name} '.ljust(49, '·')
            stop_arr_s = GTFS_Helpers.format_stop_time(stop_time.arrival_time).ljust(5, ' ')
            stop_dep_s = GTFS_Helpers.format_stop_time(stop_time.departure_time)
            print(f'{stop_id_s} - {stop_name_s} {stop_arr_s} {stop_dep_s}')        

        print(f'{header_separator_s}')
        print('FPLAN content')
        print(f'{header_separator_s}')
        
        print(self.fplan_content)

    # This is meant to query custom fields
    def compute_property_rows(self, property_key: str):
        fplan_content = self.fplan_content
        rows = Trip_Variant.compute_property_rows_for_fplan_content(property_key=property_key, fplan_content=fplan_content)
        return rows

    @staticmethod
    def init_from_db_row(db_row: sqlite3.Row, map_calendar, map_agency, map_stops):
        row_idx = db_row['row_idx']
        vehicle_type = db_row['vehicle_type']
        service_line = db_row['service_line']
        fplan_trip_id = db_row['fplan_trip_id']
        fplan_content = db_row['fplan_content']

        service_id = db_row['service_id']
        service_db_row = map_calendar[service_id]
        gtfs_calendar = GTFS_Calendar.init_from_db_row(service_db_row)

        agency_id = db_row['agency_id']
        if agency_id not in map_agency:
            # TODO - this should be done in the HRDF importer step
            # check 87_TAC
            return None
        
        agency_db_row = map_agency[agency_id]
        gtfs_agency = Agency.init_from_db_row(agency_db_row)

        from_stop_id = db_row['from_stop_id']
        if from_stop_id not in map_stops:
            # TODO - this should be done in the HRDF importer step
            # check 8505558
            return None
        from_stop_db_row = map_stops[from_stop_id]
        from_stop = GTFS_Stop.init_from_db_row(from_stop_db_row)

        to_stop_id = db_row['to_stop_id']
        if to_stop_id not in map_stops:
            # TODO - this should be done in the HRDF importer step
            # check 8505558
            return None
        to_stop_db_row = map_stops[to_stop_id]
        to_stop = GTFS_Stop.init_from_db_row(to_stop_db_row)

        stop_times_s = db_row['stop_times_data']
        stop_times = GTFS_Helpers.parse_DB_row_stop_times(stop_times_s, map_stops)

        trip = Trip_Variant(row_idx, gtfs_agency, gtfs_calendar, vehicle_type, service_line, fplan_trip_id, fplan_content, from_stop, to_stop, stop_times)

        return trip

    def as_json(self):
        stops_data = []
        for stop_time in self.stop_times:
            stop_time_json = stop_time.as_json()
            stops_data.append(stop_time_json)

        trip_json = {
            'fplan_row_idx': self.fplan_row_idx,
            'agency_id': self.agency.agency_id,
            'vehicle_type': self.vehicle_type,
            'service_line': self.service_line,
            'fplan_trip_id': self.fplan_trip_id,
            'service_id': self.service.service_id,
            'from_stop_id': self.from_stop.stop_id,
            'to_stop_id': self.to_stop.stop_id,
            'stops': stops_data,
            'fplan_content': self.fplan_content
        }

        return trip_json

    @staticmethod
    def compute_property_rows_for_fplan_content(property_key: str, fplan_content: str):
        matched_rows = []
        fplan_content_rows = fplan_content.split("\n")
        
        for row_s in fplan_content_rows:
            if row_s.startswith(property_key):
                matched_rows.append(row_s)
        
        return matched_rows
