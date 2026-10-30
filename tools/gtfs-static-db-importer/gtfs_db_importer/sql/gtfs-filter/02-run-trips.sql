SELECT 
    trips.* 
FROM 
    trips,
    link_filter_trips
WHERE
    trips.trip_id = link_filter_trips.trip_id;
