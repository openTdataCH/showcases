import { Component, Input, OnInit } from '@angular/core';

import { GTFS_RT_Static_Report_Metadata_JSON, GTFS_RT_StaticReportCompareMetadata, ReportValueLookupType } from './types/_all';
import { FilenameDateRegexp, ReportHelpers } from './helpers/report-helpers';
import { MapReportValueLookups } from './shared/constants';
import { DateHelpers } from './helpers/date-helpers';

const MapWeekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MapMonths = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

interface PageModel {
  isDataLoaded: boolean,
  
  title: string,
  dateTimeF: string,
  reportURL: string,
  gtfsDB: {
    filename: string,
    url: string,
  },
  gtfsRT: {
    filename: string,
    url: string,
  }
  gtfsRT_AgeF: string,
  gtfsRT_TotalActiveItemsF: string, 
  compare: {
    hasPrevValues: boolean,
    meanValueF: string,
    dropValueF: string,
    prevValues: string[],
    reportByAgencyURL: string,
  }
  
  // GTFS-RT Total Trips No
  gtfsRT_TotalItemsF: string,
  // Matched Trips
  gtfsRT_MatchedTripsNoF: string,

  // Matched Trips / Not-matched Routes
  gtfsRT_MatchedTripsNoMatchedRoutesF: string,
  // Not-matched Trips / Matched Routes
  gtfsRT_NoMatchedTripsMatchedRoutesF: string,
  // Not-matched Trips / Not-matched Routes
  gtfsRT_NoMatchedTripsNoMatchedRoutesF: string,
  // Not-matched Trips without ojp: prefix
  gtfsRT_NoMatchedTripsOjpPrefixF: string,

  detailReportURL: string,
}

@Component({
  selector: 'detail-report',
  templateUrl: './detail-report.component.html',
  styleUrls: ['./detail-report.component.scss']
})
export class DetailReportComponent implements OnInit {
  private _agencyId = '';
  @Input()
  set agencyId(value: string) {
    this._agencyId = value;
    this.model.detailReportURL = this.computeGTFS_RT_StatusReportURL();
  }

  private _reportMetadata: GTFS_RT_Static_Report_Metadata_JSON | null;
  @Input()
  set reportMetadata(value: GTFS_RT_Static_Report_Metadata_JSON | null) {
    this._reportMetadata = value;

    if (value) {
      this.updatePageModel();
    }
  }
  get reportMetadata(): GTFS_RT_Static_Report_Metadata_JSON | null {
    return this._reportMetadata;
  }
  
  private _compareData: GTFS_RT_StaticReportCompareMetadata | null;
  @Input()
  set compareData(value: GTFS_RT_StaticReportCompareMetadata | null) {
    this._compareData = value;

    if (value) {
      this.updatePageModel();
    }
  }
  get compareData(): GTFS_RT_StaticReportCompareMetadata | null {
    return this._compareData;
  }

  public model: PageModel;

  constructor() {
    this._reportMetadata = null;
    this.reportMetadata = null;
    this._compareData = null;
    this.compareData = null;
    
    // actual init happens in ngOnInit
    this.model = <PageModel>{
      isDataLoaded: false,
      compare: {
        hasPrevValues: false,
      }
    };
  }

  async ngOnInit(): Promise<void> {

  }

  private computeReportURL() {
    if (this._reportMetadata === null) {
      return '';
    }

    const templateURL = 'https://tools.opentransportdata.swiss/gtfs-rt-static-compare-report/[YYYY]/[MM]/[DD]/gtfs_rt_static_report-[YYYY]-[MM]-[DD]-[HHMM].json';
    const url = ReportHelpers.computeSnapshotURLFromTemplate(templateURL, this._reportMetadata.gtfs_rt_filename);

    return url;
  }

  public computeDetailLookupCaption(key: ReportValueLookupType) {
    const caption = MapReportValueLookups[key] ?? null;

    return caption;
  }

