import { Component, ElementRef, ViewChild } from '@angular/core';

import { DataService } from './data.service';
import { DateHelpers } from './helpers/date-helpers';

import { GTFS_RT_StaticReportCompareMetadata, ReportValueLookupType, GTFS_RT_Static_Monthly_Report_JSON, GTFS_RT_Static_Report_Metadata_JSON } from './types/_all'

import { MapReportValueLookups } from './shared/constants';

interface ReportValueLookup {
  type: ReportValueLookupType,
  caption: string
};

type CellClassDB = 'odd' | 'even';

interface DayCell {
  date: Date,
  dayF: string,
  dateF: string,
  isSunday: boolean
}

interface HourCell {
  hour: number,
  hourF: string
}

interface ReportCell {
  key: string
  report: GTFS_RT_Static_Report_Metadata_JSON | null
  className: string
  cellValue: string
  error: string | null
  dayCell: DayCell,
  hourCell: HourCell,
  compareMetadata: GTFS_RT_StaticReportCompareMetadata | null,
}

interface PageModel {
  mapMonthlyReports: Record<string, GTFS_RT_Static_Monthly_Report_JSON>
  monthItems: string[],
  selectedMonth: string,
  hourlyReportCells: ReportCell[][],
  
  selectedReportCell: ReportCell | null,
  selectedReportMapPrevKeys: Record<string, boolean>,
  
  dayCells: DayCell[],
  hourCells: HourCell[],
  reportValueLookups: ReportValueLookup[],
  selectedReportValueLookup: ReportValueLookup,
  appVersion: string,
  showAllHours: boolean,
  reportLastUpdateF: string,
}

const reportValueLookups = (() => {
  const lookups: ReportValueLookup[] = [];

  const reportValueLookupTypes: ReportValueLookupType[] = ['total_active_rows_no', 'total_rows_no', 'gtfs_db_age', 'gtfs_rt_age', 'tripOK_routeOK_no', 'tripOK_routeNOK_no', 'tripNOK_routeOK_no', 'tripNOK_routeNOK_no', 'tripNOK_NOJP_no'];

  reportValueLookupTypes.forEach(reportValueLookupType => {
    const lookup: ReportValueLookup = {
      type: reportValueLookupType,
      caption: MapReportValueLookups[reportValueLookupType],
    }
    lookups.push(lookup);
  });

  return lookups;
})();

const monthItems: string[] = (() => {
  const startMonthS = '2024-01';

  const startMoParts = startMonthS.split('-');
  const startY = Number(startMoParts[0]);
  const startM = Number(startMoParts[1]);
  const startDay = new Date(startY, startM - 1);

  const now = new Date();
  now.setDate(1);

  const items: string[] = [];
  
  while (startDay <= now) {
    const yearF = startDay.getFullYear();
    const monthF = (startDay.getMonth() + 1).toString().padStart(2, '0');
    items.push(yearF + '-' + monthF);

    if (items.length > 100) {
      // prevent long loops
      break;
    }

    startDay.setMonth(startDay.getMonth() + 1);
  }

  return items.slice().reverse();
})();

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss']
})
export class HomeComponent {
  public model: PageModel;

  @ViewChild('scrollContainer') scrollContainer!: ElementRef;

  constructor(private dataService: DataService) {
    this.model = {
      mapMonthlyReports: {},
      monthItems: monthItems,
      selectedMonth: monthItems[0],
      hourlyReportCells: [],
      selectedReportCell: null,
      dayCells: [],
      hourCells: [],
      reportValueLookups: reportValueLookups,
      selectedReportValueLookup: reportValueLookups[0],
      appVersion: '20260915.1',
      showAllHours: false,
      reportLastUpdateF: 'n/a',
      selectedReportMapPrevKeys: {},
    };
    this.updateHourCells();
  }

  async ngOnInit(): Promise<void> {
    await this.fetchAndUpdateReport();
    
    // HACK setTimeout with 0, otherwise doesnt scroll, the scroll scrollContainer is not ready
    setTimeout(() => {
      this.updateSelectionByDayHr();
    }, 0);
  }

  private updateHourCells() {
    const cells: HourCell[] = [];

    let hour = 0;
    while (hour <= 23) {
      const hourF = hour.toString().padStart(2, '0');

      const cell: HourCell = {
        hour: hour,
        hourF: hourF,
      };
      if (this.shouldShowHour(hour)) {
        cells.push(cell);
      }

      hour += 1;
    }

    this.model.hourCells = cells;
  }

