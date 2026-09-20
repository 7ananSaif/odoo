# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    commission_payroll_input = fields.Many2one('hr.payslip.input.type', string="Payslip input",
                                               help="Payslip input type for this commission plan, "
                                                    "commission are grouped by input type.")
