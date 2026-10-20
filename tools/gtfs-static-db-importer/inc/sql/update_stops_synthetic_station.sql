UPDATE stops
SET parent_station = stop_id
WHERE location_type = 0
    AND parent_station IS NULL
    AND EXISTS (
        SELECT 1
        FROM stations
        WHERE stations.station_id = stops.stop_id
    );
