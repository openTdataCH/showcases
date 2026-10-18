import os, sys

from pathlib import Path

import sqlite3
import csv
import shutil

from typing import Any, Dict, List, Optional, TypedDict, Union, cast

from .csv_updater import CSV_Updater
from .config_helpers import load_yaml_config

def _sanitize_col_def(col_def: str):
    col_def = col_def.strip().rstrip(',')
    col_def = ' '.join(col_def.split()) # keep only one space def
    
    return col_def

class ColumnMetadataType(TypedDict):
    names: List[str]
    defs: List[str]
    indexes: List[str]
    null_if_blank_columns: List[str]

class SQLiteDBEngine:
    db_path: Path
    _db_handle: sqlite3.Connection
    _db_tmp_path: Path

    tables: List[str]
    map_columns_metadata: Dict[str, ColumnMetadataType]

    def __init__(self, db_path: Union[Path, None] = None, is_read_only = True, db_schema_path: Union[Path, None] = None):
        if db_path is None:
            conn_ds = ':memory:'
        else:
            if isinstance(db_path, str):
                db_path = Path(db_path)
            
            self.db_path = db_path

            conn_ds = f'file:{db_path}'
            if is_read_only:
                conn_ds = f'{conn_ds}?mode=ro'
        # check memory or file
        
        self._db_tmp_path = Path(f'{db_path}.tmp')
        
        self._db_handle = sqlite3.connect(conn_ds, uri=True)
        self._db_handle.row_factory = sqlite3.Row

        self.tables = []
        self.map_columns_metadata = {}
        if db_schema_path:
            self._load_db_schema(db_schema_path)
        else:
            self._fetch_tables_via_pragma()

    @staticmethod
    def init_read_write(db_path: Path, db_schema_path: Union[Path, None] = None):
        if not db_path.parent.exists():
            os.makedirs(db_path.parent)

        db_engine = SQLiteDBEngine(db_path=db_path, is_read_only=False, db_schema_path=db_schema_path)
        return db_engine
    
    @staticmethod
    def init_memory(db_schema_path: Union[Path, None]):
        db_engine = SQLiteDBEngine(db_path=None, is_read_only=True, db_schema_path=db_schema_path)
        return db_engine
    
    def compute_table_stats(self):
        table_stats = {}
        
        for table_name in self.tables:
            table_stats[table_name] = self.count_rows_table(table_name)
            
        return table_stats
    
    def _fetch_table_columns_via_pragma(self, table_name) -> List[str]:
        sql = f"PRAGMA table_info({table_name})"
        columns_cursor = self._db_handle.cursor()
        columns_cursor.execute(sql)
        columns_db_rows = columns_cursor.fetchall()
        columns_cursor.close()

        column_names: List[str] = []
        for pragma_column_row in columns_db_rows:
            column_name: str = pragma_column_row[1]
            column_names.append(column_name)
            
        return column_names

    def _fetch_tables_via_pragma(self):
        self.tables = []
        self.map_columns_metadata = {}

        sql = "SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"
        cursor = self._db_handle.cursor()
        cursor.execute(sql)
        for db_row in cursor:
            table_name: str = db_row[0]
            self.tables.append(table_name)

            column_data: ColumnMetadataType = {
                'names': self._fetch_table_columns_via_pragma(table_name),
                'defs': [],
                'indexes': [],
                'null_if_blank_columns': [],
            }
            self.map_columns_metadata[table_name] = column_data
        cursor.close()

    def _load_db_schema(self, db_schema_path: Path):
        self.tables = []
        self.map_columns_metadata = {}

        db_schema_json = load_yaml_config(db_schema_path)
        for table_name, table_config in db_schema_json['tables'].items():
            column_names = []
            column_defs = []
            column_indexes = []
            null_if_blank_columns = []
            
            for column_def_row in table_config['columns']:
                null_if_blank = False
                if isinstance(column_def_row, str):
                    column_definition = column_def_row
                elif isinstance(column_def_row, dict):
                    column_definition = column_def_row.get('definition')
                    if not isinstance(column_definition, str):
                        raise ValueError(f'Expected a string definition for column in {table_name}: {column_def_row}')
                    null_if_blank = column_def_row.get('null_if_blank', False)
                    if not isinstance(null_if_blank, bool):
                        raise ValueError(f'Expected a boolean null_if_blank for column in {table_name}: {column_def_row}')
                else:
                    raise ValueError(f'Expected a string or mapping for column in {table_name}: {column_def_row}')

                column_def_config = _sanitize_col_def(column_definition)
                
                column_def_config_parts = column_def_config.split(' ')
                if len(column_def_config_parts) == 1:
                    print(table_config['columns'])
                    raise ValueError(f'No column type defined for {column_def_row}')
                
                column_name = column_def_config_parts[0]

                if null_if_blank:
                    null_if_blank_columns.append(column_name)
                
                column_names.append(column_name)
                column_defs.append(column_def_config)
            # loop config column defs
            
            keys_data = table_config.get('keys', [])
            for key_def_row in keys_data:
                key_def_config = _sanitize_col_def(key_def_row)
                column_defs.append(key_def_config)
            # loop keys
            
            index_defs = table_config.get('indexes', [])
            for column_def in index_defs:
                column_def_config = _sanitize_col_def(column_def)
                column_indexes.append(column_def_config)
            
            self.tables.append(table_name)
            self.map_columns_metadata[table_name] = {
                'names': column_names,
                'defs': column_defs,
                'indexes': column_indexes,
                'null_if_blank_columns': null_if_blank_columns,
            }
        # loop tables config
    
    def _query(self, sql: str, map_by_field: Optional[str] = None) -> Union[dict[str, Any], list[Any]]:
        row_items = []
        map_row_items = {}

        cursor = self._db_handle.cursor()
        cursor.execute(sql)
        
        column_names = [description[0] for description in cursor.description]
        
        for db_row in cursor:
            db_row_dict = {}
            for column_idx, column_name in enumerate(column_names):
                db_row_dict[column_name] = db_row[column_idx]
            
            if map_by_field:
                map_row_items[db_row_dict[map_by_field]] = db_row_dict
            else:
                row_items.append(db_row_dict)
        cursor.close()
        
        if map_by_field:
            return map_row_items
        else:
            return row_items

    def query(self, sql: str) -> list[Any]:
        row_items = cast(list[Any], self._query(sql))
        return row_items
    
    def query_map_by_field(self, sql: str, map_by_field: str) -> dict[str, Any]:
        map_row_items = cast(dict[str, Any], self._query(sql, map_by_field))
        return map_row_items
    
    def query_table(self, table_name: str) -> list[Any]:
        sql = f'SELECT * FROM {table_name}'
        query_results = cast(list[Any], self._query(sql))
        return query_results
    
    def query_table_map_by_field(self, table_name: str, map_by_field: str) -> dict[str, Any]:
        sql = f'SELECT * FROM {table_name}'
        query_results = cast(dict[str, Any], self._query(sql, map_by_field))
        return query_results
    
    def count_rows_table(self, table_name: str, where_clause = None) -> int:
        sql = f"SELECT COUNT(1) AS cno FROM {table_name} {where_clause}"
        return self._db_handle.cursor().execute(sql).fetchone()[0]
    
    # runs only one query. for more SQL statements use run_sql_script()
    def run_sql(self, sql: str):
        self._db_handle.execute(sql)
        self._db_handle.commit()

    # runs multiple queries in one script
    def run_sql_script(self, sql: str):
        self._db_handle.executescript(sql)
        self._db_handle.commit()
    
    def drop_table(self, table_name: str):
        sql = f'DROP TABLE IF EXISTS {table_name}'
        self.run_sql(sql)

    def drop_and_recreate_table(self, table_name: str):
        self.drop_table(table_name)

        column_defs = self.map_columns_metadata[table_name]['defs']
        if len(column_defs) == 0:
            raise ValueError(f'No defs for table {table_name} -- check schema')

        column_defs_s = ", ".join(column_defs)
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs_s});"
        self.run_sql(sql)

    def get_cursor(self) -> sqlite3.Cursor: 
        cursor = self._db_handle.cursor()
        return cursor
    
    def add_table_indexes(self, table_name):
        index_column_list = self.map_columns_metadata[table_name]['indexes']
        for column_name in index_column_list:
            column_names = [x.strip() for x in column_name.split(',')]
            column_key = '_'.join(column_names)
            sql = f"CREATE INDEX IF NOT EXISTS {table_name}_{column_key} ON {table_name}({column_name})"
            self._db_handle.execute(sql)
        
    def vacuum(self):
        sql = 'VACUUM'
        self.run_sql(sql)

    def query_rows_no(self, table_name: str):
        sql = f'SELECT COUNT(1) AS rows_no FROM {table_name}'
        query_results = cast(List[Any], self.query(sql))
        
        rows_no = query_results[0]['rows_no']
        
        return rows_no
    
    def _compute_csv_writer_path(self, table_name: str) -> Path:
        csv_path = self._db_tmp_path.joinpath(f'{table_name}.txt')
        return csv_path
    
    def create_csv_writer(self, table_name: str) -> CSV_Updater:
        csv_path = self._compute_csv_writer_path(table_name)

        if not os.path.isdir(csv_path.parent):
            os.makedirs(csv_path.parent)

        column_names = self.map_columns_metadata[table_name]['names']
        csv_writer = CSV_Updater(csv_path, column_names)
        
        return csv_writer

    def load_csv_into_table(self, table_name: str, csv_path: Path):
        null_if_blank_columns = self.map_columns_metadata[table_name]['null_if_blank_columns']

        csv_file = open(csv_path, encoding='utf-8-sig')
        csv_reader = csv.DictReader(csv_file)
        
        column_names = self.map_columns_metadata[table_name]['names']
        column_names_s = ', '.join(column_names)
        values_s = ('?, ' * len(column_names))[0:-2]
        template_insert_sql = f'INSERT INTO {table_name}({column_names_s}) VALUES({values_s})'
        
        batch_insert_rows_no = 10_000
        batch_insert_values = []

        insert_cursor = self._db_handle.cursor()
        
        for csv_row in csv_reader:
            if len(batch_insert_values) >= batch_insert_rows_no:
                insert_cursor.executemany(template_insert_sql, batch_insert_values)
                self._db_handle.commit()
                batch_insert_values = []
                
            row_values = []
            for key in column_names:
                field_value = csv_row.get(key, None)
                if key in null_if_blank_columns:
                    if field_value is not None:
                        if field_value.strip() == '':
                            field_value = None
                row_values.append(field_value)
            batch_insert_values.append(row_values)
        # loop read csv rows
        csv_file.close()
        
        insert_cursor.executemany(template_insert_sql, batch_insert_values)
        self._db_handle.commit()

    def optimize_insert_updates(self):
        self.run_sql('PRAGMA synchronous = OFF')
        self.run_sql('PRAGMA journal_mode = OFF')

    def update_table_from_csv(self, csv_path: Path, sql_template: str):
        self.optimize_insert_updates()

        batch_update_rows_no = 10_000
        batch_update_values = []

        csv_file = open(csv_path, encoding='utf-8')
        csv_reader = csv.DictReader(csv_file)

        update_cursor = self.get_cursor()

        csv_row_id = 1
        for csv_row in csv_reader:
            if len(batch_update_values) >= batch_update_rows_no:
                update_cursor.executemany(sql_template, batch_update_values)
                self._db_handle.commit()
                batch_update_values = []
            
            batch_update_values.append(csv_row)

            csv_row_id += 1
        # loop csv rows
        update_cursor.executemany(sql_template, batch_update_values)
        self._db_handle.commit()

        update_cursor.close()

        csv_file.close()

    def cleanup(self):
        shutil.rmtree(self._db_tmp_path)
        self.vacuum()

    def get_db_tmp_path(self):
        path = self._db_tmp_path
        return path
    
    def export_sql_to_csv(self, sql: str, csv_path: Path, column_names: Union[List[str], None] = None):
        cursor = self.get_cursor()
        cursor.execute(sql)
        
        if column_names is None:
            column_names = [column[0] for column in cursor.description]
        csv_updater = CSV_Updater(csv_path, column_names)

        for db_row in cursor.execute(sql):
            csv_updater.prepare_row(dict(db_row))
        cursor.close()
    
    def export_table_to_csv(self, table_name: str, csv_path: Path):
        sql = f'SELECT * FROM {table_name}'
        self.export_sql_to_csv(sql, csv_path)
