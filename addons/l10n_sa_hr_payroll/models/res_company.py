# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_sa_mol_establishment_code = fields.Char(string="MoL Establishment ID")
    l10n_sa_bank_account_id = fields.Many2one("res.partner.bank", string="Establishment's Bank Account")
    l10n_sa_annual_leave_type_id = fields.Many2one("hr.leave.type",
        string="SA Annual Leave Time-off Type",
        default=lambda self: self.env.ref("hr_holidays.leave_type_paid_time_off", raise_if_not_found=False))
