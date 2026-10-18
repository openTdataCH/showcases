import sys
import sqlite3

from datetime import datetime, timedelta
from bitarray import bitarray

class Calendar:
    def __init__(self, service_id, start_date, end_date, day_bits, 
        monday = None, tuesday = None, wednesday = None, thursday = None, friday = None, saturday = None, sunday = None
    ):
        self.service_id = service_id
        self.monday = monday
        self.tuesday = tuesday
        self.wednesday = wednesday
        self.thursday = thursday
        self.friday = friday
        self.saturday = saturday
        self.sunday = sunday
        self.start_date = start_date
        self.end_date = end_date
        self.day_bits = day_bits

    @staticmethod
    def init_from_db_row(db_row: sqlite3.Row):
        service_id = db_row['service_id']
        start_date_s = db_row['start_date']
        end_date_s = db_row['end_date']
        day_bits = db_row['day_bits']

        # patch the raw sqlite3.Row objects to allow dict lookups
        if 'get' not in dir(db_row):
            db_row = dict(db_row)

        monday = db_row.get('monday') or None
        tuesday = db_row.get('tuesday') or None
        wednesday = db_row.get('wednesday') or None
        thursday = db_row.get('thursday') or None
        friday = db_row.get('friday') or None
        saturday = db_row.get('saturday') or None
        sunday = db_row.get('sunday') or None

        start_date = datetime.strptime(start_date_s, "%Y%m%d").date()
        end_date = datetime.strptime(end_date_s, "%Y%m%d").date()

        entry = Calendar(
            service_id, start_date, end_date, day_bits,
            monday, tuesday, wednesday, thursday, friday, saturday, sunday
        )

        return entry

    def _compute_week_pattern(self):
        pattern_parts = [
            f'{self.monday or "·"}',
            f'{self.tuesday or "·"}',
            f'{self.wednesday or "·"}',
            f'{self.thursday or "·"}',
            f'{self.friday or "·"}',
            f'{self.saturday or "·"}',
            f'{self.sunday or "·"}',
        ]

        pattern_s = ''.join(pattern_parts)
        return pattern_s

    def compute_month_data_rows(self):
        # First day of Dec
        calendar_day1_s = self.start_date.strftime('%Y-%m-01')
        current_day = datetime.strptime(calendar_day1_s, "%Y-%m-%d").date()

        month_data_rows = []
        empty_day_bit_rows = []
        prev_month_key = None

        map_weekday_f = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

        while current_day <= self.end_date:
            month_key = current_day.strftime('%Y-%m')
            if prev_month_key != month_key:
                # Padding with None to always start from Monday
                empty_day_bit_rows = [None] * current_day.weekday()
                month_data = {
                    'month_key': month_key,
                    'day_bit_rows': empty_day_bit_rows,
                }
                month_data_rows.append(month_data)

                prev_month_key = month_key

            day_bit = None
            if current_day >= self.start_date:
                day_idx = (current_day - self.start_date).days
                day_bit = self.day_bits[day_idx] == '1'
            day_bit_row = {
                'day_f': f'{current_day}',
                'day_w': map_weekday_f[current_day.weekday()],
                'day_bit': day_bit,
            }
            month_data['day_bit_rows'].append(day_bit_row)

            current_day += timedelta(days=1)

        return month_data_rows

    def _debug_days(self):
        report_lines = []

        month_data_rows = self.compute_month_data_rows()

        header_separator_s = '-' * 60
        report_lines.append(f'{header_separator_s}')

        week_days_s = 'MTWTFSS ' * 6
        report_lines.append(f'Month   : {week_days_s}')

        report_lines.append(f'{header_separator_s}')

        for month_data in month_data_rows:
            month_bits_formatted = []
            for (idx, day_bit_data) in enumerate(month_data['day_bit_rows']):
                day_bit_s = ' '
                if day_bit_data is not None:
                    day_bit = day_bit_data['day_bit']
                    day_bit_s = ' '
                    if day_bit is not None:
                        day_bit_s = '1' if day_bit else '·'
                month_bits_formatted.append(day_bit_s)
                
                # space after weekdays
                if (idx % 7) == 6:
                    month_bits_formatted.append(' ')
            month_key = month_data['month_key']

            month_bits_s = ''.join(month_bits_formatted)
            report_lines.append(f'{month_key} : {month_bits_s}')

        report_lines.append(f'{header_separator_s}')

        return report_lines

    def _compute_pretty_print_lines(self):
        report_lines = []

        header_separator_s = '-' * 60
        report_lines.append(f'{header_separator_s}')

        report_lines.append(f'service_id  : {self.service_id}')

        if self.monday:
            report_lines.append(f'{header_separator_s}')
            report_lines.append(f'week pattern: MTWTFSS')
            report_lines.append(f'week pattern: {self._compute_week_pattern()}')

        report_lines += self._debug_days()

        return report_lines
    
    def pretty_print(self):
        report_lines = self._compute_pretty_print_lines()
        report_s = "\n".join(report_lines)
        return report_s

    def is_running_for_day(self, for_day: datetime) -> bool:
        day_idx = (for_day - self.start_date).days
        day_bit = self.day_bits[day_idx]
        is_running = day_bit == '1'

        return is_running

    def has_overlaps(self, another_calendar_o):
        another_calendar: Calendar = another_calendar_o
        found_overlaps = Calendar.has_calendar_overlaps(self.day_bits, another_calendar.day_bits)

        return found_overlaps

    def merge(self, another_calendar_o):
        another_calendar: Calendar = another_calendar_o

        b1_or_b2_s = Calendar.merge_calendar_day_bits(self.day_bits, another_calendar.day_bits)

        new_sevice_id = f'{self.service_id} + {another_calendar.service_id}'
        new_service = Calendar(new_sevice_id, self.start_date, self.end_date, b1_or_b2_s)

        return new_service

    @staticmethod
    def has_calendar_overlaps(cal1_day_bits: str, cal2_day_bits: str) -> bool:
        if len(cal1_day_bits) != len(cal2_day_bits):
            print(cal1_day_bits)
            print(cal2_day_bits)
            raise ValueError('ERROR has_calendar_overlaps - the services are not equal size')

        b1 = bitarray(cal1_day_bits)
        b2 = bitarray(cal2_day_bits)
        b1_and_b2 = b1 & b2

        # https://en.wikipedia.org/wiki/Bitwise_operation#AND
        # b1:           111000
        # b2:           000100
        # b1_and_b2:    000000
        
        found_overlaps = b1_and_b2.count(1) > 0

        return found_overlaps

    @staticmethod
    def merge_calendar_day_bits(cal1_day_bits: str, cal2_day_bits: str) -> str:
        if len(cal1_day_bits) != len(cal2_day_bits):
            print(cal1_day_bits)
            print(cal2_day_bits)
            raise ValueError('ERROR merge_calendar_day_bits - the services are not equal size')

        b1 = bitarray(cal1_day_bits)
        b2 = bitarray(cal2_day_bits)
        b1_or_b2 = b1 | b2

        # https://en.wikipedia.org/wiki/Bitwise_operation#OR
        # b1:           111000
        # b2:           000100
        # b1_or_b2:     111100

        b1_or_b2_s = b1_or_b2.to01()

        return b1_or_b2_s
    