  private updatePageModel() {
    const reportMetadata = this._reportMetadata;
    if (reportMetadata === null) {
      return;
    }

    const timeMatches = reportMetadata.gtfs_rt_filename.match(FilenameDateRegexp);
    if (timeMatches === null) {
      console.log('error: cant extract time/data from filename: ' + reportMetadata.gtfs_rt_filename);
      return;
    }

    const reportFilenameDate = ReportHelpers.convertGTFS_RT_FilenameToDate(reportMetadata.gtfs_rt_filename);

    const weekDayF = MapWeekDays[reportFilenameDate.getDay()];
    const monthF = MapMonths[reportFilenameDate.getMonth()];
    const dayF = reportFilenameDate.getDate().toString().padStart(2, '0');
    const reportHrF = timeMatches[4].substring(0, 2);
    const reportMinF = timeMatches[4].substring(2, 4);

    this.model.title = 'Snapshot ' + weekDayF + ' ' + dayF + '.' + monthF + ' ' + reportHrF + ':' + reportMinF;

    const reportDate = new Date(reportMetadata.gtfs_rt_ts * 1000);
    this.model.dateTimeF = DateHelpers.formatDate(reportDate);
    this.model.reportURL = this.computeReportURL();

    this.model.gtfsDB = {
      filename: reportMetadata.gtfs_db_filename,
      url: 'https://tools.opentransportdata.swiss/gtfs-static-dbs/gtfs-static-dbs.json',
    };

    this.model.gtfsRT = {
      filename: reportMetadata.gtfs_rt_filename,
      url: this.computeGTFS_RT_URL(),
    };

    this.model.gtfsRT_AgeF = this.computeDetailLookupValue('gtfs_rt_age') + ' sec';

    this.model.gtfsRT_TotalActiveItemsF = this.computeDetailLookupValue('total_active_rows_no');
    this.model.gtfsRT_TotalItemsF = this.computeDetailLookupValue('total_rows_no');
    this.model.gtfsRT_MatchedTripsNoF = this.computeDetailLookupValue('tripOK_routeOK_no');
    this.model.gtfsRT_MatchedTripsNoMatchedRoutesF = this.computeDetailLookupValue('tripOK_routeNOK_no');
    this.model.gtfsRT_NoMatchedTripsMatchedRoutesF = this.computeDetailLookupValue('tripNOK_routeOK_no');
    this.model.gtfsRT_NoMatchedTripsNoMatchedRoutesF = this.computeDetailLookupValue('tripNOK_routeNOK_no');
    this.model.gtfsRT_NoMatchedTripsOjpPrefixF = this.computeDetailLookupValue('tripNOK_NOJP_no');

    this.model.detailReportURL = this.computeGTFS_RT_StatusReportURL();

    const compareData = this._compareData;
    if (compareData) {
      this.model.compare.hasPrevValues = compareData.reportLines.length > 0;
      this.model.compare.meanValueF = this.formatNumber(parseFloat(compareData.meanValueF));
      this.model.compare.dropValueF = this.formatNumber(parseFloat(compareData.dropLineF));
      this.model.compare.prevValues = compareData.reportLines.reverse();

      const detailKey = timeMatches[1] + '-' + timeMatches[2] + '-' + timeMatches[3] + '-' + timeMatches[4];
      // https://tools.opentransportdata.swiss/gtfs-rt-static-report/detail/2026-03-13-1200
      this.model.compare.reportByAgencyURL = './detail/' + detailKey;
    }

    this.model.isDataLoaded = true;
  }

  private computeDetailLookupValue(key: ReportValueLookupType) {
    const metadata = this._reportMetadata ?? null;
    if (metadata === null) {
      return '';
    }

    const reportAny = metadata as any;
    const reportValue = reportAny[key] ?? null;

    const reportValueF = this.formatNumber(reportValue);

    return reportValueF;
  }

  private formatNumber(n: any): string {
    if (typeof n === 'number' && isFinite(n)) {
      return n.toLocaleString('de-CH');
    }

    return n.toString();
  }

  private computeGTFS_RT_URL() {
    if (this._reportMetadata === null) {
      return '';
    }

    const url = ReportHelpers.computeGTFS_RT_URL(this._reportMetadata.gtfs_rt_filename);
    return url;
  }

  private computeGTFS_RT_StatusReportURL() {
    const metadata = this._reportMetadata ?? null;
    if (metadata === null) {
      return '';
    }

    const templateURL = 'https://gtfs-rt.ch/?gtfs-rt-snapshot=[YYYY]-[MM]-[DD]-[HHMM]';
    let url = ReportHelpers.computeSnapshotURLFromTemplate(templateURL, metadata.gtfs_rt_filename);
    if (this._agencyId !== '') {
      url += '&agency=' + encodeURIComponent(this._agencyId);
    }

    return url;
  }
}
