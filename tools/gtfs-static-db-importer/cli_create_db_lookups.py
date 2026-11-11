import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gtfs_db', type=Path, required=True)
    args = parser.parse_args()

    gtfs_db_path = args.gtfs_db
    if not gtfs_db_path.exists():
        raise FileNotFoundError(f'GTFS DB path does not exist: {gtfs_db_path}')


if __name__ == '__main__':
    main()
