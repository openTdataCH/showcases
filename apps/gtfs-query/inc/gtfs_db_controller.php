<?php

class GTFS_DB_Controller {
    var $is_dev;
    var $request_URI;
    
    var $gtfs_db_day;
    var $map_business_organisations;
    var $db;

    var $use_cache;
    var $cache_prefix;

    var $map_sql_queries;
    var $app_db_cache_path;

    var $sql_builder_config;
    var $gtfs_from_date;

    function __construct($config, $gtfs_db_day) {
        $this->is_dev = APP_PROFILE === 'dev';
        $this->request_URI = $_SERVER['REQUEST_URI'];

        if ($gtfs_db_day === 'LATEST') {
            $gtfs_db_day = $this->compute_latest_gtfs_day($config);
            if (is_null($gtfs_db_day)) {
                die('cant find latest gtfs-day catalog item');
            }
        }

        $this->gtfs_db_day = $gtfs_db_day;

        $this->map_business_organisations = $this->_load_map_business_organisations($config);

        $gtfs_dbs_path = $config['ojp_gtfs_dbs_path'];

        $gtfs_db_path = $this->compute_gtfs_db_path_from_day($gtfs_dbs_path, $gtfs_db_day);
        if (!file_exists($gtfs_db_path)) {
            print('error - cant find db for ' . $gtfs_db_day);
            exit(1);
        }

        $this->db = new SQLite3($gtfs_db_path, SQLITE3_OPEN_READONLY);

        $this->map_sql_queries = $config['map_sql_queries'];
        $this->app_db_cache_path = $config['app_db_cache_path'];

        $this->use_cache = TRUE;

        $this->cache_prefix = 'v2_' . $gtfs_db_day;

        $sql_builder_config_path = $config['sql_builder_path'];
        $this->sql_builder_config = ConfigHelpers::loadConfigAtPath($sql_builder_config_path);

        $calendar_sql = "SELECT start_date FROM calendar LIMIT 1";
        $gtfs_start_dt_s = $this->db->querySingle($calendar_sql);
        $this->gtfs_from_date = date_create_from_format("Ymd", $gtfs_start_dt_s);
    }

    private function compute_gtfs_db_path_from_day($gtfs_dbs_path, $gtfs_day) {
        $gtfs_db_filename = 'gtfs_' . $gtfs_day . '.sqlite';
        $gtfs_db_path = $gtfs_dbs_path . '/' . $gtfs_db_filename;
        return $gtfs_db_path;
    }

    private function _load_map_business_organisations($config) {
        $csv_path = $config['business_organisation_latest_path'];
        $csv_file = $this->_load_csv_file($csv_path);

        $map_business_organisations = array();

        $csv_headers = fgetcsv($csv_file, null, ';', $enclosure = "\"", $escape = "\\");
        if (!$csv_headers) {
            die('empty CSV headers found for _load_map_business_organisations()');
        }

        while (($row = fgetcsv($csv_file, 1000, ';', '"', '\\')) !== false) {
            $csv_row = array_combine($csv_headers, $row);

            $sboid = $csv_row['sboid'];
            $agency_id = $csv_row['organisationNumber'];
            
            $map_business_organisations[$sboid] = $agency_id;
        }

        fclose($csv_file);

        return $map_business_organisations;
    }

    private function compute_latest_gtfs_day($config) {
        $gtfs_dbs_catalog_path = $config['gtfs_dbs_catalog_path'];
        $gtfs_dbs_catalog = json_decode(file_get_contents($gtfs_dbs_catalog_path), true);
        if (count($gtfs_dbs_catalog['items']) === 0) {
            return null;
        }

        $gtfs_day = null;
        foreach ($gtfs_dbs_catalog['items'] as $db_item) {
            if (is_null($db_item['db_relative_path'])) {
                continue;
            }

            $gtfs_day = $db_item['gtfs_day'];
            break;
        }
        
        return $gtfs_day;
    }

    private function _massage_sql_fields($sql_fields) {
        foreach ($sql_fields as $key => $value) {
            $sql_fields[$key] = rtrim($value, " ,");
        }

        return $sql_fields;
    }

