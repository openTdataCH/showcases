INSERT INTO link_filter_trips

SELECT 
    stop_times.trip_id 
FROM 
    stop_times, 
    stops, 
    trips, 
    routes
WHERE 
    stop_times.stop_id = stops.stop_id
    AND stop_times.trip_id = trips.trip_id
    AND trips.route_id = routes.route_id

[WHERE_FILTERS]
    
GROUP BY stop_times.trip_id;
