# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    l10n_mx_concept = fields.Many2one('l10n.mx.concept', string='CFDI Concept')
