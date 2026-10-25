UPDATE stop_times 
SET 
    [COLUMN_TO_RESET] = NULL 
WHERE 
    ROWID = :table_rowid