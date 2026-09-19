# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import calendar
import io
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .report_hr_epf import MONTH_SELECTION


class HrESICReport(models.Model):
    _name = 'l10n.in.hr.payroll.esic.report'
    _description = 'Indian Payroll: Employee State Insurance Report / Employees State Insurance Corporation'

    def _get_year_selection(self):
        current_year = datetime.now().year
        return [(str(i), i) for i in range(current_year, 1989, -1)]

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    month = fields.Selection(MONTH_SELECTION, default=lambda self: str(datetime.today().month), required=True)
    year = fields.Selection(selection='_get_year_selection', required=True, default=lambda self: str(datetime.now().year))
    export_report_type = fields.Selection(
        [('esi', 'ESI Summary'), ('esic', 'ESIC')],
        default='esi', required=True, string="Report Type"
    )
    period_has_payslips = fields.Boolean(compute='_compute_period_has_payslips')
    xlsx_file = fields.Binary(string="Generated File")
    xlsx_filename = fields.Char()

    _unique_esic_report_per_month_year = models.Constraint(
        'UNIQUE(company_id, month, year, export_report_type)',
        "An ESI/ESIC Report for this month and year already exists.",
    )

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "IN":
            raise UserError(_('You must be logged in a Indian company to use this feature'))
        return super().default_get(fields)

    @api.depends('month', 'year')
    def _compute_display_name(self):
        month_description = dict(self._fields['month']._description_selection(self.env))
        for report in self:
            report.display_name = f"{month_description.get(report.month)}-{report.year}"

    def _get_period_payslips_with_employees(self):
        self.ensure_one()
        indian_employees = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
            ('company_id.l10n_in_esic', '=', True),
            ('version_id.l10n_in_esic_employee_amount', '>', 0),
            ('version_id.l10n_in_esic_employer_amount', '>', 0),
        ])
        year = int(self.year)
        month = int(self.month)
        end_date = calendar.monthrange(year, month)[1]

        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', indian_employees.ids),
            ('date_from', '>=', date(year, month, 1)),
            ('date_to', '<=', date(year, month, end_date)),
            ('state', 'in', ('validated', 'paid'))
        ])
        return indian_employees, payslips

    @api.depends('month', 'year')
    def _compute_period_has_payslips(self):
        for report in self:
            _, payslips = report._get_period_payslips_with_employees()
            report.period_has_payslips = bool(payslips)

    def _get_employee_esic_data(self):
        self.ensure_one()
        # Get the relevant records based on the year and month
        result = []
        indian_employees, payslips = self._get_period_payslips_with_employees()
        if not payslips:
            return []

        payslip_line_values = payslips._get_line_values(['GROSS'])
        for employee in indian_employees:
            gross_wage = 0
            working_days = 0
            payslip_ids = payslips.filtered(lambda p: p.employee_id == employee)
            if not payslip_ids:
                continue
            for payslip in payslip_ids:
                gross_wage += payslip_line_values['GROSS'][payslip.id]['total']
                working_days = sum(workday.number_of_days for workday in payslip.worked_days_line_ids if workday.is_paid)
            result.append((
                employee.l10n_in_esic_number,
                employee.name,
                working_days,
                gross_wage,
                0,
                employee.version_id.contract_date_end.strftime('%d-%m-%Y') if employee.version_id.contract_date_end else ''
            ))
        return result

    def _get_employee_esi_data(self):
        self.ensure_one()
        # Get the relevant records based on the year and month
        result = []
        indian_employees, payslips = self._get_period_payslips_with_employees()

        if not payslips:
            return []

        payslip_line_values = payslips._get_line_values(['GROSS', 'ESICF', 'ESICS'])

        for employee in indian_employees:
            esi_wage_base = 0
            employee_esi_contribution = 0
            employer_esi_contribution = 0

            payslip_ids = payslips.filtered(lambda p: p.employee_id == employee)

            for payslip in payslip_ids:
                esi_wage_base += payslip_line_values['GROSS'][payslip.id]['total']
                employee_esi_contribution -= payslip_line_values['ESICS'][payslip.id]['total']
                employer_esi_contribution += payslip_line_values['ESICF'][payslip.id]['total']

            if not employee_esi_contribution and not employer_esi_contribution:
                continue

            result.append((
                employee.name,
                employee.registration_number or '-',
                employee.l10n_in_esic_number or '-',
                esi_wage_base,
                employee_esi_contribution,
                employer_esi_contribution,
                employee_esi_contribution + employer_esi_contribution  # Total Contribution by employee and employer
            ))

        return result

    def action_export_xlsx(self):
        self.ensure_one()

        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        if self.export_report_type == 'esi':
            self.action_export_esi_xlsx(output, workbook)
        else:
            self.action_export_esic_xlsx(output, workbook)

    def action_export_esi_xlsx(self, output, workbook):
        self.ensure_one()

        worksheet = workbook.add_worksheet(_('Employee_ESI_report'))
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'font_size': 12})
        row = 0
        worksheet.set_row(row, 20)

        headers = [
            _("EMPLOYEE NAME"),
            _("EMPLOYEE NUMBER"),
            _("STATUTORY REGISTRATION NUMBER"),
            _("ESI WAGES"),
            _("EMPLOYEE CONTRIBUTION"),
            _("EMPLOYER CONTRIBUTION"),
            _("TOTAL REMITTED"),
        ]

        rows = self._get_employee_esi_data()

        if not rows:
            raise ValidationError(_('No Employees on the ESI report for the selected period'))

        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 33)

        row = 1
        for data_row in rows:
            col = 0
            worksheet.set_row(row, 20)
            for data in data_row:
                worksheet.write(row, col, data, style_normal)
                col += 1
            row += 1

        workbook.close()
        xlsx_data = output.getvalue()

        self.xlsx_file = base64.encodebytes(xlsx_data)
        self.xlsx_filename = _("%(display_name)s ESI Report.xlsx", display_name=self.display_name)

    def action_export_esic_xlsx(self, output, workbook):
        self.ensure_one()

        esic_worksheet = workbook.add_worksheet(_('Employees\' State Insurance Corporation'))
        instruction_worksheet = workbook.add_worksheet(_('Instructions & Reason Codes'))

        # Header style with bold and background color, including text wrapping
        style_highlight = workbook.add_format({
            'bold': True,
            'pattern': 1,
            'bg_color': '#E0E0E0',
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': 1,
            'border_color': '#000000',
        })
        style_normal = workbook.add_format({'font_size': 12})
        row = 0
        esic_headers = [
            _("IP Number (10 Digits)"),
            _("IP Name (Only alphabets and space)"),
            _("No of Days for which wages paid/payable during the month"),
            _("Total Monthly Wages"),
            _("Reason Code for Zero workings days(Numeric Only: provide 0 for all other reasons)"),
            _("Last Working Day (Format DD/MM/YYYY or DD-MM-YYYY)"),
        ]

        esic_rows = self._get_employee_esic_data()

        # Writing the esic_headers
        esic_worksheet.set_row(row, 35)
        for col, header in enumerate(esic_headers):
            esic_worksheet.write(row, col, header, style_highlight)
            esic_worksheet.set_column(col, col, 40)

        row = 1
        for data_row in esic_rows:
            col = 0
            for data in data_row:
                esic_worksheet.write(row, col, data, style_normal)
                col += 1
            row += 1

        # create another worksheet for info & reason code
        reason_code_style_normal = workbook.add_format({
            'align': 'left',
            'valign': 'top',
            'text_wrap': True,
            'font_size': 12,
        })
        reason_code_style_col = workbook.add_format({
            'align': 'center',
            'text_wrap': True,
            'font_size': 12,
        })
        reason_code_header = [
            "Reason",
            "Code",
            "Note",
        ]

        row = 0
        for col, header in enumerate(reason_code_header):
            instruction_worksheet.write(row, col, header, style_highlight)
        instruction_worksheet.set_column(0, 0, 35)
        instruction_worksheet.set_column(1, 1, 20)
        instruction_worksheet.set_column(2, 2, 85)

        reason_codes_rows = [
            [_("Without Reason"), "0", _("Leave last working day as blank")],
            [_("On Leave"), "1", _("Leave last working day as blank")],
            [_("Left Service"), "2", _("Please provide last working day (dd/mm/yyyy). IP will not appear from next wage period")],
            [_("Retired"), "3", _("Please provide last working day (dd/mm/yyyy). IP will not appear from next wage period")],
            [_("Out of Coverage"), "4", _("Please provide last working day (dd/mm/yyyy). IP will not appear from next contribution "
                "period. This option is valid only if Wage Period is April/October. In case any other month then IP will continue "
                "to appear in the list")],
            [_("Expired"), "5", _("Please provide last working day (dd/mm/yyyy). IP will not appear from next wage period")],
            [_("Non Implemented area"), "6", _("Please provide last working day (dd/mm/yyyy)")],
            [_("Compliance by Immediate Employer"), "7", _("Leave last working day as blank")],
            [_("Suspension of work"), "8", _("Leave last working day as blank")],
            [_("Strike/Lockout"), "9", _("Leave last working day as blank")],
            [_("Retrenchment"), "10", _("Please provide last working day (dd/mm/yyyy). IP will not appear from next wage period")],
            [_("No Work"), "11", _("Leave last working day as blank")],
            [_("Doesnt Belong To This Employer"), "12", _("Leave last working day as blank")],
            [_("Duplicate IP"), "13", _("Leave last working day as blank")],
        ]

        row = 1
        for data_row in reason_codes_rows:
            col = 0
            if row == 5:
                instruction_worksheet.set_row(row, 50)  # Increase the height of row 5
            for data in data_row:
                instruction_worksheet.write(row, col, data, reason_code_style_col if col == 1 else reason_code_style_normal)
                col += 1
            row += 1

        row += 1
        col = 0
        instruction_worksheet.set_row(row, 40)
        instruction_worksheet.write(row, col, _('Instructions to fill in the excel file:'), workbook.add_format({
            'bold': True,
            'font_size': 17,
        }))

        info_row = [
            _("1. Enter the IP number,  IP name, No. of Days, Total Monthly Wages, Reason for 0 wages(If Wages '0') & "
                    "Last Working Day(only if employee has left service, Retired, Out of coverage, Expired, Non-Implemented"
                    "area or Retrenchment. For other reasons,  last working day  must be left  BLANK)"),
            _("2. Number of days must me a whole number.  Fractions should be rounded up to next higher whole number/integer"),
            _("3. Excel sheet upload will lead to successful transaction only when all the Employees' (who are currently "
                    "mapped in the system) details are entered perfectly in the excel sheet"),
            _("4. Reasons are to be assigned numeric code  and date has to be provided as mentioned in the table above"),
            _("5. Once  0 wages given and last working day is mentioned as in reason codes (2,3,4,5,10)  IP will be "
                    "removed from the employer's record. Subsequent months will not have this IP listed under the employer."
                    "Last working day should be mentioned only if 'Number of days wages paid/payable' is '0'"),
            _("6. In case IP has worked for part of the month(i.e. atleast 1 day wage is paid/payable) and left in between "
                    "of the month, then last working day shouldn't be mentioned"),
            _("7. Calculations - IP Contribution and Employer contribution calculation will be automatically done by the system"),
            _("8. Date  column format is  dd/mm/yyyy or dd-mm-yyyy. Pad single digit dates with 0. Eg:- 2/5/2010  or "
                    "2-May-2010 is NOT acceptable. Correct format is 02/05/2010 or 02-05-2010"),
            _("9. Excel file should be saved in .xls format (Excel 97-2003)"),
            _("10. Note that all the column including date column should be in 'Text' format"),
            _("10a. To convert  all columns to text"),
            _("   a. Select column A; Click Data in Menu Bar on top;  Select Text to Columns ; Click Next (keep default \n "
                    "selection of Delimited);  Click Next (keep default selection of Tab); Select  TEXT;  Click FINISH. \n "
                    "Excel 97 - 2003 as well have TEXT to COLUMN  conversion facility"),
            _("   b. Repeat the above step for each of the 6 columns. (Columns A - F )"),
            _("10b. Another method that can be used to text conversion is - copy the column with data and paste it in NOTEPAD."
                    "Select the column (in excel) and convert to text. Copy the data back from notepad to excel"),
            _("11. If problem continues while upload,  download a fresh template by clicking 'Sample MC Excel Template'. "
                    "Then copy the data area from Step 8a.a - eg:  copy Cell A2 to F8 (if there is data in 8 rows); "
                    "Paste it in cell A2 in the fresh template. Upload it "),
        ]

        row += 1
        for data_row in info_row:
            instruction_worksheet.set_row(row, 38)
            instruction_worksheet.merge_range(row, 0, row, 2, data_row, reason_code_style_normal)
            row += 1

        workbook.close()
        xlsx_data = output.getvalue()

        self.xlsx_file = base64.encodebytes(xlsx_data)
        self.xlsx_filename = _("%(display_name)s ESIC Report.xlsx", display_name=self.display_name)
