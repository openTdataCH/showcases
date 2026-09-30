<?php

$app_profile = 'default';
if (isset($_SERVER) && isset($_SERVER['HTTP_HOST']) && (strpos($_SERVER['HTTP_HOST'], 'localhost') !== -1)) {
    $app_profile = 'dev';
}
define('APP_PROFILE', $app_profile);

error_reporting(E_ALL);
ini_set('memory_limit', '1024M');

if (APP_PROFILE === 'dev') {
    ini_set('display_errors', 1);  
} else {
    ini_set('display_errors', 0);
}

ini_set('max_execution_time', 60);

ini_set('date.timezone', 'Europe/Zurich');

include(APP_PATH . '/inc/libs/yaml/yaml.php');
include(APP_PATH . '/inc/gtfs_db_controller.php');
include(APP_PATH . '/inc/json_view.php');
include(APP_PATH . '/inc/helpers/config.php');

$app_config_path = APP_PATH . "/inc/config.yml";
$app_config = ConfigHelpers::loadConfigAtPath($app_config_path, APP_PATH);

define('APP_CONFIG', $app_config);
