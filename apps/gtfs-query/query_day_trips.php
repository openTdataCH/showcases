<?php
define('APP_PATH', dirname(__FILE__));
include(APP_PATH . '/inc/common.php');

$gtfs_day = @$_GET['gtfs_day'] ?: null;
if ($gtfs_day === null) {
    print('error - gtfs_day is null');
    exit(1);
}

$day = @$_GET['day'] ?: date('Y-m-d');
$filter_agency_ids_s = @$_GET['filter_agency_ids'] ?: 'HAS_GTFS_RT';
$fields_key_s = @$_GET['fields_profile'] ?: 'fields_query_day_light_trips';

$gtfs_controller = new GTFS_DB_Controller(APP_CONFIG, $gtfs_day);
$result_json = $gtfs_controller->query_day_trips($fields_key_s, $day, $filter_agency_ids_s);

JsonView::dump($result_json);

