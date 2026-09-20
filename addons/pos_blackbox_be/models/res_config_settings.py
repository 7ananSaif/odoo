# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iface_fiscal_data_module = fields.Many2one(
        related="pos_config_id.iface_fiscal_data_module", readonly=False
    )

    @api.onchange('iface_fiscal_data_module')
    def _onchange_iface_fiscal_data_module_default(self):
        for res_config in self:
            if res_config.iface_fiscal_data_module:
                cash_rounding = self.env['pos.config']._create_default_cashrounding()
                if cash_rounding:
                    res_config.pos_cash_rounding = True
                    res_config.pos_rounding_method = cash_rounding
                    res_config.pos_only_round_cash_method = True
                res_config.pos_iface_print_auto = True
                res_config.pos_iface_print_skip_screen = True