    public function query_day_trips($sql_fields_profile, $row_format, $service_day, $filter_agency_ids_s, $from_hhmm = null, $to_hhmm = null) {
        $sql_query_config = $this->sql_builder_config['sql_builder'];
        if (!array_key_exists($sql_fields_profile, $sql_query_config)) {
            die('cant handle query_day_trips ' . $sql_fields_profile);
        }

        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder'][$sql_fields_profile]));

        $parse_db_row_type = 'FLAT';

        $cache_filename_parts = array(
            'query_day_trips_' . $this->cache_prefix,
            'profile_' . $sql_fields_profile,
            'row_format_' . $row_format,
            'day_' . $service_day,
            'db_row_type_' . $parse_db_row_type,
        );
        
        $filter_agency_ids = explode(',', $filter_agency_ids_s);
        $sql_where_agency = $this->compute_agency_ids_sql_filter($filter_agency_ids);
        array_push($query_config['where'], $sql_where_agency);
        array_push($cache_filename_parts, 'agency_ids_' . implode('-', $filter_agency_ids));

        $service_day_where = $this->_compute_sql_service_day_where($service_day);
        array_push($query_config['where'], $service_day_where);

        if ($from_hhmm !== null) {
            array_push($cache_filename_parts, 'from_' . $from_hhmm);
        }
        if ($to_hhmm !== null) {
            array_push($cache_filename_parts, 'from_' . $to_hhmm);
        }
        if (($from_hhmm !== null) && ($to_hhmm !== null)) {
            $sql_where_from_to = file_get_contents($this->map_sql_queries['where_from_to_trips']);
            
            $request_from_day_minutes = $this->convert_hhmm_day_minutes($from_hhmm);
            $request_to_day_minutes = $this->convert_hhmm_day_minutes($to_hhmm);
            $sql_where_from_to = str_replace('[INTERVAL_FROM]', $request_from_day_minutes, $sql_where_from_to);
            $sql_where_from_to = str_replace('[INTERVAL_TO]', $request_to_day_minutes, $sql_where_from_to);
            array_push($query_config['where'], $sql_where_from_to);
        }

        $sql = $this->build_select_query($query_config);

        $cache_filename = implode('__', $cache_filename_parts) . '.json';
        $cache_path = $this->app_db_cache_path . '/' . $cache_filename;

        $data_source = null;
        if ($this->use_cache && file_exists($cache_path)) {
            $db_rows_s = file_get_contents($cache_path);
            $db_rows = json_decode($db_rows_s, TRUE);
            $data_source = 'cache: ' . $cache_filename;
        } else {
            $db_rows = $this->query_db_trips($sql, $parse_db_row_type, $row_format);
            file_put_contents($cache_path, json_encode($db_rows));
            $data_source = 'DB';
        }

        $result_json = array(
            'metadata' => array(
                'data_source' => $data_source,
                'rows_no' => count($db_rows),
                'columns' => $this->_massage_sql_fields($query_config['fields']),
            ),
            'rows' => $db_rows,
        );

        if (APP_PROFILE === 'dev') {
            $result_json['metadata']['sql'] = $sql;
        }

        return $result_json;
    }

    private function query_db_trips($sql, $parse_db_row_type, $row_format) {
        $result = $this->db->query($sql);

        $result_rows = array();

        while ($db_row = $result->fetchArray(SQLITE3_ASSOC)) {
            // FLAT by default
            $result_row = $db_row;
            if ($parse_db_row_type === 'FULL') {
                $result_row = $this->parse_db_trip_full($db_row);
            }

            if (array_key_exists('day_bit', $result_row)) {
                unset($result_row['day_bit']);
            }

            if ($row_format === 'array') {
                $result_row = array_values($result_row);
            }

            array_push($result_rows, $result_row);
        }

        return $result_rows;
    }

