# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date


class L10nChMonthlySummary(models.Model):
    _name = 'l10n.ch.monthly.summary'
    _description = 'Swiss Payroll: Monthly Summary'
    _order = 'date_start'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "CH":
            raise UserError(_('You must be logged in a Swiss company to use this feature'))
        return super().default_get(fields)

    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], required=True, default=lambda self: str((fields.Date.today() + relativedelta(months=-1)).month))
    date_start = fields.Date(
        'Start Period', store=True, readonly=False,
        compute='_compute_dates')
    date_end = fields.Date(
        'End Period', store=True, readonly=False,
        compute='_compute_dates')
    aggregation_type = fields.Selection([
        ('company', 'By Company'),
        ('employee', 'By Employee'),
    ], required=True, default='company')
    company_ids = fields.Many2many('res.company', default=lambda self: self.env.companies.filtered(lambda c: c.country_id.code == "CH"))
    currency_id = fields.Many2one('res.currency', related='company_ids.currency_id')
    monthly_summary_pdf_file = fields.Binary('Monthly Summary PDF', readonly=True, attachment=False)
    monthly_summary_pdf_filename = fields.Char()
    monthly_summary_xls_file = fields.Binary('Monthly Summary XLS', readonly=True, attachment=False)
    monthly_summary_xls_filename = fields.Char()

    @api.depends('date_start')
    def _compute_display_name(self):
        for record in self:
            record.display_name = format_date(self.env, record.date_start, date_format="MMMM y", lang_code=self.env.user.lang)

    @api.depends('year', 'month')
    def _compute_dates(self):
        for record in self:
            record.update({
                'date_start': date(record.year, int(record.month), 1),
                'date_end': date(record.year, int(record.month), 1) + relativedelta(day=31),
            })

    def _get_valid_payslips(self):
        domain = [
            ('state', 'in', ['paid', 'validated']),
            ('company_id', 'in', self.company_ids.ids),
            ('date_from', '>=', self.date_start),
            ('date_to', '<=', self.date_end),
            ('struct_id.code', '=', 'CHMONTHLYELM')
        ]
        payslips = self.env['hr.payslip'].search(domain)
        if not payslips:
            raise UserError(_("There is no paid or validated payslips over the selected period."))
        return payslips

    def _get_line_values(self):
        self.ensure_one()
        payslips = self._get_valid_payslips()

        # Initialize a nested defaultdict to accumulate totals per aggregate record and code, name pair
        result = defaultdict(lambda: defaultdict(float))

        for payslip in payslips:
            # Determine the aggregation key based on aggregation_type
            if self.aggregation_type == "company":
                key = payslip.company_id
            else:
                key = payslip.employee_id

            # Process payslip lines with Swiss-specific rule codes
            for line in payslip.line_ids.filtered(lambda l: l.salary_rule_id.l10n_ch_code):
                rule = line.salary_rule_id
                code = rule.l10n_ch_code

                # Handle special rule codes with custom names
                if code == "9041" and payslip.l10n_ch_additional_accident_insurance_line_ids:
                    solution_code = payslip.l10n_ch_additional_accident_insurance_line_ids[0].solution_code
                    name = f'LAAC Salary - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "9043" and len(payslip.l10n_ch_additional_accident_insurance_line_ids) > 1:
                    solution_code = payslip.l10n_ch_additional_accident_insurance_line_ids[1].solution_code
                    name = f'LAAC Salary - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "5041" and payslip.l10n_ch_additional_accident_insurance_line_ids:
                    solution_code = payslip.l10n_ch_additional_accident_insurance_line_ids[0].solution_code
                    name = f'{line.name[:-2]} - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "5043" and len(payslip.l10n_ch_additional_accident_insurance_line_ids) > 1:
                    solution_code = payslip.l10n_ch_additional_accident_insurance_line_ids[1].solution_code
                    name = f'{line.name[:-2]} - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "5045" and payslip.l10n_ch_sickness_insurance_line_ids:
                    solution_code = payslip.l10n_ch_sickness_insurance_line_ids[0].solution_code
                    name = f'{line.name[:-2]} - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "5047" and len(payslip.l10n_ch_sickness_insurance_line_ids) > 1:
                    solution_code = payslip.l10n_ch_sickness_insurance_line_ids[1].solution_code
                    name = f'{line.name[:-2]} - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "9051" and payslip.l10n_ch_sickness_insurance_line_ids:
                    solution_code = payslip.l10n_ch_sickness_insurance_line_ids[0].solution_code
                    name = f'IJM Salary - Code {solution_code}'
                    result[key][code, name] += line.total
                elif code == "9053" and len(payslip.l10n_ch_sickness_insurance_line_ids) > 1:
                    solution_code = payslip.l10n_ch_sickness_insurance_line_ids[1].solution_code
                    name = f'IJM Salary - Code {solution_code}'
                    result[key][code, name] += line.total
                else:
                    # Handle regular rules, excluding specific codes
                    if code not in ["9070", "9072", "9071", "9073", "9075", "5061", "5062", "5060"]:
                        name = rule.name
                        result[key][code, name] += line.total

            # Process IS (source tax) lines
            for is_line in payslip.l10n_ch_is_log_line_ids:
                if is_line.code == "ISSALARY":
                    code = "9070"
                    name = f'Source-Tax Salary - {is_line.source_tax_canton}-{is_line.is_code}'
                    result[key][code, name] += is_line.amount
                elif is_line.code == "ISDTSALARY":
                    code = "9073"
                    name = f'Source-Tax Rate Determinant Salary - {is_line.source_tax_canton}'
                    result[key][code, name] += is_line.amount
                elif is_line.code == "IS":
                    code = "5060"
                    name = f'Source-Tax Amount - {is_line.source_tax_canton}-{is_line.is_code}'
                    result[key][code, name] += -is_line.amount  # Negate as it's a deduction

        # Convert accumulated data into the final format
        final_result = {}
        for agg_record, data in result.items():
            lines = [
                {"code": code, "name": name, "total": round(total, 2)}
                for (code, name), total in sorted(data.items(), key=lambda x: x[0][0])  # Sort by code
            ]
            final_result[agg_record] = lines

        return final_result

    def action_generate_pdf(self):
        self.ensure_one()
        report_data = {
            'date_start': self.date_start.strftime("%d/%m/%Y"),
            'date_end': self.date_end.strftime("%d/%m/%Y"),
            'line_values': self._get_line_values(),
        }

        filename = '%s-%s-monthly-summary.pdf' % (self.date_start.strftime("%d%B%Y"), self.date_end.strftime("%d%B%Y"))
        monthly_summary, _ = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
            self.env.ref('l10n_ch_hr_payroll.action_report_monthly_summary'),
            res_ids=self.ids, data=report_data)

        self.monthly_summary_pdf_filename = filename
        self.monthly_summary_pdf_file = base64.encodebytes(monthly_summary)

    def action_generate_xls(self):
        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        line_values = self._get_line_values()

        for aggregate_record, rules_data in line_values.items():
            worksheet = workbook.add_worksheet(aggregate_record.name)
            style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
            style_normal = workbook.add_format({'align': 'center'})
            row = 0
            col = 0

            headers = ["Code", "Name", "Amount"]
            rows = [(line['code'], line['name'], line['total']) for line in rules_data]

            for header in headers:
                worksheet.write(row, col, header, style_highlight)
                worksheet.set_column(col, col, 30)
                col += 1

            row = 1
            for employee_row in rows:
                col = 0
                for employee_data in employee_row:
                    worksheet.write(row, col, employee_data, style_normal)
                    col += 1
                row += 1

        workbook.close()
        xlsx_data = output.getvalue()

        self.monthly_summary_xls_file = base64.encodebytes(xlsx_data)
        self.monthly_summary_xls_filename = '%s-%s-monthly-summary.xlsx' % (self.date_start.strftime("%d%B%Y"), self.date_end.strftime("%d%B%Y"))
