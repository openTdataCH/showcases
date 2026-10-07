import { Component, OnInit } from '@angular/core';
import { HttpService } from './services/http-service';

import Trip_Variant from './models/hrdf/trip_variant';
import {
  HRDF_DuplicatesAgencyData,
  HRDF_DuplicatesReport,
  HRDF_DuplicateTripsData,
} from './types/hrdf-duplicates-report';

import {
  RenderModel,
  RenderModelAgencyData,
  RenderModelSelectedAgencyData,
  RenderModelVehicleTypeData,
  RenderModelGroupData,
  RenderModelDuplicateTrip,
  RenderModelStopTime,
} from './publication-report.component-interface';
import HRDF_DuplicatesFetchController from './controllers/hrdf-duplicates-fetch-controller';

@Component({
  selector: 'publication-report',
  templateUrl: './publication-report.component.html',
  styleUrls: ['./publication-report.component.scss'],
})
export class PublicationReportComponent implements OnInit {
  private queryParams: URLSearchParams;
  public renderModel: RenderModel;
  private currentDuplicatesReport: HRDF_DuplicatesReport | null;

  constructor(private httpService: HttpService) {
    this.queryParams = new URLSearchParams(document.location.search);
    this.renderModel = {
      currentDay: null,
      reportDays: [],
      agenciesData: [],
      selectedAgency: null,
    };
    this.currentDuplicatesReport = null;
  }

  ngOnInit(): void {
    this.fetchDuplicateDays();
  }

  private fetchDuplicateDays() {
    this.httpService.getDuplicatesList().subscribe((data) => {
      const reportDays = data.hrdf_duplicates_available_days;
      if (reportDays.length > 0) {
        const reportDay = this.queryParams.get('day') ?? reportDays[0];
        this.renderModel.currentDay = reportDay;

        const reportAgencyId = this.queryParams.get('agency_id') ?? '11';
        this.loadReportForDay(reportDay, reportAgencyId);
      }

      this.renderModel.reportDays = reportDays;
    });
  }

  private loadReportForDay(hrdfDay: string, agencyId: string) {
    const fetchController = new HRDF_DuplicatesFetchController(
      this.httpService
    );
    fetchController.fetchDay(hrdfDay, (duplicatesReport) => {
      this.currentDuplicatesReport = duplicatesReport;
      this.parseAgenciesReportToRenderModel(duplicatesReport);

      this.doSelectByAgencyId(duplicatesReport, agencyId);
    });
  }

  private parseAgenciesReportToRenderModel(report: HRDF_DuplicatesReport) {
    this.renderModel.agenciesData = [];

    report.agenciesData.forEach((agencyData) => {
      const agencyDisplayName = this.computeAgencySelectName(agencyData);
      const agencyRenderData: RenderModelAgencyData = {
        agencyId: agencyData.agency.agency_id,
        displayName: agencyDisplayName,
      };
      this.renderModel.agenciesData.push(agencyRenderData);
    });
  }

  private computeAgencySelectName(
    agencyData: HRDF_DuplicatesAgencyData
  ): string {
    const agency = agencyData.agency;
    const hrdf_trips_count = agencyData.tripsData.length;

    let name = agency.agency_code ?? '';
    name += ' (' + agency.agency_id + ')';
    name +=
      ' - ' +
      agency.agency_name +
      ' - ' +
      hrdf_trips_count +
      ' group duplicates';

    return name;
  }

  private doSelectByAgencyId(
    duplicatesReport: HRDF_DuplicatesReport,
    agencyId: string
  ) {
    let agencyData =
      duplicatesReport.agenciesData.find((agencyData) => {
        return agencyData.agency.agency_id === agencyId;
      }) ?? null;

    if (agencyData === null) {
      // The days SELECT was select to an older day that doesnt have the current agency.
      console.error('ERROR cant find agency_id: ' + agencyId);

      // default to the first one in the report
      agencyData = duplicatesReport.agenciesData[0];
      agencyId = agencyData.agency.agency_id;
    }

    const selectedAgencyRenderModel: RenderModelSelectedAgencyData = {
      agencyId: agencyId,
      // mapService: duplicatesReport.serviceData,
      vehiclesTypeData: [],
    };
    this.renderModel.selectedAgency = selectedAgencyRenderModel;

    const mapTripsByVehicleType: Record<string, HRDF_DuplicateTripsData[]> = {};
    agencyData.tripsData.forEach((hrdf_duplicateTripsData) => {
      const vehicle_type_key = hrdf_duplicateTripsData.sortKey;
      if (!(vehicle_type_key in mapTripsByVehicleType)) {
        mapTripsByVehicleType[vehicle_type_key] = [];
      }

      mapTripsByVehicleType[vehicle_type_key].push(hrdf_duplicateTripsData);
    });
    const tripsByVehicleType: HRDF_DuplicateTripsData[][] = Object.values(
      mapTripsByVehicleType
    );

    tripsByVehicleType.forEach((vehicleTypeData, idx) => {
      const renderModelVehicleTypeData = this.computeRenderModelVehicleTypeData(
        vehicleTypeData,
        idx
      );
      selectedAgencyRenderModel.vehiclesTypeData.push(
        renderModelVehicleTypeData
      );
    });
  }

