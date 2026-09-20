from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_confirmation_wa_template_id = fields.Many2one(
        comodel_name='whatsapp.template',
        related='company_id.stock_confirmation_wa_template_id',
        domain="[('model', '=', 'stock.picking'), ('status', '=', 'approved')]",
        readonly=False,
    )
