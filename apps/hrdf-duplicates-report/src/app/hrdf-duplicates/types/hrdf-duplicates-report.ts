import Agency from "../models/gtfs/agency";
import Trip_Variant from "../models/hrdf/trip_variant";

export interface HRDF_DuplicatesReport {
    agenciesData: HRDF_DuplicatesAgencyData[],
    serviceData: Record<string, string>
}

export interface HRDF_DuplicatesAgencyData {
    agency: Agency
    sortKey: string
    tripsData: HRDF_DuplicateTripsData[]
    totalGroupCount: number
}

export interface HRDF_DuplicateTripsData {
    hrdfTripKey: string
    sortKey: string
    hrdfTrips: Trip_Variant[]
}
