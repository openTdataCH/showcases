UPDATE routes SET representative_trip_id = 
(
	SELECT 
	    trips.trip_id
	    FROM trips, calendar
	    WHERE 
	        trips.route_id = routes.route_id
	        AND trips.service_id = calendar.service_id
	    GROUP BY trips.trip_id
	    ORDER BY (
	        -- most calendar days (values: 0..360) * 10 (for normalisation)
	        LENGTH(REPLACE(calendar.day_bits, '0', '')) * 10
	        + 
	        -- max number of stops (max in ch is 80)
	        trips.stop_times_count
	    ) DESC
	LIMIT 1
)