SELECT
    parent_stops.stop_id,
    parent_stops.day_bits,
    GROUP_CONCAT(DISTINCT routes.day_bits) AS routes_day_bits
FROM 
    parent_stops,
    stops,
    stop_times,
    trips,
    routes
WHERE
    parent_stops.stop_id = :stop_id
    AND (stops.parent_station = :stop_id OR stops.stop_id = :stop_id)
    AND stop_times.stop_id = stops.stop_id
    AND trips.trip_id = stop_times.trip_id
    AND routes.route_id = trips.route_id;
