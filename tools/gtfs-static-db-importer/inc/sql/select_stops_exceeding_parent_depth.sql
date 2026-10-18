SELECT
    child.stop_id,
    parent.stop_id AS parent_stop_id,
    parent.parent_station AS grandparent_stop_id
FROM stops AS child
JOIN stops AS parent ON parent.stop_id = child.parent_station
WHERE TRIM(parent.parent_station) <> ''
LIMIT 1;
