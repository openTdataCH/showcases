import argparse
import os
from datetime import date
from pathlib import Path

from gtfs_filter.gtfs_filter import GTFS_Filter


def _parse_date(value: str) -> date:
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f'Invalid date: {value}. Expected a valid calendar date in YYYY-MM-DD format.'
        ) from None

    if parsed_date.isoformat() != value:
        raise argparse.ArgumentTypeError(
            f'Invalid date format: {value}. Expected YYYY-MM-DD.'
        )

    return parsed_date


def _main():
    parser = argparse.ArgumentParser(
        description='Filter a GTFS folder by date range',
        epilog='Currently filters feed_info.txt only.'
    )
    parser.add_argument(
        '--gtfs-src', '--gtfs_src', type=Path, required=True,
        help='Path to the source GTFS folder'
    )
    parser.add_argument(
        '--gtfs-dst', '--gtfs_dst', type=Path, required=True,
        help='Path to the writable destination GTFS folder'
    )
    parser.add_argument(
        '--from', dest='date_from', type=_parse_date,
        metavar='YYYY-MM-DD', help='Start date of the filter range; required if --to is omitted'
    )
    parser.add_argument(
        '--to', dest='date_to', type=_parse_date,
        metavar='YYYY-MM-DD', help='End date of the filter range; required if --from is omitted'
    )
    args = parser.parse_args()

    if not args.gtfs_src.is_dir():
        parser.error(f'--gtfs-src must be an existing folder: {args.gtfs_src}')

    destination_parent = args.gtfs_dst.parent
    if not destination_parent.is_dir():
        parser.error(f'--gtfs-dst parent must be an existing folder: {destination_parent}')

    if not os.access(destination_parent, os.W_OK | os.X_OK):
        parser.error(f'--gtfs-dst parent must be writable: {destination_parent}')

    if args.date_from is None and args.date_to is None:
        parser.error('At least one of --from or --to is required')

    if args.date_from is not None and args.date_to is not None:
        if args.date_from > args.date_to:
            parser.error('--from must be on or before --to')

    gtfs_filter = GTFS_Filter(args.gtfs_src, args.gtfs_dst, args.date_from, args.date_to)
    gtfs_filter.filter()


if __name__ == '__main__':
    _main()
