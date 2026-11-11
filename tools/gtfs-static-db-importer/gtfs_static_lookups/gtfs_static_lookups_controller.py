from contextlib import closing
from pathlib import Path
from typing import List, Optional, TypedDict, cast

from gtfs_db_importer.helpers.gtfs_helpers import parse_gtfs_day

from .helpers.config_helpers import load_yaml_config
from .helpers.db_engine import SQLiteDBEngine
from .helpers.json_helpers import export_json_to_file
from .helpers.log_helpers import log_message


class AgencyRow(TypedDict):
    rowid: int
    agency_id: str
    agency_name: str
    agency_url: Optional[str]
    agency_timezone: Optional[str]
    agency_lang: Optional[str]
    agency_phone: Optional[str]


class AgencyLookup(TypedDict):
    lookup_name: str
    data_source: str
    rows_no: int
    rows: List[AgencyRow]


class GTFS_StaticLookupsController:
    def __init__(self, gtfs_db_path: Path):
        self._gtfs_db_path = gtfs_db_path
        module_path = Path(__file__).resolve().parent
        config_path = module_path / 'config.yml'
        self._app_config = load_yaml_config(config_path, module_path.parent)
        gtfs_day = parse_gtfs_day(gtfs_db_path.name)
        self._gtfs_day = gtfs_day.strftime('%Y-%m-%d')

    def create_table_lookups(self):
        self._create_agency_lookup()

    def _create_agency_lookup(self):
        log_message('Creating agency lookup')
        path_template = self._app_config['gtfs_static_path_templates']['gtfs_table']
        output_path_s = path_template.replace('${GTFS_DAY}', self._gtfs_day)
        output_path_s = output_path_s.replace('${TABLE_NAME}', 'agency')
        output_path = Path(output_path_s)

        db_engine = SQLiteDBEngine(db_path=self._gtfs_db_path)
        rows: List[AgencyRow] = []
        with closing(db_engine.get_cursor()) as cursor:
            cursor.execute('SELECT ROWID, * FROM agency')
            for database_row in cursor:
                agency_row = cast(AgencyRow, dict(database_row))
                rows.append(agency_row)

        lookup: AgencyLookup = {
            'lookup_name': 'agency',
            'data_source': str(self._gtfs_db_path),
            'rows_no': len(rows),
            'rows': rows,
        }
        export_json_to_file(lookup, output_path, pretty_print=True)

        log_message(f'Created agency lookup with {len(rows)} rows: {output_path}')
