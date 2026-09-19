from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_whatsapp_stock = fields.Boolean("WhatsApp Confirmation")

    @api.onchange('stock_confirmation_type', 'stock_text_confirmation')
    def _onchange_stock_confirmation_fields(self):
        super()._onchange_stock_confirmation_fields()
        if self.stock_text_confirmation and self.stock_confirmation_type == 'whatsapp':
            self.module_whatsapp_stock = True
