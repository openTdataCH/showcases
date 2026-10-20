SELECT
    stations.station_id,
    stations.day_bits,
    GROUP_CONCAT(DISTINCT routes.day_bits) AS routes_day_bits
FROM 
    stations,
    stops,
    stop_times,
    trips,
    routes
WHERE
    stations.station_id = :station_id
    AND (stops.parent_station = :station_id OR stops.stop_id = :station_id)
    AND stop_times.stop_id = stops.stop_id
    AND trips.trip_id = stop_times.trip_id
    AND routes.route_id = trips.route_id;
