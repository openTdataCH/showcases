<?php
define('APP_PATH', dirname(__FILE__));
include(APP_PATH . '/inc/common.php');

$gtfs_day = @$_GET['gtfs_day'] ?: null;
if ($gtfs_day === null) {
    print('error - gtfs_day is null');
    exit(1);
}

$day = @$_GET['day'] ?: date('Y-m-d');
$from_hhmm = @$_GET['from_hhmm'] ?: date('Hi');
$to_hhmm = @$_GET['to_hhmm'] ?: date('Hi');

$filter_agency_ids_s = @$_GET['filter_agency_ids'] ?: 'HAS_GTFS_RT';
$row_format_s = @$_GET['row_format'] ?: 'object';

$gtfs_controller = new GTFS_DB_Controller(APP_CONFIG, $gtfs_day);
$result_json = $gtfs_controller->query_day_trips('query_day_full_trips', $row_format_s, $day, $filter_agency_ids_s, $from_hhmm, $to_hhmm);

JsonView::dump($result_json);

