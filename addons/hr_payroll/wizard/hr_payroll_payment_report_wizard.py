import base64
import csv

from io import StringIO

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_amount, format_date


class HrPayrollPaymentReportWizard(models.TransientModel):
    _name = 'hr.payroll.payment.report.wizard'

    _description = 'HR Payroll Payment Report Wizard'

    payslip_run_id = fields.Many2one('hr.payslip.run', check_company=True)
    payslip_ids = fields.Many2many('hr.payslip', required=True, check_company=True)
    export_format = fields.Selection([
        ('csv', 'CSV'),
    ], string='Export Format', required=True, default='csv')
    company_id = fields.Many2one('res.company', compute="_compute_company_id")
    effective_date = fields.Date(
        string='Payment Date',
        help='Payment Entry Date: the banking day on which you intend the payslip batch to be settled.',
        default=fields.Date.context_today, required=True)

    @api.depends('payslip_ids')
    def _compute_company_id(self):
        self.company_id = self.payslip_ids[0].company_id

    def _create_csv_binary(self):
        output = StringIO()
        report_data = csv.writer(output)
        report_data.writerow([_('Sequence'), _('Payment Date'), _('Report Date'), _('Payslip Period'), _('Employee name'), _('Bank account'), _('BIC'), _('Amount to pay')])
        rows = []
        index = 1
        for slip in self.payslip_ids:
            legal_name = slip.employee_id.legal_name
            allocations = slip.compute_salary_allocations()
            if not allocations:
                continue
            for ba in slip.employee_id.bank_account_ids:
                amount = allocations[str(ba.id)]
                if amount == 0:
                    continue
                rows.append((
                    str(index),
                    format_date(self.env, self.effective_date),
                    format_date(self.env, fields.Date.today()),
                    format_date(self.env, slip.date_from) + ' - ' + format_date(self.env, slip.date_to),
                    legal_name,
                    ba.acc_number,
                    ba.bank_bic or '',
                    format_amount(self.env, amount, slip.currency_id)
                ))
                index += 1
        report_data.writerows(rows)
        return base64.encodebytes(output.getvalue().encode())

    def _write_file(self, payment_report, extension, filename=''):
        if self.payslip_run_id:
            batch_filename = filename or _('Payment Report - %(batch_name)s', batch_name=self.payslip_run_id.name)
            self.payslip_run_id.write({
                'payment_report': payment_report,
                'payment_report_filename': batch_filename + extension,
                'payment_report_format': dict(self._fields['export_format']._description_selection(self.env))[self.export_format],
                'payment_report_date': fields.Date.today()})

        for payslip in self.payslip_ids:
            payslip_filename = filename or _('Payment Report - %(dates)s - %(employee_name)s',
                                             dates=payslip._get_period_name({}),
                                             employee_name=payslip.employee_id.legal_name)
            payslip.write({
                'payment_report': payment_report,
                'payment_report_filename': payslip_filename + extension,
                'payment_report_date': fields.Date.today()})

    def _perform_checks(self):
        """
        Extend this function and first call super()._perform_checks().
        Then make condition(s) for the format(s) you added and corresponding checks.
        The checks below are common to all payment reports.
        """
        if not self.payslip_ids:
            raise ValidationError(_('There should be at least one payslip to generate the file.'))
        payslips = self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0)
        if not payslips:
            raise ValidationError(_('There is no valid payslip (validated and net wage > 0) to generate the file.'))

    def _write_payment_date(self):
        self.payslip_ids.write({
            'paid_date': self.effective_date
        })

    def generate_payment_report(self):
        """
        Extend this function and first call super().generate_payment_report().
        Then make condition(s) for the format(s) you added and corresponding methods.
        """
        self.ensure_one()
        if self.payslip_ids.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self._perform_checks()
        self._write_payment_date()
        if self.export_format == 'csv':
            payment_report = self._create_csv_binary()
            self._write_file(payment_report, '.csv')
