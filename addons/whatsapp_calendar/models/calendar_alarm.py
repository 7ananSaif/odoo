from odoo import api, fields, models


class CalendarAlarm(models.Model):
    _inherit = 'calendar.alarm'

    alarm_type = fields.Selection(selection_add=[
        ('whatsapp', 'WhatsApp Message')
    ], ondelete={'whatsapp': 'set default'})
    wa_template_id = fields.Many2one(
        'whatsapp.template', string='WhatsApp Template',
        domain=[('model', '=', 'calendar.attendee'), ('status', '=', 'approved')],
        compute='_compute_wa_template_id', readonly=False, store=True,
        help='Template used to render WhatsApp reminder content.'
    )

    @api.depends('alarm_type')
    def _compute_wa_template_id(self):
        self.filtered(lambda a: a.alarm_type != 'whatsapp').wa_template_id = False
