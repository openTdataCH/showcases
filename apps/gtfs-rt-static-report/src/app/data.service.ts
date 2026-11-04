import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { GTFS_RT_Static_Monthly_Report_JSON, GTFS_RT_Static_Report } from './types/_all';
import { Response_GTFS_RT } from './models/gtfs-rt/gtfs-rt-response';
import { GTFS_DB_LookupAgency, GTFS_DB_LookupRoutes } from './models/gtfs/gtfs';
import { BusinessOrganisationsController } from './controllers/business-organisations';

@Injectable({
  providedIn: 'root'
})
export class DataService {
  public businessOrganisationsController: BusinessOrganisationsController;

  constructor(private http: HttpClient) {
    this.businessOrganisationsController = new BusinessOrganisationsController();
  }

  public async fetchBusinessOrganisationsCSV(): Promise<string> {
    const url = 'https://opentdatach.github.io/data/business-organisation-v2/full-business-organisation_LATEST.csv';
    const params = { rand: Date.now().toString() };
    const csv = await firstValueFrom(this.http.get(url, { params: params, responseType: 'text' }));
    return csv;
  }

  async getMonthlyReport(dateYM: string): Promise<GTFS_RT_Static_Monthly_Report_JSON> {
    const dateYMParts = dateYM.split('-');

    const now = new Date();

    let url = 'https://tools.opentransportdata.swiss/gtfs-rt-static-compare-report/[YYYY]/gtfs_rt_static_report-[YYYY-MM].json?ts=' + now.getTime();
    url = url.replace('[YYYY]', dateYMParts[0]);
    url = url.replace('[YYYY-MM]', dateYM);
    
    return await firstValueFrom(this.http.get<GTFS_RT_Static_Monthly_Report_JSON>(url));
  }

  public async fetchGTFS_RT_Snapshot(url: string): Promise<Response_GTFS_RT> {
    const gtfsRT_SnapshotJSON = await firstValueFrom(this.http.get<Response_GTFS_RT>(url));
    return gtfsRT_SnapshotJSON;
  }

  public async fetchGTFS_RT_StaticReport(url: string): Promise<GTFS_RT_Static_Report> {
    const json = await firstValueFrom(this.http.get<GTFS_RT_Static_Report>(url));
    return json;
  }

  // https://tools.opentransportdata.swiss/gtfs-query/lookup/routes?gtfs_day=2026-03-07
  public async fetchGTFS_Routes(gtfsDay: string): Promise<GTFS_DB_LookupRoutes> {
    const url = 'https://tools.opentransportdata.swiss/gtfs-query/lookup/routes?gtfs_day=' + gtfsDay;
    const response = await firstValueFrom(this.http.get<GTFS_DB_LookupRoutes>(url));
    return response;
  }

  // https://tools.opentransportdata.swiss/gtfs-query/lookup/agency?gtfs_day=2026-03-07
  public async fetchGTFS_Agency(gtfsDay: string): Promise<GTFS_DB_LookupAgency> {
    const url = 'https://tools.opentransportdata.swiss/gtfs-query/lookup/agency?gtfs_day=' + gtfsDay;
    const response = await firstValueFrom(this.http.get<GTFS_DB_LookupAgency>(url));
    return response;
  }
}
