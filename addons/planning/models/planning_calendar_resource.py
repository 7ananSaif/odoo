from odoo import fields, models


class PlanningCalendarResource(models.Model):
    """ Personnal calendar resource filter """

    _name = 'planning.calendar.resource'
    _description = 'planning calendar resource'

    user_id = fields.Many2one('res.users', 'Me', required=True, default=lambda self: self.env.user, ondelete='cascade', export_string_translation=False)
    resource_id = fields.Many2one('resource.resource', 'resource', export_string_translation=False)
    active = fields.Boolean('Active', default=True, export_string_translation=False)
    resource_type = fields.Selection(related='resource_id.resource_type', export_string_translation=False)
    checked = fields.Boolean(default=True, export_string_translation=False)

    def get_calendar_filters(self, user_id, field_names):
        field_names.append('resource_type')
        # Create open shit filter for the user if it does not already exist
        if not self.env['planning.calendar.resource'].search_count([('user_id', '=', user_id), ('resource_id', '=', False)]):
            self.env['planning.calendar.resource'].create({'resource_id': False, 'user_id': user_id})
        return self.search_read(domain=[('user_id', '=', user_id)], fields=field_names)
