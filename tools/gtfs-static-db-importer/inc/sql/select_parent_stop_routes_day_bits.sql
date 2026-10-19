WITH stop_parents AS (
    SELECT
        stop_id,
        COALESCE(parent_station, stop_id) AS parent_stop_id
    FROM stops
)
SELECT
    parent_stops.stop_id,
    parent_stops.day_bits,
    GROUP_CONCAT(DISTINCT routes.day_bits) AS routes_day_bits
FROM 
    parent_stops,
    stop_parents,
    stop_times,
    trips,
    routes
WHERE
    stop_parents.parent_stop_id = parent_stops.stop_id
    AND stop_times.stop_id = stop_parents.stop_id
    AND trips.trip_id = stop_times.trip_id
    AND routes.route_id = trips.route_id
GROUP BY parent_stops.stop_id;
