import Trip_Variant from "./models/hrdf/trip_variant";

export interface RenderModel {
  currentDay: string | null
  reportDays: string[];
  agenciesData: RenderModelAgencyData[];
  selectedAgency: RenderModelSelectedAgencyData | null;
}

export interface RenderModelAgencyData {
  agencyId: string;
  displayName: string;
}

export interface RenderModelSelectedAgencyData {
  agencyId: string;
  shownGroupCount: number;
  totalGroupCount: number;
  vehiclesTypeData: RenderModelVehicleTypeData[];
}

export interface RenderModelVehicleTypeData {
  cardBodyId: string;
  vehicleType: string;
  groupsNoF: string;
  groupsData: RenderModelGroupData[];
}

export interface RenderModelGroupData {
  cardBodyId: string;
  tripId: string;
  duplicatesNoF: string;
  duplicateTrips: RenderModelDuplicateTrip[];
}

export interface RenderModelDuplicateTrip {
  fplanLineIDx: string;
  fplanType: string;
  tripMetaCell: string;
  serviceCell: string;
  stopTimes: RenderModelStopTime[];
  hrdfTrip: Trip_Variant;
}

export interface RenderModelStopTime {
  stopF: string;
  arrF: string;
  depF: string;
}
