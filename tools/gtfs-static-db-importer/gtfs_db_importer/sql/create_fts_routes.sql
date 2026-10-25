DROP TABLE IF EXISTS fts_routes;

-- fts5 is not supported by PHP 7.x
-- CREATE VIRTUAL TABLE fts_routes USING fts5(route_id, trip_stop_ids);
CREATE VIRTUAL TABLE fts_routes USING fts3(route_id, trip_stop_ids);

-- populate routes with distinct stops
INSERT INTO fts_routes (route_id, trip_stop_ids)
SELECT
	trips.route_id,
	GROUP_CONCAT(DISTINCT stops_main.stop_id)
FROM
	trips, stop_times, stops, stops AS stops_main
WHERE
	trips.trip_id = stop_times.trip_id 
	AND stop_times.stop_id = stops.stop_id	
	AND stops.location_type != 1
	AND stops.parent_station = stops_main.stop_id 
GROUP BY trips.route_id;
