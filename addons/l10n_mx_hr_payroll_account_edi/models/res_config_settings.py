# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_company = fields.Boolean(related="company_id.partner_id.is_company")
    l10n_mx_risk_type = fields.Selection(related="company_id.l10n_mx_risk_type", readonly=False)
    l10n_mx_curp = fields.Char(related="company_id.l10n_mx_curp", readonly=False)
    l10n_mx_imss_id = fields.Char(related="company_id.l10n_mx_imss_id", readonly=False)
