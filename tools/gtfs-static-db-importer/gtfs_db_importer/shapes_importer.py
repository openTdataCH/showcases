import csv

from .helpers.file_helpers import compute_file_rows_no
from .helpers.log_helpers import log_message
from .import_context import ImportContext


class ShapesImporter:
    def __init__(self, context: ImportContext):
        self._context = context

    def import_shapes(self):
        log_message('START import shapes')
        shapes_path = self._context.gtfs_folder_path / 'shapes.txt'
        shapes_writer = self._context.db_engine.create_csv_writer('shapes')
        row_count = 0
        try:
            if shapes_path.is_file():
                log_message(f'Reading {shapes_path}')
                total_rows = compute_file_rows_no(shapes_path) - 1
                if total_rows < 0:
                    total_rows = 0
                self._context.source_table_rows['shapes'] = total_rows
                formatted_total_rows = f'{total_rows:,}'.replace(',', "'")
                log_message(f'Found {formatted_total_rows} shapes rows')
                with shapes_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                    csv_reader = csv.DictReader(csv_file)
                    for shape_row in csv_reader:
                        if row_count % 2_000_000 == 0:
                            formatted_row_count = f'{row_count:,}'.replace(',', "'")
                            log_message(
                                f'... parsed {formatted_row_count} / {formatted_total_rows} shapes rows; '
                                f'kept {formatted_row_count}'
                            )

                        shapes_writer.prepare_row(shape_row)
                        row_count += 1
                    # loop shapes.txt CSV rows
                # with
                formatted_row_count = f'{row_count:,}'.replace(',', "'")
                log_message(
                    f'Parsed {formatted_row_count} / {formatted_total_rows} shapes rows; '
                    f'kept {formatted_row_count}'
                )
            else:
                log_message('No shapes.txt present; creating an empty shapes table')
        finally:
            shapes_writer.close()

        self._context.db_engine.drop_and_recreate_table('shapes')
        self._context.db_engine.load_csv_into_table('shapes', shapes_writer.csv_path)
        self._context.db_engine.add_table_indexes('shapes')
        formatted_row_count = f'{row_count:,}'.replace(',', "'")
        log_message(f'Imported {formatted_row_count} shapes rows')
        log_message('DONE import shapes')
        print()
