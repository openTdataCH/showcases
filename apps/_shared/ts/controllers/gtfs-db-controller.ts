import { GTFS_DB_LookupJSON } from '../types/gtfs/gtfs';

import Agency from '../models/gtfs/agency';
import Route from '../models/gtfs/route';
import Stop from '../models/gtfs/stop';

export class GTFS_DB_Controller {
  public gtfsDay: string
  public mapAgency: Record<string, Agency>
  public mapRoutes: Record<string, Route>
  public mapStops: Record<string, Stop>

  constructor(gtfsDay: string) {
    this.gtfsDay = gtfsDay;
    this.mapAgency = {};
    this.mapRoutes = {};
    this.mapStops = {};
  }

  loadDBLookups(lookupJSON: GTFS_DB_LookupJSON) {
    this.mapAgency = {};
    lookupJSON.agency.rows.forEach(itemJSON => {
      const agency = Agency.initFromAgencyJSON(itemJSON);
      this.mapAgency[agency.agency_id] = agency;
    });

    this.mapRoutes = {};
    lookupJSON.routes.rows.forEach(itemJSON => {
      try {
        const route = Route.initFromJSON(itemJSON, this.mapAgency);
        this.mapRoutes[route.route_id] = route;
      } catch (error) {
        console.log('Route cannot be initialized', itemJSON, error);
      }
    });

    this.mapStops = {};
    lookupJSON.stops.rows.forEach(itemJSON => {
      const stop = Stop.initFromJSON(itemJSON);
      this.mapStops[stop.stop_id] = stop;
    });
  }
}
