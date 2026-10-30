SELECT 
    routes.* 
FROM 
    routes,
    trips,
    link_filter_trips
WHERE
    routes.route_id = trips.route_id
    AND trips.trip_id = link_filter_trips.trip_id
GROUP BY routes.route_id;