  private async fetchAndUpdateReport() {
    this.model.mapMonthlyReports = {};

    const prevMonthF: string = (() => {
      const monthParts = this.model.selectedMonth.split('-');
      let prevYear = Number(monthParts[0]);
      let prevMonth = Number(monthParts[1]) - 1;
      if (prevMonth === 0) {
        prevYear -= 1;
        prevMonth = 12;
      }

      const prevYearF = String(prevYear).padStart(2, '0');
      const prevMonthF = String(prevMonth).padStart(2, '0');

      return prevYearF + '-' + prevMonthF;
    })();

    const prevMonthReport = await this.dataService.getMonthlyReport(prevMonthF);
    this.model.mapMonthlyReports[prevMonthF] = prevMonthReport

    const currentMonthReport = await this.dataService.getMonthlyReport(this.model.selectedMonth);
    this.model.mapMonthlyReports[this.model.selectedMonth] = currentMonthReport;

    this.updateReportModel();
  }

  public async onMonthSelectChange() {
    await this.fetchAndUpdateReport();
  }

  public onClickShowAllHours() {
    this.updateHourCells();
    this.updateReportModel();
  }

  public onReportValueTypeChange() {
    this.updateReportModel();
  }

  private updateReportModel() {
    const latestReport = this.model.mapMonthlyReports[this.model.selectedMonth] ?? null;

    if (latestReport === null) {
      return;
    }

    const reportLastUpdate = new Date(latestReport.last_update_dt);
    this.model.reportLastUpdateF = latestReport.last_update_dt;

    const dayReportCells: ReportCell[][] = [];
    const dayCells: DayCell[] = [];

    let classDBSource: CellClassDB = 'odd';
    let prevDBName: string | null = null;

    for (const reportYM in this.model.mapMonthlyReports) {
      const report = this.model.mapMonthlyReports[reportYM];

      const monthDay1Date = new Date(reportYM + '-01');
      const selectedMonthDaysNo = DateHelpers.computeMonthDaysNo(monthDay1Date);

      const reportYMParts = reportYM.split('-');
      const reportYearF = Number(reportYMParts[0]);
      const reportMonthF = Number(reportYMParts[1]);

      let currentDay = 1;
      while (currentDay <= selectedMonthDaysNo) {
        const dayF = currentDay.toString().padStart(2, '0');

        const dayCell: DayCell = (() => {
          const currentDayDate = new Date(reportYearF, reportMonthF - 1, currentDay);
          let currentDayF = currentDayDate.toLocaleDateString('en-US', {
            weekday: 'short',
            day: '2-digit',
            month: 'short',
          });
          currentDayF = currentDayF.replace(',', '');
          const currentDayFParts = currentDayF.split(' ');
          currentDayF = currentDayFParts[0] + ' ' + currentDayFParts[2] + '.' + currentDayFParts[1].replace(',', '');
          const isSunday = currentDayFParts[0] === 'Sun';

          return {
            date: currentDayDate,
            dayF: reportYM + '-' + dayF,
            dateF: currentDayF,
            isSunday: isSunday,
          }
        })();

        const hourReportCells: ReportCell[] = [];
        const mapDataHourlyReports = report.report_days[dayF] ?? null;

        this.model.hourCells.forEach(hourCell => {
          const key = dayCell.dayF + '-' + hourCell.hourF;

          const reportCell: ReportCell = {
            key: key,
            report: null,
            className: 'ok_empty',
            cellValue: '',
            error: null,
            dayCell: dayCell,
            hourCell: hourCell,
            compareMetadata: null,
          }

          const hasData: boolean = (() => {
            const reportCellDateS = reportYM + '-' + dayF + ' ' + hourCell.hourF + ':00:00';
            const reportCellDate = new Date(reportCellDateS);

            const isFuture = reportCellDate > reportLastUpdate;
            // Discard future event cells
            if (isFuture) {
              return false;
            }

            // Otherwise check if we have a report
            return mapDataHourlyReports !== null;
          })();

          if (hasData) {
            const hrMinF = hourCell.hourF + '00';
            const reportHR = mapDataHourlyReports[hrMinF] ?? null;
            if (reportHR === null) {
              if (prevDBName !== null) {
                reportCell.cellValue = 'n/a';
                reportCell.error = 'DATA';
              }
            } else {
              const reportAny = reportHR as any;
              const reportValue = reportAny[this.model.selectedReportValueLookup.type] ?? null;
              if (reportValue === null) {
                reportCell.cellValue = 'n/a'
              } else {
                reportCell.cellValue = reportValue.toLocaleString('de-CH');
              }
  
              if (Math.abs(reportHR.gtfs_rt_age) > 60) {
                reportCell.error = 'RT age';
              }

              if (reportHR.tripNOK_NOJP_no > 0) {
                reportCell.error = 'Match';
              }

              if (prevDBName !== null && (prevDBName !== reportHR.gtfs_db_filename)) {
                classDBSource = classDBSource === 'odd' ? 'even' : 'odd';
              }
              prevDBName = reportHR.gtfs_db_filename;

              reportCell.className = 'ok_' + classDBSource;

              if (dayF in report.compare_days) {
                if (hrMinF in report.compare_days[dayF]) {
                  const compare_info = report.compare_days[dayF][hrMinF];

                  const prevValues: Number[] = [];
                  const compareReportLines: string[] = [];
                  for (const dayF in compare_info.map_days) {
                    const prevValue = compare_info.map_days[dayF];
                    prevValues.push(prevValue);
                    const compareReportLine = dayF + ': ' + prevValue;
                    compareReportLines.push(compareReportLine);
                  }

                  const compareMetadata: GTFS_RT_StaticReportCompareMetadata = {
                    info: compare_info,
                    reportLines: compareReportLines,
                    valueF: '' + (reportAny['total_active_rows_no'] ?? 0),
                    meanValueF: '' + compare_info.mean_value,
                    dropLineF: '' + Math.round(Number(compare_info.drop_line)),
                  };

                  reportCell.compareMetadata = compareMetadata;
                  if (compare_info.compare_type === 'w_p') {
                    reportCell.error = 'Drop';
                  }
                }
              }
            }
            
            reportCell.report = reportHR;
          }

          if (this.shouldShowHour(hourCell.hour)) {
            hourReportCells.push(reportCell);
          }
        });

        dayReportCells.push(hourReportCells);

        dayCells.push(dayCell);

        currentDay += 1;
      }
    }

    this.model.hourlyReportCells = dayReportCells;
    this.model.dayCells = dayCells;
  }

