# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_hk_use_713 = fields.Boolean("ADW Calculation",
        help="Calculates the employee’s pay according to the Average Daily Wage (ADW) rules under Hong Kong employment regulations.")
