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

class MissingTripMinutesCountRow(TypedDict):
    trips_count: int

class TripIdRow(TypedDict):
    trip_id: str
