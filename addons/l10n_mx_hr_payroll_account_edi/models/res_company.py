# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_risk_type = fields.Selection(
        selection=[
            ('1', 'Class I'),
            ('2', 'Class II'),
            ('3', 'Class III'),
            ('4', 'Class IV'),
            ('5', 'Class V'),
            ('99', 'Does Not Apply')],
        default='1', required=True)
    l10n_mx_curp = fields.Char()
    l10n_mx_imss_id = fields.Char(size=20)
