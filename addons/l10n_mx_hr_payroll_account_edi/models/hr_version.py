# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_mx_regime_type = fields.Selection(
        selection=[
            ('02', 'Salaries (Includes income specified in section I of article 94 of the Income Tax Law)'),
            ('03', 'Retirees'),
            ('04', 'Pensioners'),
            ('05', 'Assimilated Members of Production Cooperatives'),
            ('06', 'Assimilated Members of Civil Societies and Associations'),
            ('07', 'Assimilated Board Members'),
            ('08', 'Assimilated Commission Agents'),
            ('09', 'Assimilated Fees'),
            ('10', 'Assimilated Shares'),
            ('11', 'Others Assimilated'),
            ('12', 'Retirees or Pensioners'),
            ('13', 'Severance or Separation'),
            ('99', 'Other Regime'),
        ],
        required=True, default='02', groups="hr_payroll.group_hr_payroll_user")

    l10n_mx_shift_type = fields.Selection(
        selection=[
            ('01', 'Daytime'),
            ('02', 'Nighttime'),
            ('03', 'Mixed'),
            ('04', 'Hourly'),
            ('05', 'Reduced'),
            ('06', 'Continued'),
            ('07', 'Split'),
            ('08', 'Shift-Based'),
            ('99', 'Other Schedule'),
        ],
        required=True, default='01', groups="hr_payroll.group_hr_payroll_user")

    l10n_mx_payment_periodicity = fields.Selection(
        selection=[
            ('01', 'Daily'),
            ('02', 'Weekly'),
            ('03', '14 Days'),
            ('04', '15 Days'),
            ('05', 'Monthly'),
            ('06', 'Bi-Monthly'),
            ('07', 'Unit of Work'),
            ('08', 'Commission'),
            ('09', 'Lump Sum'),
            ('10', '10 Days'),
            ('99', 'Other Frequency'),
        ],
        compute='_compute_payment_periodicity', groups="hr_payroll.group_hr_payroll_user")

    @api.depends('schedule_pay')
    def _compute_payment_periodicity(self):
        for record in self:
            if record.schedule_pay == 'daily':
                record.l10n_mx_payment_periodicity = '01'
            elif record.schedule_pay == 'weekly':
                record.l10n_mx_payment_periodicity = '02'
            elif record.schedule_pay == '10_days':
                record.l10n_mx_payment_periodicity = '10'
            elif record.schedule_pay == '14_days':
                record.l10n_mx_payment_periodicity = '03'
            elif record.schedule_pay == 'bi-weekly':
                record.l10n_mx_payment_periodicity = '04'
            elif record.schedule_pay == 'monthly':
                record.l10n_mx_payment_periodicity = '05'
            elif record.schedule_pay == 'bi-monthly':
                record.l10n_mx_payment_periodicity = '06'
            else:
                record.l10n_mx_payment_periodicity = '99'
