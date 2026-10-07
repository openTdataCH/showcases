import { HttpService } from "../services/http-service";

import Trip_Variant from "../models/hrdf/trip_variant";
import { HRDF_DB_LookupsResponse } from "../types/hrdf-db-lookups-response";
import { HRDF_DuplicatesAgencyData, HRDF_DuplicatesReport, HRDF_DuplicateTripsData } from "../types/hrdf-duplicates-report";
import { HRDF_DuplicatesReportResponse } from "../types/hrdf-duplicates-report-response";
import HRDF_DB_Lookups_Controller from "./hrdf-db-lookups-controller";

export default class HRDF_DuplicatesFetchController {
  constructor(private httpService: HttpService) {
    
  }

  public fetchDay(hrdfDay: string, completion: (report: HRDF_DuplicatesReport) => void) {
    this.httpService.getHRDF_DBLookup(hrdfDay).subscribe((dbData) => {
      this.httpService
        .getHRDF_DuplicatesReport(hrdfDay)
        .subscribe((reportData) => {
          const report = this.parseHRDF_DuplicatesResponse(
            reportData,
            dbData
          );

          completion(report);
        });
    });
  }

  private parseHRDF_DuplicatesResponse(
    reportData: HRDF_DuplicatesReportResponse,
    dbData: HRDF_DB_LookupsResponse
  ): HRDF_DuplicatesReport {
    const mapHRDF_Lookups =
      HRDF_DB_Lookups_Controller.initFromDBLookups(dbData);

    const duplicatesReport: HRDF_DuplicatesReport = {
      agenciesData: [],
      serviceData: reportData.service_data,
    };

    for (const [agency_id, mapAgencyTripsData] of Object.entries(
      reportData.agency_data
    )) {
      const agencyTripsData: HRDF_DuplicateTripsData[] = [];

      for (const [hrdfTripKey, fplanRowIndices] of Object.entries(
        mapAgencyTripsData
      )) {
        const hrdfTrips: Trip_Variant[] = [];

        fplanRowIndices.forEach((fplan_row_idx) => {
          const hrdf_trip_db = reportData.map_hrdf_trips[fplan_row_idx];
          const hrdf_trip = Trip_Variant.initFromTripVariantDB(
            hrdf_trip_db,
            mapHRDF_Lookups.agency,
            mapHRDF_Lookups.calendar,
            mapHRDF_Lookups.stops
          );
          hrdfTrips.push(hrdf_trip);
        });

        if (hrdfTrips.length === 0) {
          console.log('ERROR - no trips for the agency?');
          console.log(agencyTripsData);
          return duplicatesReport;
        }

        const firstTrip = hrdfTrips[0];

        // Sort by vehicle type + line number (numerically)
        let sortKey = firstTrip.vehicleType;

        if (firstTrip.service_line) {
          const digits_matches = firstTrip.service_line.match(/\d+/);
          const digits_matches_s = digits_matches ? digits_matches[0] : '';

          let repeat_no = 5 - digits_matches_s.length;
          if (repeat_no < 0) {
            repeat_no = 0;
          }

          const sort_key_line =
            '0'.repeat(repeat_no) +
            digits_matches_s +
            '_' +
            firstTrip.service_line;
          sortKey += '_' + sort_key_line;
        }

        const hrdf_duplicate_trips_data: HRDF_DuplicateTripsData = {
          hrdfTripKey: hrdfTripKey,
          sortKey: sortKey,
          hrdfTrips: hrdfTrips,
        };
        agencyTripsData.push(hrdf_duplicate_trips_data);
      }

      agencyTripsData.sort((a, b) => {
        if (a.sortKey < b.sortKey) return -1;
        if (a.sortKey < b.sortKey) return 1;
        return 0;
      });

      const agency = mapHRDF_Lookups.agency[agency_id];
      const sort_key = agency.agency_code ?? 'n/a';
      const agency_data: HRDF_DuplicatesAgencyData = {
        agency: agency,
        sortKey: sort_key,
        tripsData: agencyTripsData,
        totalGroupCount: reportData.agency_total_group_counts?.[agency_id] ?? agencyTripsData.length,
      };

      duplicatesReport.agenciesData.push(agency_data);
    }

    duplicatesReport.agenciesData.sort((a, b) => {
      if (a.sortKey < b.sortKey) return -1;
      if (a.sortKey < b.sortKey) return 1;
      return 0;
    });

    return duplicatesReport;
  }
}
