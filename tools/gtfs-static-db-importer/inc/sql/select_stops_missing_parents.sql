SELECT
    child.stop_id,
    child.parent_station
FROM stops AS child
WHERE child.parent_station IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM stops AS parent
        WHERE parent.stop_id = child.parent_station
    )
LIMIT 1;
