SELECT 
    agency.* 
FROM 
    agency, 
    routes, 
    trips, 
    link_filter_trips
WHERE
    agency.agency_id = routes.agency_id
    AND routes.route_id = trips.route_id
    AND trips.trip_id = link_filter_trips.trip_id
GROUP BY agency.agency_id
