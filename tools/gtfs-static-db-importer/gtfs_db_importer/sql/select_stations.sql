SELECT stop_id AS station_id
FROM stops
WHERE parent_station IS NULL;
