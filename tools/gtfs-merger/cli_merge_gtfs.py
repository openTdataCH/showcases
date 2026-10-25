import argparse
from pathlib import Path

from gtfs_merger.gtfs_merger import GTFS_Merger


def main():
    parser = argparse.ArgumentParser(
        description='Merge two GTFS folders (currently feed_info.txt, agency.txt and calendar.txt).'
    )
    parser.add_argument('--gtfs1', type=Path, required=True)
    parser.add_argument('--gtfs2', type=Path, required=True)
    parser.add_argument('--output-gtfs', type=Path, required=True)
    args = parser.parse_args()

    merger = GTFS_Merger(args.gtfs1, args.gtfs2, args.output_gtfs)
    merger.merge()


if __name__ == '__main__':
    main()
