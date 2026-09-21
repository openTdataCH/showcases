import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { GTFS_Static_DB_Catalog_JSON } from '../../shared/models/gtfs_catalog';
import { GTFS_DB_LookupJSON, GTFS_DB_Trips_Response } from '../../shared/types/gtfs/gtfs';
import { AtlasStopsFeatureCollection } from '../../shared/controllers/atlas-data';
import { AtlasOEV_RouteReport } from '../types/_all';

@Injectable({
  providedIn: 'root',
})
export class HTTP_Service {
  constructor(private http: HttpClient) {}

  async fetchLatestGTFSCatalog(): Promise<GTFS_Static_DB_Catalog_JSON> {
    const url = 'https://tools.opentransportdata.swiss/gtfs-static-dbs/gtfs-static-dbs.json';

    const params = new HttpParams()
      .set('rand', Date.now().toString());
    
    return await firstValueFrom(this.http.get<GTFS_Static_DB_Catalog_JSON>(url, { params: params }));
  }

  async fetchBusinessOrganisationsCSV(): Promise<string> {
    const url = 'https://opentdatach.github.io/data/business-organisation-v2/full-business-organisation_LATEST.csv';

    const params = new HttpParams()
      .set('rand', Date.now().toString());

    const response = this.http.get(url, { params: params, responseType: 'text' });
    return await firstValueFrom(response);
  }

  async fetchAtlasLinieCSV(): Promise<string> {
    const url = 'https://opentdatach.github.io/data/line-v2/actual-date-line_LATEST.csv';

    const params = new HttpParams()
      .set('rand', Date.now().toString());

    const response = this.http.get(url, { params: params, responseType: 'text' });
    return await firstValueFrom(response);
  }

  async fetchDBLookups(gtfsDay: string): Promise<GTFS_DB_LookupJSON> {
    const url = 'https://tools.opentransportdata.swiss/gtfs-query/db_lookups';

    const params = new HttpParams()
      .set('rand', Date.now().toString())
      .set('gtfs_day', gtfsDay);

    const response = this.http.get<GTFS_DB_LookupJSON>(url, { params: params} );

    return await firstValueFrom(response);
  }

  async fetchAtlasStopsGeoJSON(): Promise<AtlasStopsFeatureCollection> {
    const url = 'https://tools.opentransportdata.swiss/data/atlas_stops.geojson';

    const params = new HttpParams()
      .set('rand', Date.now().toString());

    const response = this.http.get<AtlasStopsFeatureCollection>(url, { params: params });

    return await firstValueFrom(response);
  }

  async fetchRoutesRepresentativeTrip(gtfsDay: string): Promise<GTFS_DB_Trips_Response> {
    let baseURL = 'https://tools.opentransportdata.swiss/gtfs-query';
    
    const url = baseURL + '/query_routes_representative_trip';

    const params = new HttpParams()
    .set('rand', Date.now().toString())
    .set('gtfs_day', gtfsDay);

    const response = this.http.get<GTFS_DB_Trips_Response>(url, { params: params });

    return await firstValueFrom(response);
  }

  async fetchAtlasOEV_Routes(): Promise<AtlasOEV_RouteReport> {
    const url = 'https://tools.opentransportdata.swiss/data/atlas_oev_report.json';

    const params = new HttpParams()
      .set('rand', Date.now().toString());

    const response = this.http.get<AtlasOEV_RouteReport>(url, { params: params });

    return await firstValueFrom(response);
  }
}
