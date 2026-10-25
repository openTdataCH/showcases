SELECT 
    calendar.service_id, 

    calendar.start_date,
    calendar.end_date,
    calendar.sunday, 
    calendar.monday, 
    calendar.tuesday, 
    calendar.wednesday, 
    calendar.thursday, 
    calendar.friday, 
    calendar.saturday,

    COUNT(calendar_dates.ROWID) AS calendar_dates_cno,
    GROUP_CONCAT(
        PRINTF('%s|%s', calendar_dates.date, calendar_dates.exception_type)
    ) AS exception_dates
FROM calendar 
LEFT JOIN calendar_dates ON calendar.service_id = calendar_dates.service_id 
GROUP BY calendar.service_id