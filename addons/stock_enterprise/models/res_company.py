from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    stock_confirmation_type = fields.Selection(
        selection_add=[('whatsapp', 'Whatsapp')], ondelete={'whatsapp': 'set default'}
    )
