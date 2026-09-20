from odoo import Command, api, fields, models


class HelpdeskTagAssignment(models.Model):
    _name = 'helpdesk.tag.assignment'
    _description = "Helpdesk Tag Assignment"

    team_id = fields.Many2one('helpdesk.team', export_string_translation=False)
    tag_id = fields.Many2one('helpdesk.tag', "Ticket Tag", required=True)
    # Used to prevent a tag from appearing in the dropdown in the list view if it already exists in the mapping.
    user_ids = fields.Many2many('res.users', string="Team Members", required=True, domain=[('share', '=', False)])

    _tag_team_unique = models.Constraint(
        'UNIQUE(team_id, tag_id)',
        "A tag can only be used once per team.",
    )
