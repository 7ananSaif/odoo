# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrFonacot(models.Model):
    _name = 'l10n.mx.hr.fonacot'
    _description = 'fonacot'

    status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ], string="Status", required=True, default='in_progress')

    version_id = fields.Many2one('hr.version')
    currency_id = fields.Many2one(related='version_id.currency_id')
    company_id = fields.Many2one(related='version_id.company_id')

    extra_fixed_monthly_contribution = fields.Monetary(string="Extra Fixed Monthly Contribution")
    monthly_import = fields.Monetary(string="Import")

    _check_positive_monthly_import = models.Constraint(
        'CHECK (monthly_import >= 0)',
        'The monthly import cannot be negative'
    )
    _check_positive_extra_fixed_monthly_contribution = models.Constraint(
        'CHECK (extra_fixed_monthly_contribution >= 0)',
        'The extra fixed monthly contribution cannot be negative'
    )
