# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    l10n_mx_payroll_type = fields.Selection(
        selection=[
            ('O', 'Ordinary Payroll'),
            ('E', 'Extraordinary Payroll'),
        ],
        default='O', required=True)
