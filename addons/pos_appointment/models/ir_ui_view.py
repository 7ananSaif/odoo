from odoo import api, models
from odoo.fields import Domain


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _get_default_view_domain(self, model, view_type):
        return super()._get_default_view_domain(model, view_type) & \
            Domain('name', 'not in', [
                'calendar.event.view.kanban.pos.appointment',
                'calendar.event.view.calendar.pos.appointment',
                'calendar.event.view.gantt.booking.resource.pos.appointment'
            ])
