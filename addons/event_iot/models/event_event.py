from odoo import fields, models


class EventEvent(models.Model):
    _inherit = 'event.event'

    badge_format = fields.Selection(selection_add=[('96x82', '96x82mm (Badge Printer)')], ondelete={'96x82': 'set default'})
