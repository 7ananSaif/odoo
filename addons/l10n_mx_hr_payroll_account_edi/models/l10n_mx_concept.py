# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nMxConcept(models.Model):
    _name = 'l10n.mx.concept'
    _description = 'Concept'
    _order = 'cfdi_type,sat_code'

    name = fields.Char(required=True, translate=True)
    display_name = fields.Char(compute='_compute_display_name')
    cfdi_type = fields.Selection(
        string='Type', required=True,
        selection=[
            ('perception', 'Perception'),
            ('deduction', 'Deduction'),
            ('other', 'Other Payment')
        ]
    )
    is_taxable = fields.Boolean(string='Taxable', help='Check if taxable, uncheck if exempt from taxes.', default=True)
    sat_code = fields.Char(string='SAT Code', required=True)
    payroll_code = fields.Char(string='Payroll Code', required=True)

    @api.depends('name', 'payroll_code')
    def _compute_display_name(self):
        for concept in self:
            concept.display_name = f'({concept.payroll_code}) {concept.name}'
