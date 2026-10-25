SELECT 
    calendar_dates.* 
FROM 
    calendar_dates
WHERE
    calendar_dates.service_id IN 
    (
        SELECT 
            trips.service_id 
        FROM 
            trips,
            link_filter_trips
        WHERE
            trips.trip_id = link_filter_trips.trip_id
    );
