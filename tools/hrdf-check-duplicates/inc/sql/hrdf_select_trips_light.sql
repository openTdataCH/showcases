-- SAME as ./hrdf_select_trips.sql but with fewer JOINs / fieldnames
SELECT 
    fplan_trip_bitfeld.fplan_row_idx,
    fplan.agency_id,
    fplan.vehicle_type,
    fplan.service_line,
    fplan.fplan_trip_id,
    fplan.fplan_content,
    fplan_trip_bitfeld.service_id
FROM 
    fplan, 
    fplan_trip_bitfeld
WHERE 
    fplan.row_idx = fplan_trip_bitfeld.fplan_row_idx
    [EXTRA_WHERE]

GROUP BY fplan_trip_bitfeld.fplan_trip_bitfeld_id;
