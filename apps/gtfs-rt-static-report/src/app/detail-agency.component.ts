import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { DateHelpers } from './helpers/date-helpers';
import { FilenameDateRegexp, ReportHelpers } from './helpers/report-helpers';

import { DataService } from './data.service';

import { AgencyJSON } from './models/gtfs/gtfs';
import { GTFS_RT_Static_Monthly_Report_JSON, GTFS_RT_Static_Report, GTFS_RT_Static_Report_Metadata_JSON } from './types/_all';

interface DetailReportRow {
  agency: AgencyJSON,
  valueNow: {
    gtfsRt: number,
    gtfsStatic: number,
    coverage: number,
    coverageClass: string,
  },
  valuePrev: {
    gtfsRt: number,
    gtfsStatic: number,
    coverage: number,
    coverageClass: string,
  },
  computed: {
    rtDiff: number,
    deltaDiff: number,
  }
};

type SortColumn = 'name' | 'keyA' | 'keyB' | 'rt-diff' | 'delta-diff';
type SortDirection = 'asc' | 'desc';

interface PageModel {
  reportRows: DetailReportRow[],
  keyA: string,
  prevKeyB: string,
  agencyRows: AgencyJSON[],
  compareKeys: string[],
  sort: {
    column: SortColumn,
    direction: SortDirection,
  },
  reportMetadata: GTFS_RT_Static_Report_Metadata_JSON | null,
};

// 2026-03-09-1200
type HrReportKey = string;

interface MapAgencyReportData {
  id: string,
  agencyJSON: AgencyJSON,
  gtfsRtActiveNo: number,
  gtfsStaticActiveNo: number,
};
type MapDaysData = Record<HrReportKey, Record<string, MapAgencyReportData>>;

@Component({
  selector: 'app-detail-agency',
  templateUrl: './detail-agency.component.html',
  styleUrls: ['./detail-agency.component.scss']
})
export class DetailAgencyComponent implements OnInit {
  public readonly realtimeTripsTooltip = 'Fahrten mit Echtzeitmeldungen / Erwartete Fahrten gemäss GTFS-Static (letzte Stunde)';
  public tooltip = {
    visible: false,
    x: 0,
    y: 0,
  };

  private mapGTFS_Agency: Record<string, Record<string, AgencyJSON>>;
  private mapDaysData: MapDaysData;
  public model: PageModel;

  constructor(private route: ActivatedRoute, private dataService: DataService) {
    this.mapGTFS_Agency = {};
    this.mapDaysData = {};
    this.model = {
      reportRows: [],
      keyA: 'n/a',
      prevKeyB: '... loading',
      agencyRows: [],
      compareKeys: ['... loading'],
      sort: {
        column: 'rt-diff',
        direction: 'asc',
      },
      reportMetadata: null,
    };
  }

  async ngOnInit(): Promise<void> {
    this.route.paramMap.subscribe(async (params) => {
      const userReportId = params.get('id');
      this.model.keyA = this.massageReportDate(userReportId);
      await this.fetchData();
    });
  }

  private massageReportDate(s: string | null): string {
    if (s === null) {
      // YYYY-MM-DD HH:MM:SS
      s = DateHelpers.formatDate();
    }

    s = s.replaceAll(':', '');
    s = s.replaceAll(' ', '-');

    // 2026-03-11-1053
    s = s.substring(0, 15);

    return s;
  }

  private updateSelectedReportCell(monthlyReport: GTFS_RT_Static_Monthly_Report_JSON, dayF: string, hrMinF: string) {
    if (!(dayF in monthlyReport.report_days)) {
      console.log('error updateSelectedReportCell - cant find day ' + dayF  + ' in monthlyReport.report_days');
      return;
    }
    if (!(hrMinF in monthlyReport.report_days[dayF])) {
      console.log('error updateSelectedReportCell - cant find hrMinF ' + hrMinF  + ' in monthlyReport.report_days');
      return;
    }

    this.model.reportMetadata = monthlyReport.report_days[dayF][hrMinF];
  }

