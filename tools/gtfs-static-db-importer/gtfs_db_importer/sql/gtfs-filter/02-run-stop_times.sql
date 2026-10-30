SELECT 
    stop_times.* 
FROM 
    stop_times,
    link_filter_trips
WHERE
    stop_times.trip_id = link_filter_trips.trip_id;