    private function parse_db_trip_full($db_row) {
        $stop_times = array();
        $stop_times_data = explode(' -- ', $db_row['stop_times_s']);
        foreach($stop_times_data as $stop_time_data) {
            $stop_time_parts = explode('|', $stop_time_data);
            
            $stop_id = $stop_time_parts[0];
            
            $stop_arr_hhmm = $stop_time_parts[1];
            if ($stop_arr_hhmm === '') {
                $stop_arr_hhmm = null;
            }

            $stop_dep_hhmm = $stop_time_parts[2];
            if ($stop_dep_hhmm === '') {
                $stop_dep_hhmm = null;
            }

            $stop_time_row = array(
                'stop_id' => $stop_id,
                'stop_arr' => $stop_arr_hhmm,
                'stop_dep' => $stop_dep_hhmm,
            );
            array_push($stop_times, $stop_time_row);
        }

        $result_row = array(
            'trip_id' => $db_row['trip_id'],
            'departure_time' => $db_row['departure_time'],
            'arrival_time' => $db_row['arrival_time'],
            'trip_headsign' => $db_row['trip_headsign'],
            'route_id' => $db_row['route_id'],
            'agency_id' => $db_row['agency_id'],
            'has_day' => $db_row['day_bit'] === '1',
            'stop_times' => $stop_times,
        );

        return $result_row;
    }

    private function convert_hhmm_day_minutes($hhmm_s) {
        $hours = (int) substr($hhmm_s, 0, 2);
        $minutes = (int) substr($hhmm_s, 2, 2);

        return $hours * 60 + $minutes;;
    }

    private function compute_agency_ids_sql_filter($filter_agency_ids) {
        $agency_ids = $filter_agency_ids;
        if (in_array('HAS_GTFS_RT', $agency_ids)) {
            $agency_ids_sql_filter = "link_agency.has_gtfs_rt = 1";
            return $agency_ids_sql_filter;
        }

        if (empty($agency_ids)) {
            return null;
        }

        $agency_ids_escaped = array();
        foreach($agency_ids as $agency_id) {
            $agency_id_escaped = "'" . $agency_id . "'";
            array_push($agency_ids_escaped, $agency_id_escaped);
        }

        $agency_ids_sql_filter = "routes.agency_id IN (" . implode(', ', $agency_ids_escaped) . ")";
        
        return $agency_ids_sql_filter;
    }

    private function _load_csv_file($csv_path) {
        if (is_file($csv_path) === FALSE) {
            error_log('_load_csv_file: CANT load file at path ' . $csv_path);
            die('cant load file, see error logs for path');
        }

        $csv_file = fopen($csv_path, 'r');
        
        // Read the first line to check for BOM
        $bom = fread($csv_file, 3);
        if ($bom !== "\xEF\xBB\xBF") {
            // If no BOM, rewind the file pointer
            rewind($csv_file);
        }

        return $csv_file;
    }

    public function query_table($table_name) {
        $allowed_tables = array('agency', 'calendar', 'routes', 'stops', 'fts_routes'); 
        if (!in_array($table_name, $allowed_tables)) {
            $message = array(
                "error" => "No lookup found for " . $table_name,
            );
            JsonView::dump_error('400', $message);
            die;
        }

        $cache_filename = 'lookup_table_' . $this->cache_prefix . '_' . $table_name . '.json';
        $cache_path = $this->app_db_cache_path . '/' . $cache_filename;

        if ($this->use_cache && file_exists($cache_path)) {
            $result_rows_s = file_get_contents($cache_path);
            $result_rows = json_decode($result_rows_s, TRUE);
            $data_source = 'cache: ' . $cache_filename;
        } else {
            $result_rows = $this->fetch_table_rows($table_name);
            file_put_contents($cache_path, json_encode($result_rows));
            $data_source = 'DB';
        }

        $result_json = array(
            'lookup_name' => $table_name,
            'data_source' => $data_source,
            'rows_no' => count($result_rows),
            'rows' => $result_rows,
        );

        return $result_json;
    }