  private async fetchData() {
    const reportKey = this.model.keyA;

    const timeMatches = reportKey.match(FilenameDateRegexp);
    if (timeMatches === null) {
      return;
    }

    this.mapGTFS_Agency = {};
    this.mapDaysData = {};

    const reportYearF = timeMatches[1];
    const reportMonthF = timeMatches[2];
    const reportDayF = timeMatches[3];
    const reportHrMinF = timeMatches[4];

    const ym = reportYearF + '-' + reportMonthF;
    const monthlyReport = await this.dataService.getMonthlyReport(ym);
    this.updateSelectedReportCell(monthlyReport, reportDayF, reportHrMinF);

    const reportURL = ReportHelpers.computeReportURLForTime(reportKey);
    const reportData = await this.dataService.fetchGTFS_RT_StaticReport(reportURL);
    await this.parseReport(reportData, reportKey);

    const mapCompareReportURLs: Record<string, string> = {};
    const mapDayCompareReports = monthlyReport.compare_days[reportDayF] ?? null;
    if (mapDayCompareReports) {
      const snapshotCompareData = mapDayCompareReports[reportHrMinF] ?? null;
      if (snapshotCompareData) {
        const dayKeys = Object.keys(snapshotCompareData.map_days);
        dayKeys.forEach(dayKey => {
          const compareReportKey = dayKey + '-' + reportHrMinF;
          const compareReportURL = ReportHelpers.computeReportURLForTime(compareReportKey);
          mapCompareReportURLs[compareReportKey] = compareReportURL;
        });
      }
    }

    const compareReportKeys = Object.keys(mapCompareReportURLs);
    for (const compareReportKey of compareReportKeys) {
      const compareDayReportURL = mapCompareReportURLs[compareReportKey];
      const compareReportData = await this.dataService.fetchGTFS_RT_StaticReport(compareDayReportURL);
      await this.parseReport(compareReportData, compareReportKey);
    }

    const mapAgencies: Record<string, AgencyJSON> = {};
    const reportKeys = Object.keys(this.mapDaysData);
    reportKeys.forEach(reportKey => {
      const reportAgencyIds = Object.keys(this.mapDaysData[reportKey]);
      reportAgencyIds.forEach(agencyId => {
        mapAgencies[agencyId] = this.mapDaysData[reportKey][agencyId].agencyJSON;
      });
    });
    this.model.agencyRows = Object.values(mapAgencies);

    this.model.compareKeys = compareReportKeys.slice();
    this.model.prevKeyB = this.model.compareKeys.length > 0 ? this.model.compareKeys[0] : 'n/a';

    this.updatePageModel();
    this.sortRows();
  }

  private computeAgencySnapshotData(agency: AgencyJSON, reportKey: string, property: 'gtfs_rt' | 'gtfs_static'): number {
    const dataKey = this.mapDaysData[reportKey] ?? null;
    if (dataKey === null) {
      return -1;
    }

    const agencySnapshotData = dataKey[agency.agency_id] ?? null;
    if (agencySnapshotData === null) {
      return 0;
    }

    if (property ===  'gtfs_rt') {
      return agencySnapshotData.gtfsRtActiveNo;
    } else {
      return agencySnapshotData.gtfsStaticActiveNo;
    }
  }

  private computeCoverageClassName(value: number, coverage: number) {
    if (value <= 10) {
      return 'text-black progress-light';
    } else {
      if (coverage > 95) {
        return 'text-bg-success';
      }
      if (coverage > 80) {
        return 'text-bg-warning';
      }
      if (coverage > 50) {
        return 'text-bg-secondary';
      }

      return 'text-bg-danger';
    }
  }

  private updatePageModel() {
    this.model.agencyRows.forEach(agencyJSON => {
      let reportRow = this.model.reportRows.find(el => el.agency.agency_id === agencyJSON.agency_id) ?? null;
      if (reportRow === null) {
        reportRow = {
          agency: agencyJSON,
          valueNow: {
            gtfsRt: this.computeAgencySnapshotData(agencyJSON, this.model.keyA, 'gtfs_rt'),
            gtfsStatic: this.computeAgencySnapshotData(agencyJSON, this.model.keyA, 'gtfs_static'),
            coverage: 0,
            coverageClass: '',
          },
          valuePrev: {
            // gtfsRt, gtfsStatic - are updated whenever new data is pulled
            gtfsRt: -1,
            gtfsStatic: -1,
            coverage: 0,
            coverageClass: '',
          },
          computed: {
            rtDiff: -1,
            deltaDiff: -1,
          },
        };
        this.model.reportRows.push(reportRow);
      }

      reportRow.valuePrev.gtfsRt = this.computeAgencySnapshotData(agencyJSON, this.model.prevKeyB, 'gtfs_rt');
      reportRow.valuePrev.gtfsStatic = this.computeAgencySnapshotData(agencyJSON, this.model.prevKeyB, 'gtfs_static');

      if (reportRow.valueNow.gtfsStatic !== 0) {
        reportRow.valueNow.coverage = Math.round(reportRow.valueNow.gtfsRt / reportRow.valueNow.gtfsStatic * 100);
      }

      if (reportRow.valuePrev.gtfsStatic !== 0) {
        reportRow.valuePrev.coverage = Math.round(reportRow.valuePrev.gtfsRt / reportRow.valuePrev.gtfsStatic * 100);
      }

      reportRow.valueNow.coverageClass = this.computeCoverageClassName(reportRow.valueNow.gtfsRt, reportRow.valueNow.coverage);
      reportRow.valuePrev.coverageClass = this.computeCoverageClassName(reportRow.valuePrev.gtfsRt, reportRow.valuePrev.coverage);

      reportRow.computed.rtDiff = reportRow.valueNow.gtfsRt - reportRow.valuePrev.gtfsRt;
      reportRow.computed.deltaDiff = Math.abs((reportRow.valueNow.gtfsStatic - reportRow.valueNow.gtfsRt) - (reportRow.valuePrev.gtfsStatic - reportRow.valuePrev.gtfsRt));
    });
  }
  
