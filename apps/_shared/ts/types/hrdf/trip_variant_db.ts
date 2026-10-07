import { HRDF_Stop_Time_DB } from "./stop_time_db"

export interface HRDF_Trip_Variant_DB {
    agency_id: string
    fplan_content: string
    fplan_row_idx: number
    fplan_trip_id: string
    from_stop_id: string
    to_stop_id: string
    service_id: string
    service_line: string | null
    vehicle_type: string
    stops: HRDF_Stop_Time_DB[]
}
