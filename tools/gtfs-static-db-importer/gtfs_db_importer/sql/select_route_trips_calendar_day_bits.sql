SELECT
    trips.route_id,
    GROUP_CONCAT(calendar.day_bits) AS trips_day_bits
FROM
    trips, calendar
WHERE
    trips.service_id = calendar.service_id
GROUP BY trips.route_id;
