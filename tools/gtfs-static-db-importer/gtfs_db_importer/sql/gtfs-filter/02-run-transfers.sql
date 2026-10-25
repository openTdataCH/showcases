WITH used_stops AS (
  SELECT DISTINCT stop_id
  FROM 
    stop_times,
    link_filter_trips
  WHERE
    stop_times.trip_id = link_filter_trips.trip_id
)
SELECT 
    transfers.*
FROM 
    transfers
WHERE 
    transfers.from_stop_id IN (SELECT stop_id FROM used_stops)
    AND transfers.to_stop_id IN (SELECT stop_id FROM used_stops);