  private computeRenderModelVehicleTypeData(
    vehicleTypeData: HRDF_DuplicateTripsData[],
    idx: number
  ): RenderModelVehicleTypeData {
    const firstTrip = vehicleTypeData[0].hrdfTrips[0];
    let vehicleTypeTitle = firstTrip.vehicleType;
    if (firstTrip.service_line) {
      vehicleTypeTitle += ' ' + firstTrip.service_line;
    }

    const cardBodyId = 'card_level1_body_' + idx;
    const groupsNo = vehicleTypeData.length;
    const groupsNoFormatted =
      groupsNo + ' ' + (groupsNo === 1 ? 'group' : 'groups');

    const renderModelVehicleTypeData: RenderModelVehicleTypeData = {
      cardBodyId: cardBodyId,
      vehicleType: vehicleTypeTitle,
      groupsNoF: groupsNoFormatted,
      groupsData: [],
    };

    vehicleTypeData.forEach((groupData, level2Idx) => {
      const cardBodyId = 'card_level2_body_' + idx + '_' + level2Idx;
      const renderModelGroupData: RenderModelGroupData =
        this.computeRenderModelGroupData(groupData, cardBodyId);
      renderModelVehicleTypeData.groupsData.push(renderModelGroupData);
    });

    return renderModelVehicleTypeData;
  }

  private computeRenderModelGroupData(
    groupData: HRDF_DuplicateTripsData,
    cardBodyId: string
  ): RenderModelGroupData {
    const itemsNo = groupData.hrdfTrips.length;
    const itemsNoFormatted =
      itemsNo + ' ' + (itemsNo === 1 ? 'duplicate' : 'duplicates');

    const renderModelGroupData: RenderModelGroupData = {
      cardBodyId: cardBodyId,
      tripId: groupData.hrdfTripKey,
      duplicatesNoF: itemsNoFormatted,
      duplicateTrips: [],
    };

    groupData.hrdfTrips.forEach((hrdfTrip) => {
      const fplanLineIDx =
        hrdfTrip.fplan_row_idx + '.' + hrdfTrip.service.service_id;

      let fplanType = hrdfTrip.vehicleType;
      if (hrdfTrip.service_line) {
        fplanType += hrdfTrip.service_line;
      }

      const tripMetaCell = this.computeTripMetaCell(hrdfTrip);

      let serviceCell = '';
      if (this.currentDuplicatesReport) {
        serviceCell =
          this.currentDuplicatesReport.serviceData[
            hrdfTrip.service.service_id
          ] ?? '';
      }

      const renderModelDuplicateTrip: RenderModelDuplicateTrip = {
        fplanLineIDx: fplanLineIDx,
        fplanType: fplanType,
        tripMetaCell: tripMetaCell,
        serviceCell: serviceCell,
        stopTimes: [],
        hrdfTrip: hrdfTrip,
      };

      hrdfTrip.stopTimes.forEach((stopTime) => {
        const stopFormatted =
          stopTime.stop.stop_name + ' (' + stopTime.stop.stop_id;

        const renderModelStopTime: RenderModelStopTime = {
          stopF: stopFormatted,
          arrF: stopTime.arrivalTimeS ?? '',
          depF: stopTime.departureTimeS ?? '',
        };
        renderModelDuplicateTrip.stopTimes.push(renderModelStopTime);
      });

      renderModelGroupData.duplicateTrips.push(renderModelDuplicateTrip);
    });

    return renderModelGroupData;
  }

  private computeTripMetaCell(hrdf_trip: Trip_Variant) {
    const service_id = hrdf_trip.service.service_id;

    const trip_stop_ids: string[] = [];
    hrdf_trip.stopTimes.forEach((stop_time) => {
      trip_stop_ids.push(stop_time.stop.stop_id);
    });

    const fplan_content_meta_rows: string[] = [];

    const fplan_content_rows = hrdf_trip.fplan_content.split('\n');
    fplan_content_rows.forEach((fplan_content_row) => {
      const isMeta = fplan_content_row[0] === '*';
      const isStopTime = !isMeta;

      let isDifferentVariant = false;

      const isAVE = fplan_content_row.substring(0, 5) === '*A VE';
      if (isAVE) {
        const hasCalendarService = fplan_content_row.indexOf(service_id) !== -1;
        if (!hasCalendarService) {
          isDifferentVariant = true;
        }
      }

      if (isStopTime) {
        const fplan_content_stop_id = fplan_content_row.substring(0, 7);
        if (!trip_stop_ids.includes(fplan_content_stop_id)) {
          isDifferentVariant = true;
        }
      }

      // TODO - remove prefix until we have a better viz
      // if (isDifferentVariant) {
      //   fplan_content_row = '=> different variant ··· ' + fplan_content_row;
      // }

      const meta_row = fplan_content_row;
      fplan_content_meta_rows.push(meta_row);
    });

    const fplan_content_meta_HTML = fplan_content_meta_rows.join('\n');

    return fplan_content_meta_HTML;
  }

  public handleAgencyChange() {
    const agencyId = this.renderModel.selectedAgency?.agencyId ?? null;
    if (agencyId === null) {
      return;
    }

    if (this.currentDuplicatesReport === null) {
      return;
    }

    this.doSelectByAgencyId(this.currentDuplicatesReport, agencyId);
  }

  public handleDayChange() {
    const currentDay = this.renderModel.currentDay;
    const currentAgencyId = this.renderModel.selectedAgency?.agencyId ?? '11';

    if (currentDay) {
      this.renderModel.agenciesData = [];
      this.renderModel.selectedAgency = null;
      this.loadReportForDay(currentDay, currentAgencyId);
    }
  }
}