    private function fetch_table_rows($table_name, $filter = null) {
        $sql = "SELECT rowid, * FROM $table_name";
        if ($filter) {
            $sql .= " WHERE " . $filter;
        }
        
        $result = $this->db->query($sql);

        $result_rows = array();

        while ($db_row = $result->fetchArray(SQLITE3_ASSOC)) {
            array_push($result_rows, $db_row);
        }

        return $result_rows;
    }

    public function query_trip($trip_id) {
        $result = array(
            'message' => array(),
            'result' => array(
                'trip' => null,
                'calendar' => null,
                'route' => null,
                'agency' => null,
            )
        );

        $trip_rows = $this->fetch_table_rows('trips', "trip_id = '" . $trip_id . "'");
        if (count($trip_rows) !== 1) {
            $result['message']['error'] = 'no trip found for ' . $trip_id;
            return $result;
        }

        $trip_db = $trip_rows[0];
        $result['result']['trip'] = $trip_db;

        $service_id = $trip_db['service_id'] ?: null;
        $calendar_rows = $this->fetch_table_rows('calendar', "service_id = '" . $service_id . "'");
        $result['result']['calendar'] = $calendar_rows[0];

        $route_id = $trip_db['route_id'];
        $route_rows = $this->fetch_table_rows('routes', "route_id = '" . $route_id . "'");
        $result['result']['route'] = $route_rows[0];

        $agency_id =$route_rows[0]['agency_id'];
        $agency_rows = $this->fetch_table_rows('agency', "agency_id = '" . $agency_id . "'");
        $result['result']['agency'] = $agency_rows[0];

        return $result;
    }

    private function build_select_query($query_config) {
        $sql_lines = array('SELECT');   

        $fields = $this->_massage_sql_fields($query_config['fields']);
        $fields_s = implode(",\n", $fields);
        array_push($sql_lines, $fields_s);

        $tables_s = implode(", ", $query_config['tables']);
        array_push($sql_lines, 'FROM ' . $tables_s);

        if (array_key_exists('where', $query_config)) {
            array_push($sql_lines, 'WHERE');
            
            $where_s = implode("\nAND ", $query_config['where']);
            array_push($sql_lines, $where_s);
        }

        if (array_key_exists('limit', $query_config) && ($query_config['limit'] !== null)) {
            $limit_s = 'LIMIT ' . $query_config['limit'];
            array_push($sql_lines, $limit_s);
        }

        $sql = implode("\n", $sql_lines);
        return $sql;
    }

    public function query_trips_by_route_line_ref($route_short_name, $line_ref, $service_day = null) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_routes']));

        $line_ref_parts = explode(':', $line_ref);
        $agency_id = null;

        if (strpos(strtolower($line_ref), ':line:') !== FALSE) {
            // ch:1:Line:823:14

            $agency_id = $line_ref_parts[3];
        } else {
            // 85:801:2425
            
            if (count($line_ref_parts) !== 3) {
                die('unexpected line_ref: '. $line_ref);
            }

            $agency_id = $line_ref_parts[1];
        }

        $agency_id_where = "routes.agency_id = '" . $agency_id . "'";
        array_push($query_config['where'], $agency_id_where);

        $route_short_name_where = "routes.route_short_name = '" . $route_short_name . "'";
        array_push($query_config['where'], $route_short_name_where);

        $sql = $this->build_select_query($query_config);

        $result = $this->db->query($sql);

        $user_route_line_ref = $line_ref_parts[2];

        // POST (801) and other operators have more services with same route_short_name
        // Try to match the first one matching the lineref
        // i.e. for publishedLineName='525' and lineRef='85:801:2425' 
        // -> matches route_id='96-242-5-j24-1' in DB routes

        $matched_route_id = null;
        while ($db_row = $result->fetchArray(SQLITE3_ASSOC)) {
            $found_route_id_matches = preg_match('/^[0-9]{2}-(.+?)-j[0-9]{2}-[0-9]*$/', $db_row['route_id'], $route_id_matches);
            if (!$found_route_id_matches) {
                // TODO: throw an error instead?
                continue;
            }

            $route_line_ref = $route_id_matches[1];
            $route_line_ref = str_replace('-', '', $route_line_ref);
            if ($route_line_ref === $user_route_line_ref) {
                $matched_route_id = $db_row['route_id'];
                break;
            }
        }

