from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    stock_confirmation_wa_template_id = fields.Many2one(
        'whatsapp.template', string='WhatsApp Template',
        help='Send WhatsApp to the customer once the order is delivered.',
    )
