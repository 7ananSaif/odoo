from odoo import api, fields, models


class WebsiteVisitor(models.Model):
    _inherit = 'website.visitor'

    calendar_event_ids = fields.One2many('calendar.event', 'visitor_id')

    @api.depends('calendar_event_ids')
    def _compute_email_phone(self):
        super()._compute_email_phone()

        left_visitors = self.filtered(lambda visitor: not visitor.email or not visitor.mobile)
        # Get the last booker created for each visitor without email and mobile to update
        # those missing data.
        last_booker_by_visitor = dict(self.env['calendar.event']._read_group(
            [('visitor_id', 'in', left_visitors.ids)], ['visitor_id'], ['appointment_booker_id:max']
        ))
        ResPartner = self.env['res.partner'].with_prefetch(last_booker_by_visitor.values())

        for visitor in left_visitors:
            if appointment_booker_id := last_booker_by_visitor.get(visitor):
                appointment_booker = ResPartner.browse(appointment_booker_id)
                visitor.email = appointment_booker.email
                visitor.mobile = appointment_booker.phone

    def _merge_visitor(self, target):
        """ Link the calendar event to the main visitor to avoid them being lost. """
        if self.calendar_event_ids:
            self.calendar_event_ids.write({'visitor_id': target.id})
        return super()._merge_visitor(target)