  private sortRows() {
    this.model.reportRows.sort((a, b) => {
      let expr = (() => {
        if (this.model.sort.column === 'keyA') {
          return a.valueNow.gtfsRt - b.valuePrev.gtfsRt;
        }
        if (this.model.sort.column === 'keyB') {
          return a.valuePrev.gtfsRt - b.valuePrev.gtfsRt;
        }
        if (this.model.sort.column === 'rt-diff') {
          return a.computed.rtDiff - b.computed.rtDiff;
        }
        if (this.model.sort.column === 'delta-diff') {
          return a.computed.deltaDiff - b.computed.deltaDiff;
        }

        // default name sorting
        return a.agency.agency_name.localeCompare(b.agency.agency_name);
      })();
      
      if (this.model.sort.direction === 'desc') {
        expr = -1 * expr;
      }

      return expr;
    });
  }

  private async loadGTFS_DataForGTFS_Day(gtfsDay: string) {
    if (gtfsDay in this.mapGTFS_Agency) {
      return;
    }

    this.mapGTFS_Agency[gtfsDay] = {};
  
    const gtfsAgencyData = await this.dataService.fetchGTFS_Agency(gtfsDay);
    const mapAgency: Record<string, AgencyJSON> = {};
    gtfsAgencyData.rows.forEach(row => {
      mapAgency[row.agency_id] = row;
    });

    this.mapGTFS_Agency[gtfsDay] = mapAgency;
  }

  private async parseReport(reportData: GTFS_RT_Static_Report, reportKey: string) {
    const gtfsDay = reportData.gtfs_trips_active_data.gtfs_day;
    
    await this.loadGTFS_DataForGTFS_Day(gtfsDay);
    const mapGTFS_Agency = this.mapGTFS_Agency[gtfsDay] ?? null;
    if (mapGTFS_Agency === null) {
      throw new Error('No lookups for GTFS day: ' + gtfsDay);
    }

    this.mapDaysData[reportKey] = {};

    const agencyIds = Object.keys(reportData.gtfs_trips_active_data.trips_active_by_agency);
    agencyIds.forEach(agencyId => {
      const agencyJSON = mapGTFS_Agency[agencyId] ?? null;
      if (agencyJSON === null) {
        throw new Error('No GTFS agency for ' + agencyId + ' in GTFS day: ' + gtfsDay);
      }

      const gtfsRT_activeNo = reportData.gtfs_rt_active_by_agency[agencyId] ?? 0;
      const gtfsStatc_activeNo = reportData.gtfs_trips_active_data.trips_active_by_agency[agencyId] ?? 0;
      this.mapDaysData[reportKey][agencyId] = {
        id: agencyId,
        agencyJSON: agencyJSON,
        gtfsStaticActiveNo: gtfsStatc_activeNo,
        gtfsRtActiveNo: gtfsRT_activeNo,
      };
    });
  }

  public onCompareValueChange() {
    this.updatePageModel();
  }

  public showRealtimeTripsTooltip(event: MouseEvent) {
    this.tooltip.visible = true;
    this.moveRealtimeTripsTooltip(event);
  }

  public moveRealtimeTripsTooltip(event: MouseEvent) {
    this.tooltip.x = event.clientX + 12;
    this.tooltip.y = event.clientY + 12;
  }

  public hideRealtimeTripsTooltip() {
    this.tooltip.visible = false;
  }

  public onSortClick(column: SortColumn) {
    if (this.model.sort.column === column) {
      this.model.sort.direction = this.model.sort.direction === 'asc' ? 'desc' : 'asc';
    } else {
      const sortAscendingColumns: SortColumn[] = ['name', 'rt-diff'];
      if (sortAscendingColumns.includes(column)) {
        this.model.sort.direction = 'asc';
      } else {
        this.model.sort.direction = 'desc';
      }

      this.model.sort.column = column;
    }

    this.updatePageModel();
    this.sortRows();
  }
}
