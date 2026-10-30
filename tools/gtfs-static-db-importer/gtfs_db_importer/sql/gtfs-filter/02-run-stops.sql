WITH used_parent_stops AS (
    SELECT DISTINCT parent_station
    FROM stops
    WHERE stop_id IN (
        SELECT DISTINCT stop_id
        FROM stop_times
        WHERE trip_id IN (SELECT trip_id FROM link_filter_trips)
    )
)
SELECT 
    stops.*
FROM 
    stops
WHERE
(
    stops.stop_id IN used_parent_stops
    OR stops.parent_station IN used_parent_stops
)