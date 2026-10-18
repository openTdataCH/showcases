<?php

class HRDF_DB_Controller {
    var $is_dev;
    var $request_URI;
    
    var $hrdf_day;
    var $db_path;

    var $meta_hrdf_dbs_json;
    var $map_resources;

    var $map_app_db_cache_paths;
    var $use_cache;
    var $cache_prefix;

    function __construct($config, $hrdf_day) {
        $this->is_dev = APP_PROFILE === 'dev';
        $this->request_URI = $_SERVER['REQUEST_URI'];

        $meta_hrdf_dbs_json = $this->compute_meta_hrdf_dbs($config);
        $hrdf_available_days = array_keys($meta_hrdf_dbs_json);
        rsort($hrdf_available_days);
        if (count($hrdf_available_days) === 0) {
            $message = array(
                "error" => "No HRDF DBs available",
            );
            JsonView::dump_error('400', $message);
            die;
        }

        if ($hrdf_day === 'latest') {
            $hrdf_day = $hrdf_available_days[0];
        } else {
            if (!in_array($hrdf_day, $hrdf_available_days)) {
                $message = array(
                    "error" => "No DB found for " . $hrdf_day,
                );
                JsonView::dump_error('400', $message);
                die;
            }
        }

        $this->hrdf_day = $hrdf_day;
        $this->db_path = $config['map_resources']['hrdf_db']['base_path'] . '/' . $meta_hrdf_dbs_json[$hrdf_day]['file'];

        $this->meta_hrdf_dbs_json = $meta_hrdf_dbs_json;
        $this->map_resources = $config['map_resources'];
        
        $this->map_app_db_cache_paths = $config['map_app_db_cache_paths'];

        $this->use_cache = TRUE;

        $this->cache_prefix = 'v1';
    }

    public function compute_hrdf_duplicates_list() {
        $resource_json_path = $this->map_app_db_cache_paths['meta_hrdf_duplicates_json'];

        $meta_hrdf_duplicates_json = $this->compute_fetch_meta_resource(
            $resource_json_path, 
            $this->map_resources['hrdf_duplicates']
        );

        $resource_keys = array_keys($meta_hrdf_duplicates_json);
        rsort($resource_keys);

        $meta_json = array(
            'hrdf_duplicates_available_days' => $resource_keys,
        );
        
        return $meta_json;
    }

    private function compute_meta_hrdf_dbs($config) {
        $meta_hrdf_dbs_json_path = $config['map_app_db_cache_paths']['meta_hrdf_dbs_json'];

        $meta_hrdf_dbs_json = $this->compute_fetch_meta_resource(
            $meta_hrdf_dbs_json_path, 
            $config['map_resources']['hrdf_db']
        );

        return $meta_hrdf_dbs_json;
    }

    private function compute_fetch_meta_resource($resource_json_path, $resource_config, $cache_ttl = 60) {
        if ($this->use_cache && file_exists($resource_json_path)) {
            $file_ts = filemtime($resource_json_path);
            $now_ts = time();
            $file_age = $now_ts - $file_ts;
            if ($file_age < $cache_ttl) {
                $resource_json = json_decode(file_get_contents($resource_json_path), TRUE);
                return $resource_json;
            }
        }

        $resource_json = $this->fetch_resource_files($resource_config);

        if ($this->use_cache) {
            file_put_contents($resource_json_path, json_encode($resource_json));
        }

        return $resource_json;
    }

    private function fetch_resource_files($resource_config) {
        $resource_items = array();

        $resources_folder_path = $resource_config['base_path'];
        $resource_files = scandir($resources_folder_path);
        foreach($resource_files as $resource_file) {
            $resource_matched = preg_match($resource_config['filename_regexp'], $resource_file, $resource_file_matches);
            if ($resource_matched !== 1) {
                continue;
            }

            $resource_path = $resources_folder_path . '/' . $resource_file;
            if (!is_file($resource_path) || !is_readable($resource_path)) {
                continue;
            }

            if (strtolower(pathinfo($resource_file, PATHINFO_EXTENSION)) === 'json') {
                $resource_size = filesize($resource_path);
                // discard 0, none files
                if (!$resource_size) {
                    continue;
                }
            }

            $resource_item = array(
                'file' => $resource_file,
            );

            foreach ($resource_file_matches as $key => $val) {
                if (is_numeric($key)) {
                    continue;
                }

                $resource_item[$key] = $val;
            }

            $resource_pk = $resource_item[$resource_config['resource_pk']];
            $resource_items[$resource_pk] = $resource_item;
        }

        return $resource_items;
    }
}
