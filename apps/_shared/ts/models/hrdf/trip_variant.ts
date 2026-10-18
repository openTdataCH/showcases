import { HRDF_Stop_Time_DB } from "../../types/hrdf/stop_time_db";
import { HRDF_Trip_Variant_DB } from "../../types/hrdf/trip_variant_db";

import Agency from "../gtfs/agency";
import Calendar from "../gtfs/calendar";
import Stop from "../gtfs/stop";
import StopTime from "../gtfs/stop_time";

export default class Trip_Variant {
    public fplan_row_idx: number
    
    public agency: Agency
    public service: Calendar
    
    public fplan_trip_id: string
    public service_line: string | null
    public vehicleType: string
    public from_stop: Stop
    public to_stop: Stop

    public stopTimes: StopTime[]

    public fplan_content: string

    constructor(fplan_row_idx: number, agency: Agency, service: Calendar, fplan_trip_id: string, service_line: string | null, vehicle_type: string, from_stop: Stop, to_stop: Stop, stop_times: StopTime[], fplan_content: string) {
        this.fplan_row_idx = fplan_row_idx

        this.agency = agency
        this.service = service
        
        this.fplan_trip_id = fplan_trip_id
        this.service_line = service_line
        this.vehicleType = vehicle_type
        this.from_stop = from_stop
        this.to_stop = to_stop

        this.stopTimes = stop_times

        this.fplan_content = fplan_content
    }

    public static initFromTripVariantDB(tripVariantDB: HRDF_Trip_Variant_DB, mapAgency: Record<string, Agency>, mapCalendarService: Record<string, Calendar>, mapStops: Record<string, Stop>) {
        const fplan_row_idx = tripVariantDB.fplan_row_idx

        const agency = mapAgency[tripVariantDB.agency_id]
        const service = mapCalendarService[tripVariantDB.service_id]

        const fplan_trip_id = tripVariantDB.fplan_trip_id
        const service_line = tripVariantDB.service_line
        const vehicle_type = tripVariantDB.vehicle_type

        const fromStop = mapStops[tripVariantDB.from_stop_id]
        const toStop = mapStops[tripVariantDB.from_stop_id]

        const stopTimes: StopTime[] = [];
        const tripStops: HRDF_Stop_Time_DB[] = tripVariantDB.stops ?? [];
        tripStops.forEach(stopTimeDB => {
            const stop = mapStops[stopTimeDB.stop_id]
            const stopTime = StopTime.initFromHRDFStopTimeDB(stopTimeDB, stop)
            stopTimes.push(stopTime);
        });

        const fplan_content = tripVariantDB.fplan_content

        const trip = new Trip_Variant(fplan_row_idx, agency, service, fplan_trip_id, service_line, vehicle_type, fromStop, toStop, stopTimes, fplan_content);

        return trip
    }
}
