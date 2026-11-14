import argparse
from pathlib import Path

from gtfs_static_lookups.gtfs_static_lookups_controller import GTFS_StaticLookupsController


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gtfs_db', type=Path, required=True)
    args = parser.parse_args()

    gtfs_db_path = args.gtfs_db
    if not gtfs_db_path.exists():
        raise FileNotFoundError(f'GTFS DB path does not exist: {gtfs_db_path}')

    controller = GTFS_StaticLookupsController(gtfs_db_path)
    controller.create_table_lookups()

    # TODO - think of the day trips lookups - how to build the cache


if __name__ == '__main__':
    main()
