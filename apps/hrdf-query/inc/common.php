<?php

$app_profile = 'default';
if (isset($_SERVER) && isset($_SERVER['HTTP_HOST']) && (strpos($_SERVER['HTTP_HOST'], 'localhost') !== false)) {
    $app_profile = 'dev';
}

define('APP_PROFILE', $app_profile);

error_reporting(E_ALL);

if (APP_PROFILE === 'dev') {
    ini_set('display_errors', 1);  
} else {
    ini_set('display_errors', 0);
}

ini_set('date.timezone', 'Europe/Zurich');

include(APP_PATH . '/inc/libs/yaml/yaml.php');
include(APP_PATH . '/inc/hrdf_db_controller.php');
include(APP_PATH . '/inc/json_view.php');

$app_config_path = APP_PATH . "/inc/config.yml";

$app_config_s = file_get_contents($app_config_path);
$app_config_s = str_replace('[APP_PATH]', APP_PATH, $app_config_s);
$yaml = new Yaml();
$app_config = $yaml->loadString($app_config_s);

define('APP_CONFIG', $app_config);