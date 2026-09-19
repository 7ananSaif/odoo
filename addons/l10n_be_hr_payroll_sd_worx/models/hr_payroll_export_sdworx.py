# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models
from odoo.tools.misc import format_date


class L10nBeHrPayrollExportSdworx(models.Model):
    _name = 'l10n.be.hr.payroll.export.sdworx'
    _inherit = ['hr.work.entry.export.mixin']
    _description = 'Export Leaves to SDWorx'

    eligible_employee_line_ids = fields.One2many('l10n.be.hr.payroll.export.sdworx.employee')

    @api.model
    def _country_restriction(self):
        return 'BE'

    def _generate_line(self, employee, date, work_entry_collection):
        """
        Export line format (fixed-width, total length = 31 characters):
        Fields:
        - Employer number          : 7 digits
        - Employee number          : 7 digits
        - Delimiter                : 1 char, always 'K'
        - Presence/absence date    : 8 digits, format YYYYMMDD
        - Attendance Type code     : 4 Alphanumerics
        - Number of hours          : 4 digits, expressed in hundredth always with 2 decimal places

          Example:
            - '1500' = 15.00 hours
            - '0375' = 03.75 hours (3 hours 45 minutes)
            - '0050' = 00.50 hours  (30 minutes)

          Full line Example:
          '11111113333333K2025062400010125'
            - Employer 1111111, Employee 3333333, Date 24/06/2025, Attendance type code 0001, Duration 1.25h (1h 15m)
        """
        sdworx_code = work_entry_collection.work_entries[0].work_entry_type_id.sdworx_code
        time_str = f'{int(work_entry_collection.duration / 36):04d}'
        line = "%(company)s%(employee)sK%(date)s%(leave)s%(time)s" % {
            'company': self.company_id.sdworx_code,
            'employee': employee.sdworx_code,
            'date': date.strftime('%Y%m%d'),
            'leave': sdworx_code,
            'time': time_str
        }
        return line

    def _generate_export_file(self):
        self.ensure_one()
        lines = []
        for employee_line in self.eligible_employee_line_ids:
            we_by_day_and_code = employee_line._get_work_entries_by_day_and_code()
            for we_date, we_by_code in we_by_day_and_code.items():
                for work_entry_collection in we_by_code.values():
                    line = self._generate_line(employee_line.employee_id, we_date, work_entry_collection)
                    lines.append(line)
        lines.sort()
        return "\n".join(lines)

    def _generate_export_filename(self):
        return 'SDWorx_export_%(month)s_%(year)s.txt' % {
            'month': format_date(self.env, date(int(self.reference_year), int(self.reference_month), 1), date_format='MMMM'),
            'year': self.reference_year,
        }

    def _get_name(self):
        return self.env._('Export to SD Worx')


class L10nBeHrPayrollExportSdworxEmployee(models.Model):
    _name = 'l10n.be.hr.payroll.export.sdworx.employee'
    _description = 'SDWorx Export Employee'
    _inherit = ['hr.work.entry.export.employee.mixin']

    export_id = fields.Many2one('l10n.be.hr.payroll.export.sdworx')

    def _relations_to_check(self):
        return super()._relations_to_check() + [
            (self.env._('companies'), 'export_id.company_id.sdworx_code'),
            (self.env._('employees'), 'employee_id.sdworx_code'),
            (self.env._('work entry types'), 'work_entry_ids.work_entry_type_id.sdworx_code'),
        ]
