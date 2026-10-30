SELECT 
    trips.*,
    frequencies.*,
    GROUP_CONCAT(PRINTF(
        '%s|%s|%s|%s', 
        stop_times.ROWID, 
        stop_times.stop_id, 
        stop_times.arrival_time, 
        stop_times.departure_time), 
    ' -- ') AS stop_times_data
FROM 
    trips, 
    stop_times,
    frequencies
WHERE
    trips.trip_id = stop_times.trip_id
    AND trips.trip_id = frequencies.trip_id
GROUP BY trips.trip_id