import { HRDF_Trip_Variant_DB } from "../types/hrdf/trip_variant_db"

export interface HRDF_DuplicatesReportResponse {
    agency_data: Record<string, Record<string, number[]>>
    agency_total_group_counts?: Record<string, number>
    map_hrdf_trips: Record<number, HRDF_Trip_Variant_DB>
    service_data: Record<string, string>
}