  private updateSelectionByDayHr(reportYMDH: string | null = null) {
    const allReports = this.model.hourlyReportCells.flat();
    const latestReportCell = allReports.reverse().find(el => (el.report !== null)) ?? null;
    if (latestReportCell === null) {
      // return early
      return;
    }

    if (reportYMDH === null) {
      // use latest available report
      this.model.selectedReportCell = latestReportCell;
    } else {
      const ymd = reportYMDH.substring(0, 10);
      const dayReportCells = allReports.filter(el => (el.dayCell.dayF === ymd));

      if (dayReportCells.length === 0) {
        // no reports for given day, defaults to latest available report
        this.model.selectedReportCell = latestReportCell;
      } else {
        const hrF = reportYMDH.substring(11, 13);
        const hrReport = dayReportCells.find(el => (el.hourCell.hourF === hrF)) ?? null;
        
        if (hrReport === null) {
          // the hr couldnt be found, display first for the given day
          this.model.selectedReportCell = dayReportCells[0];
        } else {
          this.model.selectedReportCell = hrReport;
        }
      }
    }

    this.updatePrevDaysModel();

    const dayF = this.model.selectedReportCell.dayCell.dayF;
    this.scrollToDay(dayF);
  }

  private updatePrevDaysModel() {
    if (this.model.selectedReportCell === null) {
      return;
    }

    this.model.selectedReportMapPrevKeys = {};
    const mapPrevDays = this.model.selectedReportCell.compareMetadata?.info.map_days ?? {};
    for (const prevDayF in mapPrevDays) {
      const prevReportKey = prevDayF + '-' + this.model.selectedReportCell.hourCell.hourF;
      this.model.selectedReportMapPrevKeys[prevReportKey] = true;
    }
  }

  private shouldShowHour(hour: number) {
    if (this.model.showAllHours) {
      return true;
    }

    const isNormalHour = (6 <= hour) && (hour <=18);
    
    return isNormalHour;
  }
  
  public scrollToDay(ymd: string) {
    const row = this.scrollContainer.nativeElement.querySelector(`#row-${ymd}`) ?? null;
    if (row === null) {
      return;
    }

    row.scrollIntoView({ behavior: 'auto', block: 'nearest' });
  }

  public updateSelection(reportCell: ReportCell) {
    this.model.selectedReportCell = reportCell;
    this.updatePrevDaysModel();
  }
}