        if (is_null($matched_route_id)) {
            // this can happen for train routes like 85:22:S21 
            // - in this case we have a route_id '91-21-j24-1' - without 'S21'
        }

        $result = $this->query_trips_by_agency_route_short_name($agency_id, $route_short_name, null, $service_day, $matched_route_id);

        return $result;
    }

    public function query_trips_by_agency_for_service_day($agency_id, $service_day) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_trips']));

        $query_config['limit'] = null;

        $agency_id_where = "agency.agency_id = '" . $agency_id . "'";
        array_push($query_config['where'], $agency_id_where);

        $cache_filename_parts = array(
            'query_agency_trips_' . $this->cache_prefix,
            'service_day_' . $service_day,
            'agency_id_' . $agency_id,
        );
        $cache_filename = implode('__', $cache_filename_parts) . '.json';
        $cache_path = $this->app_db_cache_path . '/' . $cache_filename;

        $result = $this->_query_trips($query_config, $service_day, $cache_path);

        return $result;
    }

    public function query_trips_by_agency_route_short_name($agency_id, $route_short_name, $trip_short_name = null, $service_day = null, $route_id = null) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_trips']));

        $agency_id_where = "agency.agency_id = '" . $agency_id . "'";
        array_push($query_config['where'], $agency_id_where);

        if (!is_null($route_id)) {
            $route_id_where = "routes.route_id = '" . $route_id . "'";
            array_push($query_config['where'], $route_id_where);
        }

        $route_short_name_where = "routes.route_short_name = '" . $route_short_name . "'";
        array_push($query_config['where'], $route_short_name_where);

        if (!is_null($trip_short_name)) {
            $trip_short_name_where = "trips.trip_short_name = '" . $trip_short_name . "'";
            array_push($query_config['where'], $trip_short_name_where);
        }

        $result = $this->_query_trips($query_config, $service_day);

        return $result;
    }

    public function query_trips_by_journey_ref($journey_ref = null, $service_day = null) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_trips']));

        $error_result = array(
            'metadata' => array(
                'error' => 'error: n/a',
                
            ),
            'rows' => array(),
        );

        $agency_id = null;
        $trip_short_name = null;

        if (strpos($journey_ref, 'sjyid') !== false) {
            // ch:1:sjyid:100001:730-001
            $journey_ref_parts = explode(':', $journey_ref);
            if (count($journey_ref_parts) < 5) {
                $error_result['metadata']['error'] = 'unexpected journey_ref';
                return $error_result;
            }

            $sboid = 'ch:1:sboid:' . $journey_ref_parts[3];
            if (!array_key_exists($sboid, $this->map_business_organisations)) {
                $error_result['metadata']['error'] = 'cant find sboid: ' . $sboid;
                return $error_result;
            }

            $agency_id = $this->map_business_organisations[$sboid];

            $trip_short_name_parts = explode('-', $journey_ref_parts[4]);
            $trip_short_name = $trip_short_name_parts[0];
        } else {
            $journey_ref_parts = explode(':', $journey_ref);
            // 85:33:4491:001
            if (count($journey_ref_parts) === 4) {
                $agency_id = $journey_ref_parts[1];
                $trip_short_name = $journey_ref_parts[2];
            }
        }

        if (is_null($agency_id)) {
            $error_result['metadata']['error'] = 'cant determine agency_id from ' . $journey_ref;
            return $error_result;
        }
        
        $agency_id_where = "agency.agency_id = '" . $agency_id . "'";
        array_push($query_config['where'], $agency_id_where);

        $trip_short_name_where = "trips.trip_short_name = '" . $trip_short_name . "'";
        array_push($query_config['where'], $trip_short_name_where);

        $result = $this->_query_trips($query_config, $service_day);

        return $result;
    }

    public function query_trips_by_original_trip_id($original_trip_id, $service_day = null) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_trips']));

        $original_trip_id_where = "trips.original_trip_id = '" . $original_trip_id . "'";
        array_push($query_config['where'], $original_trip_id_where);
        
        $result = $this->_query_trips($query_config, $service_day);

        return $result;
    }

    public function query_trips_by_route_id($route_id, $service_day = null) {
        $query_config = unserialize(serialize($this->sql_builder_config['sql_builder']['query_trips']));

        $route_id_where = "trips.route_id = '" . $route_id . "'";
        array_push($query_config['where'], $route_id_where);
        
        $result = $this->_query_trips($query_config, $service_day);

        return $result;
    }

    private function compute_cache_result($cache_path) {
        if (!($this->use_cache && file_exists($cache_path))) {
            return null;
        }
            
        $cache_path_parts = explode('/', $cache_path);
        $cache_filename = $cache_path_parts[count($cache_path_parts) - 1];

        $result_s = file_get_contents($cache_path);
        $result = json_decode($result_s, TRUE);
        $result['metadata']['cache'] = $cache_filename;

        return $result;
    }

    public function query_routes_representative_trip($service_day = null) {
        $sql_path = $this->map_sql_queries['query_routes_representative_trip'];
        $sql = file_get_contents($sql_path);

        $sql_where_items = array();

        if ($service_day !== null) {
            $service_day_where = 'AND ' . $this->_compute_sql_service_day_where($service_day);
            array_push($sql_where_items, $service_day_where);
        }
        
        $sql_where_s = implode("\n", $sql_where_items);
        $sql = str_replace('[EXTRA_WHERE]', $sql_where_s, $sql);

        $cache_filename_parts = array(
            'query_routes_representative_trip_' . $this->cache_prefix,
            'service_day_' . ($service_day ?? 'ALL'),
        );
        $cache_filename = implode('__', $cache_filename_parts) . '.json';
        $cache_path = $this->app_db_cache_path . '/' . $cache_filename;

        $cache_result = $this->compute_cache_result($cache_path);
        if ($cache_result) {
            return $cache_result;
        }

        $result = $this->db->query($sql);

        $result_rows = array();
        while ($db_row = $result->fetchArray(SQLITE3_ASSOC)) {
            array_push($result_rows, $db_row);
        }

        $result = $this->_compute_and_cache_result($sql, $result_rows, $cache_path);

        return $result;
    }

    private function _query_trips($query_config, $service_day = null, $cache_path = null) {
        if ($cache_path !== null) {
            $cache_result = $this->compute_cache_result($cache_path);
            if ($cache_result) {
                return $cache_result;
            }
        }

        if ($service_day !== null) {
            $service_day_where = $this->_compute_sql_service_day_where($service_day);
            array_push($query_config['where'], $service_day_where);
        }

        $sql = $this->build_select_query($query_config);

        $result = $this->db->query($sql);

        $result_rows = array();

        while ($db_row = $result->fetchArray(SQLITE3_ASSOC)) {
            array_push($result_rows, $db_row);
        }

        $result = $this->_compute_and_cache_result($sql, $result_rows, $cache_path);

        return $result;
    }

    private function _compute_sql_service_day_where($service_day) {
        $request_day_date = date_create_from_format("Y-m-d", $service_day);
        $day_idx = $request_day_date->diff($this->gtfs_from_date)->days;

        $service_day_where = file_get_contents($this->map_sql_queries['where_day_bits_day_idx']);
        $service_day_where = str_replace('[DAY_IDX]', $day_idx, $service_day_where);

        return $service_day_where;
    }

    private function _compute_and_cache_result($sql, $result_rows, $cache_path) {
        $result = array(
            'metadata' => array(
                'gtfs_day' => $this->gtfs_db_day,
                
            ),
            'rows' => $result_rows
        );

        if (APP_PROFILE === 'dev') {
            $result['metadata']['sql'] = str_replace("\n", " ", $sql);
        }

        $result['metadata']['rows_no'] = count($result_rows);

        if ($this->use_cache && $cache_path) {
            file_put_contents($cache_path, json_encode($result));
        }

        return $result;
    }
}
