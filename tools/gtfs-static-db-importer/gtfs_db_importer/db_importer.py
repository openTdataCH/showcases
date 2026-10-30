import os, sys
from pathlib import Path
import yaml
import datetime
from typing import Optional

from .helpers.db_engine import SQLiteDBEngine
from .helpers.log_helpers import log_message

from .import_context import ImportContext
from .import_metadata import ImportMetadata
from .date_range import resolve_import_date_range
from .csv_importer import CSVImporter
from .calendar_importer import CalendarImporter
from .feed_info_importer import FeedInfoImporter
from .agency_importer import AgencyImporter
from .stops_importer import StopsImporter
from .stations_importer import StationsImporter
from .trips_importer import TripsImporter
from .stop_times_importer import StopTimesImporter
from .frequencies_importer import FrequenciesImporter
from .routes_importer import RoutesImporter
from .transfers_importer import TransfersImporter
from .shapes_importer import ShapesImporter


class GTFS_DB_Importer:
    _map_sql_queries: dict[str, str]
    _db_engine: SQLiteDBEngine
    _gtfs_folder_path: Path
    _db_lock_path: Path
    _bo_realtime_csv_path: Path

    def __init__(self, app_config, gtfs_folder_path: Path, db_path: Path,
                 from_date: Optional[datetime.datetime] = None, to_date: Optional[datetime.datetime] = None):
        calendar_data = resolve_import_date_range(gtfs_folder_path, from_date, to_date)
        self._map_sql_queries = app_config['map_sql_queries']

        script_path = Path(os.path.realpath(__file__))
        db_schema_path = Path(f"{script_path.parent}/config/gtfs_schema.yml")
        self._db_engine = SQLiteDBEngine.init_read_write(db_path, db_schema_path=db_schema_path)
        
        self._gtfs_folder_path = gtfs_folder_path
        self._db_lock_path = Path(f'{self._db_engine.db_path}.lock')
        self._bo_realtime_csv_path = Path(app_config['bo_realtime_csv_path'])

        context = ImportContext(
            db_engine=self._db_engine,
            map_sql_queries=self._map_sql_queries,
            gtfs_folder_path=self._gtfs_folder_path,
            bo_realtime_csv_path=self._bo_realtime_csv_path,
            calendar_data=calendar_data,
        )
        self._csv_importer = CSVImporter(context)
        self._calendar_importer = CalendarImporter(context)
        self._feed_info_importer = FeedInfoImporter(context)
        self._agency_importer = AgencyImporter(context)
        self._stops_importer = StopsImporter(context)
        self._stations_importer = StationsImporter(context)
        self._trips_importer = TripsImporter(context)
        self._stop_times_importer = StopTimesImporter(context)
        self._frequencies_importer = FrequenciesImporter(context)
        self._routes_importer = RoutesImporter(context)
        self._transfers_importer = TransfersImporter(context)
        self._shapes_importer = ShapesImporter(context)
        self._import_metadata = ImportMetadata(context)

    def start(self):
        import_start = datetime.datetime.now(datetime.timezone.utc)
        log_message("START GTFS IMPORT")
        log_message(f'GTFS PATH : {self._gtfs_folder_path}')
        log_message(f'DB PATH   : {self._db_engine.db_path}')
        print()
        
        if os.path.isfile(self._db_lock_path):
            print('ERROR: lock path present, ABORT')
            print(f'ls -al {self._db_lock_path.parent}')
            sys.exit(1)
        #
        
        self._write_lock_file()
        self._import_metadata.start_import(import_start)

        # calendar
        self._calendar_importer.log_date_range()
        self._feed_info_importer.import_feed_info()
        self._calendar_importer.import_calendar()
        
        # trips
        self._trips_importer.import_trips()

        # routes, agency
        self._routes_importer.import_routes()
        self._agency_importer.import_agency()

        # stops
        self._stops_importer.import_stops()

        # stop_times
        self._stop_times_importer.import_stop_times()

        # update trips, stop_times
        self._trips_importer.update_trips_stop_times()
        self._trips_importer.check_trips_day_minutes()

        # frequencies
        self._frequencies_importer.import_frequencies()

        # update stations, stop.day_bits
        self._stations_importer.populate_stations()
        self._stations_importer.update_stations_day_bits()

        # transfers
        self._transfers_importer.import_transfers()
        
        self._routes_importer.update_routes_representative_trip()
        self._routes_importer.create_fts_routes()

        self._shapes_importer.import_shapes()
        
        self._cleanup()
        self._import_metadata.finish_import()
        
        self._remove_lock_file()

        log_message("DONE GTFS IMPORT")

    def _load_schema_config(self):
        script_path = Path(os.path.realpath(__file__))
        db_schema_path = f"{script_path.parent}/config/gtfs_schema.yml"
        db_schema_config = yaml.safe_load(open(db_schema_path, encoding='utf-8'))

        return db_schema_config

    def _write_lock_file(self):
        now_f = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lock_file_text = f'START: {now_f}'
        lock_file = open(self._db_lock_path, 'w', encoding='utf-8')
        lock_file.write(lock_file_text)
        lock_file.close()

    def _remove_lock_file(self):
        os.remove(self._db_lock_path)

    def _cleanup(self):
        log_message('START cleaning up tmp folder, VACUUM')
        self._db_engine.cleanup()
        log_message('... DONE')
        print()
