# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_industry_fsm_report = fields.Boolean("Worksheet Templates")
    module_industry_fsm_sale = fields.Boolean(
        string="Time and Material Invoicing",
        store=True,
        readonly=False)
