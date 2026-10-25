from pathlib import Path

from .agency_merger import AgencyMerger
from .calendar_merger import CalendarMerger
from .feed_info_merger import FeedInfoMerger
from .helpers.config_helpers import load_yaml_config
from .helpers.log_helpers import log_message


class GTFS_Merger:
    def __init__(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path):
        self._first_gtfs_path = first_gtfs_path
        self._second_gtfs_path = second_gtfs_path
        self._output_gtfs_path = output_gtfs_path

    def merge(self):
        log_message('START GTFS folder merge')
        log_message(f'First GTFS folder: {self._first_gtfs_path}')
        log_message(f'Second GTFS folder: {self._second_gtfs_path}')
        log_message(f'Output GTFS folder: {self._output_gtfs_path}')
        print()

        merger_path = Path(__file__).resolve().parent
        config = load_yaml_config(merger_path / 'config.yml', merger_path)
        schema = load_yaml_config(Path(config['gtfs_schema_path']))

        feed_info_merger = FeedInfoMerger()
        merged_feed = feed_info_merger.prepare(self._first_gtfs_path, self._second_gtfs_path)
        self._output_gtfs_path.mkdir(parents=True, exist_ok=True)
        feed_info_merger.write(self._output_gtfs_path, merged_feed, schema['tables']['feed_info'])
        print()

        agency_merger = AgencyMerger()
        agency_merger.merge(
            self._first_gtfs_path, self._second_gtfs_path, self._output_gtfs_path,
            schema['tables']['agency'],
        )
        print()

        calendar_merger = CalendarMerger()
        calendar_merger.merge(
            self._first_gtfs_path, self._second_gtfs_path, self._output_gtfs_path,
            schema['tables']['calendar'],
        )
        print()

        log_message('DONE GTFS folder merge')
