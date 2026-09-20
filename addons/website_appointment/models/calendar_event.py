from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    visitor_id = fields.Many2one('website.visitor', string='Visitor', ondelete='set null', index='btree_not_null')
