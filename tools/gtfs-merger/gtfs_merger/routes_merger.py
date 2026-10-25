import csv
from pathlib import Path
from typing import Dict, List, Set

from .helpers.csv_updater import CSV_Updater
from .helpers.log_helpers import log_message


class RoutesMerger:
    def merge(self, first_gtfs_path: Path, second_gtfs_path: Path, output_gtfs_path: Path,
              table_config: Dict[str, List[str]]) -> Dict[str, str]:
        log_message('START merge routes')
        second_routes_by_id: Dict[str, Dict[str, str]] = {}
        second_input_path = second_gtfs_path / 'routes.txt'
        log_message(f'Reading {second_input_path}')
        row_count = 0
        with second_input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for route in csv_reader:
                if row_count % 10_000 == 0:
                    formatted_row_count = f'{row_count:,}'.replace(',', "'")
                    log_message(f'... parsed {formatted_row_count} routes from {second_input_path}')

                second_routes_by_id[route['route_id']] = route
                row_count += 1
            # loop
        # with

        first_route_id_map: Dict[str, str] = {}
        output_route_ids: Set[str] = set()
        output_path = output_gtfs_path / 'routes.txt'
        csv_writer = CSV_Updater.init_with_table_config(output_path, table_config)
        try:
            for route in second_routes_by_id.values():
                csv_writer.prepare_row(route)
                output_route_ids.add(route['route_id'])
            # loop

            first_input_path = first_gtfs_path / 'routes.txt'
            log_message(f'Reading {first_input_path}')
            row_count = 0
            with first_input_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for route in csv_reader:
                    if row_count % 10_000 == 0:
                        formatted_row_count = f'{row_count:,}'.replace(',', "'")
                        log_message(f'... parsed {formatted_row_count} routes from {first_input_path}')

                    route_id = route['route_id']
                    output_route_id = route_id
                    insert_route = True
                    if route_id in second_routes_by_id:
                        second_route = second_routes_by_id[route_id]
                        if self._routes_match(route, second_route):
                            insert_route = False
                        else:
                            output_route_id = f'd1.{route_id}'

                    if insert_route:
                        if output_route_id in output_route_ids:
                            raise ValueError(
                                f'Route ID collision: GTFS1 route {route_id} maps to existing ID {output_route_id}'
                            )
                        route['route_id'] = output_route_id
                        csv_writer.prepare_row(route)
                        output_route_ids.add(output_route_id)
                    first_route_id_map[route_id] = output_route_id
                    row_count += 1
                # loop
            # with
        finally:
            csv_writer.close()

        formatted_total = f'{len(output_route_ids):,}'.replace(',', "'")
        log_message(f'Saved {formatted_total} unique routes to {output_path}')
        log_message('DONE merge routes')
        return first_route_id_map

    def _routes_match(self, first_route: Dict[str, str], second_route: Dict[str, str]) -> bool:
        for field in ['agency_id', 'route_short_name', 'route_desc', 'route_type']:
            first_value = first_route.get(field, '')
            second_value = second_route.get(field, '')
            if first_value is None:
                first_value = ''
            if second_value is None:
                second_value = ''
            if first_value != second_value:
                return False
        # loop
        return True
