# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_tr_ytd_gross = fields.Monetary(string='Year to Date Gross', compute='_compute_l10n_tr_ytd_amounts', currency_field='currency_id')
    l10n_tr_ytd_tax = fields.Monetary(string='Year to Date Tax', compute='_compute_l10n_tr_ytd_amounts', currency_field='currency_id')
    l10n_tr_current_month_gross = fields.Monetary(compute='_compute_l10n_tr_current_month_gross', currency_field='currency_id')

    @api.depends('employee_id', 'date_from')
    def _compute_l10n_tr_ytd_amounts(self):
        self.l10n_tr_ytd_gross = 0
        self.l10n_tr_ytd_tax = 0

        tr_slips = self.filtered(lambda p: p.country_code == 'TR')
        if not tr_slips:
            return

        reference_dates = tr_slips.mapped('date_from')
        min_date = min(reference_dates).replace(month=1, day=1)
        max_date = max(reference_dates)
        current_year_payslips_raw = self.env['hr.payslip']._read_group(
            domain=[('employee_id', 'in', self.employee_id.ids),
                    ('date_from', '>=', min_date),
                    ('date_to', '<', max_date),
                    ('state', 'in', ('validated', 'paid'))],
            groupby=['employee_id', 'date_from:year'],
            aggregates=['id:recordset']
        )

        current_year_payslips = {}
        for employee, date, payslips in current_year_payslips_raw:
            current_year_payslips.setdefault(employee, {})[date.year] = payslips

        for payslip in tr_slips.sorted("date_from"):
            reference_date = payslip.date_from
            ytd_payslips = current_year_payslips.get(payslip.employee_id, {}).get(reference_date.year, self.env['hr.payslip']).filtered(lambda ps: ps.date_to < reference_date)
            ytd_amounts = ytd_payslips._get_line_values(['CURTAXABLE', 'BTAXNET'], compute_sum=True)
            payslip.l10n_tr_ytd_gross = ytd_amounts['CURTAXABLE']['sum']['total']
            payslip.l10n_tr_ytd_tax = ytd_amounts['BTAXNET']['sum']['total']

    def _l10n_tr_calculate_net_guess_accuracy(self, guess, target):
        self.ensure_one()
        self.l10n_tr_current_month_gross = guess
        expected_ntg = next((line for line in self._get_payslip_lines() if line.get('code') == 'EXPNET'), {'amount': 0.0})
        return float_round(expected_ntg['amount'], precision_rounding=self.currency_id.rounding) - target

    def _estimate_l10n_tr_gross_from_net(self, target, max_iterations=50, tolerance=0.001):
        """
        A safe version of Newton's method using the secant method to avoid division by zero.
        """
        self.ensure_one()
        guess1, guess2 = self.version_id.wage, self.version_id.wage * 2
        for _ in range(max_iterations):
            value1 = self._l10n_tr_calculate_net_guess_accuracy(guess1, target)
            value2 = self._l10n_tr_calculate_net_guess_accuracy(guess2, target)

            if abs(value1) < tolerance:
                return guess1

            # prevent division by zero
            if float_compare(value1, value2, precision_digits=self.currency_id.decimal_places) == 0:
                break

            # Estimate the slope (secant) and update guess using the secant method
            slope = (value2 - value1) / (guess2 - guess1)
            next_guess = guess1 - value1 / slope

            guess1, guess2 = guess2, next_guess

        return guess1

    @api.depends('version_id')
    def _compute_l10n_tr_current_month_gross(self):
        for payslip in self:
            if payslip.country_code == 'TR' and payslip.version_id.l10n_tr_is_net_to_gross:
                payslip.l10n_tr_current_month_gross = payslip._estimate_l10n_tr_gross_from_net(payslip.version_id.wage)
            else:
                payslip.l10n_tr_current_month_gross = 0

    def _l10n_tr_get_tax(self, taxable_amount):
        self.ensure_one()
        total_tax = 0
        rates = iter(self._rule_parameter('l10_tr_tax_rates'))
        lower, upper, rate = next(rates)
        while lower < taxable_amount:
            total_tax += min((taxable_amount - lower, float(upper) - lower)) * rate
            lower, upper, rate = next(rates)
        return total_tax

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_tr_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
            ])]
