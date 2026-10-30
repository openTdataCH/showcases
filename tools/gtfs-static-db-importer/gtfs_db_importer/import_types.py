import datetime
from typing import Optional, TypedDict


class CalendarData(TypedDict):
    start_date: datetime.datetime
    end_date: datetime.datetime
    days_no: int

class StationTripsDayBitsRow(TypedDict):
    station_id: str
    day_bits: str
    trips_day_bits: Optional[str]

class StationIdRow(TypedDict):
    station_id: str

class StopMissingParentRow(TypedDict):
    stop_id: str
    parent_station: str

class StopParentDepthRow(TypedDict):
    stop_id: str
    parent_stop_id: str
    grandparent_stop_id: str

class StationCountRow(TypedDict):
    stations_count: int

class MissingTripMinutesCountRow(TypedDict):
    trips_count: int

class TripIdRow(TypedDict):
    trip_id: str

class TripRouteIdRow(TripIdRow):
    route_id: str

class CalendarExceptionGroupRow(TypedDict):
    service_id: str
    exception_dates: str

class ServiceIdRow(TypedDict):
    service_id: str

class CalendarDayBitsRow(TypedDict):
    day_bits: str

class AgencyValidationIssueRow(TypedDict):
    agency_id: str
    issue: str

