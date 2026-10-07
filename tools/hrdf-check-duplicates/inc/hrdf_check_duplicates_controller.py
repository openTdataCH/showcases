import os, sys
import sqlite3

from typing import List, Optional, TypedDict

from pathlib import Path

from .shared.inc.models.gtfs_static.calendar import Calendar as GTFS_Calendar
from .shared.inc.models.hrdf.trip_variant import Trip_Variant as HRDF_Trip_Variant

from .shared.inc.helpers.bundle_helpers import load_resource_from_bundle
from .shared.inc.helpers.db_helpers import table_select_rows
from .shared.inc.helpers.log_helpers import log_message
from .shared.inc.helpers.json_helpers import export_json_to_file
from .shared.inc.helpers.hrdf_helpers import compute_formatted_date_from_hrdf_db_path

type MapFplanDbRow = dict[str, List[FplanDbRow]]

class FplanDbRow(TypedDict):
    fplan_row_idx: int
    agency_id: str
    vehicle_type: str
    service_line: str
    fplan_trip_id: str
    fplan_content: str
    service_id: str

class CalendarDbRow(TypedDict):
    service_id: str
    start_date: str
    end_date: str
    day_bits: str

class HRDF_Check_Duplicates_Controller:
    def __init__(self, app_config, hrdf_db_path: Path):
        log_message('HRDF_Check_Duplicates_Controller - START INIT')

        self.hrdf_db_path = hrdf_db_path
        self.hrdf_db = sqlite3.connect(str(hrdf_db_path))
        self.hrdf_db.row_factory = sqlite3.Row

        self.hrdf_db_lookups = self._compute_lookups(self.hrdf_db)

        self.map_sql_queries = app_config['map_sql_queries']

        self.report_paths = app_config['report_paths']

        log_message('HRDF_Check_Duplicates_Controller - DONE INIT')

    def check(self):
        print(f'=================================')
        print(f'HRDF check duplicates')
        print(f'=================================')
        print(f'HRDF DB PATH: {self.hrdf_db_path}')
        print(f'=================================')
        print('')

        file_ymd = compute_formatted_date_from_hrdf_db_path(self.hrdf_db_path)
        if file_ymd is None:
            raise ValueError(f'ERROR - cant read ymd from {self.hrdf_db_path.name}')

        map_hrdf_duplicates_agency_errors_path: str = self.report_paths['hrdf_duplicates_report_path']
        map_hrdf_duplicates_agency_errors_path = map_hrdf_duplicates_agency_errors_path.replace('[HRDF_YMD]', file_ymd)

        map_hrdf_duplicates_agency_errors = self._check()

        export_json_to_file(map_hrdf_duplicates_agency_errors, Path(map_hrdf_duplicates_agency_errors_path), pretty_print=True)
        log_message(f'Saved report to {map_hrdf_duplicates_agency_errors_path}')

        log_message(f'DONE')

    def _compute_lookups(self, db_handle):
        map_db_lookups = {}

        table_names = ['agency', 'calendar', 'stops']
        map_table_keys = {
            'agency': 'agency_id',
            'calendar': 'service_id',
            'stops': 'stop_id',
        }
        for table_name in table_names:
            pk_field = map_table_keys[table_name]
            map_db_lookups[table_name] = table_select_rows(db_handle, table_name, group_by_key=pk_field)

        return map_db_lookups

    def _check(self):
        map_hrdf_duplicates_errors = {
            'agency_data': {},
            'service_data': {},
            'map_hrdf_trips': {}
        }

        agency_ids = self._fetch_agency_ids()
        for agency_row_idx, agency_id in enumerate(agency_ids):
            if agency_row_idx % 100 == 0:
                log_message(f"... parsed {agency_row_idx}/{len(agency_ids)} agencies ...")

            map_duplicate_trips = self._compute_duplicate_trips_for_agency(agency_id)
            if map_duplicate_trips == {}:
                continue

            agency_data = {}
            
            for duplicate_key, hrdf_db_trips in map_duplicate_trips.items():
                hrdf_lookup_keys = []
                for hrdf_db_trip in hrdf_db_trips:
                    service_id = hrdf_db_trip['service_id']

                    # include also service_id (for *A VE cases)
                    fplan_row_idx = hrdf_db_trip['fplan_row_idx']
                    hrdf_lookup_key = f'{fplan_row_idx}.{service_id}'
                    hrdf_lookup_keys.append(hrdf_lookup_key)

                    map_hrdf_duplicates_errors['map_hrdf_trips'][hrdf_lookup_key] = dict(hrdf_db_trip)

                    if service_id not in map_hrdf_duplicates_errors['service_data']:
                        calendar_db_row: sqlite3.Row = self.hrdf_db_lookups['calendar'][service_id]
                        calendar_db = GTFS_Calendar.init_from_db_row(calendar_db_row)
                        map_hrdf_duplicates_errors['service_data'][service_id] = calendar_db.pretty_print()
                # loop trips

                agency_data[duplicate_key] = hrdf_lookup_keys
            # duplicate groups

            map_hrdf_duplicates_errors['agency_data'][agency_id] = agency_data
        # loop agency

        return map_hrdf_duplicates_errors

    def _fetch_agency_ids(self):
        agency_ids = []

        sql = 'SELECT agency_id FROM agency WHERE in_fplan = 1;'
        db_cursor = self.hrdf_db.cursor()
        db_cursor.execute(sql)

        for fplan_db_row in db_cursor:
            agency_id = fplan_db_row['agency_id']
            agency_ids.append(agency_id)

        db_cursor.close()

        return agency_ids

    def _compute_duplicate_trips_for_agency(self, agency_id) -> MapFplanDbRow:
        map_duplicate_trips = self._query_duplicate_trips_for_agency_id(agency_id)
        if map_duplicate_trips == {}:
            return {}

        keep_map_duplicate_trips: MapFplanDbRow = {}
        for duplicate_key, trip_db_rows in map_duplicate_trips.items():
            merged_day_bits: Optional[str] = None
            has_overlaps = False

            map_fplan_row_indices = {}
            
            for trip_db_row in trip_db_rows:
                service_id = trip_db_row['service_id']
                calendar_db_row: CalendarDbRow = self.hrdf_db_lookups['calendar'][service_id]
                day_bits = calendar_db_row['day_bits']

                if merged_day_bits is None:
                    merged_day_bits = f'{day_bits}'
                    continue

                if GTFS_Calendar.has_calendar_overlaps(merged_day_bits, day_bits):
                    has_overlaps = True

                merged_day_bits = GTFS_Calendar.merge_calendar_day_bits(merged_day_bits, day_bits)

                map_fplan_row_indices[trip_db_row['fplan_row_idx']] = 1
            # loop

            # Discard variants (*A VE) of the same FPLAN entry: they describe
            # one source trip, rather than separate duplicate trips.
            fplan_row_indices = list(map_fplan_row_indices.keys())
            if len(fplan_row_indices) == 1:
                continue
            
            if not has_overlaps:
                # Trips on disjoint service days never run on the same day,
                # so sharing a duplicate key does not make them duplicates.
                continue

            keep_map_duplicate_trips[duplicate_key] = trip_db_rows

        map_duplicate_trips = keep_map_duplicate_trips

        return map_duplicate_trips

    def _query_duplicate_trips_for_agency_id(self, agency_id) -> MapFplanDbRow:
        hrdf_trips_sql = load_resource_from_bundle(self.map_sql_queries, 'hrdf_select_trips_light')

        where_parts = [
            f"AND fplan.agency_id = '{agency_id}'"
        ]

        where_parts_s = "\n".join(where_parts)
        hrdf_trips_sql = hrdf_trips_sql.replace('[EXTRA_WHERE]', where_parts_s)

        hrdf_cursor = self.hrdf_db.cursor()
        hrdf_cursor.execute(hrdf_trips_sql)

        map_duplicates: MapFplanDbRow = {}
        for db_row in hrdf_cursor:
            hrdf_trip_db_row: FplanDbRow = db_row

            duplicate_key = hrdf_trip_db_row['fplan_trip_id']
            if agency_id == '801':
                irn_rows = HRDF_Trip_Variant.compute_property_rows_for_fplan_content('*I RN', hrdf_trip_db_row['fplan_content'])
                if len(irn_rows) == 1:
                    extra_key = irn_rows[0][29:38]
                    duplicate_key = f'{duplicate_key}-{extra_key}'
                else:
                    row_idx = hrdf_trip_db_row['fplan_row_idx']
                    raise ValueError(f'ERROR - row_idx:{row_idx} - expected 1 *I RN row, got {len(irn_rows)} instead')

            if duplicate_key not in map_duplicates:
                map_duplicates[duplicate_key] = []

            map_duplicates[duplicate_key].append(hrdf_trip_db_row)

        hrdf_cursor.close()

        # Discard groups with only one trip: a duplicate requires at least
        # two trips sharing the same duplicate key.
        keep_map_duplicates: MapFplanDbRow = {}
        for duplicate_key, hrdf_db_trip_rows in map_duplicates.items():
            if len(hrdf_db_trip_rows) > 1:
                keep_map_duplicates[duplicate_key] = hrdf_db_trip_rows
        
        map_duplicates = keep_map_duplicates

        return map_duplicates
