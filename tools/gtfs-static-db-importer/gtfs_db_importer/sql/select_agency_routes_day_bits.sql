SELECT
    routes.agency_id,
    GROUP_CONCAT(routes.day_bits) AS routes_day_bits
FROM
    routes
GROUP BY routes.agency_id;
