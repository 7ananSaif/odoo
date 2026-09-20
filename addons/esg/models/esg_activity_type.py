from odoo import fields, models


class EsgActivityType(models.Model):
    _name = 'esg.activity.type'
    _description = 'Activity Type'

    name = fields.Char(required=True, translate=True)

    _name_uniq = models.Constraint(
        'unique (name)',
        'A tag with the same name already exists.',
    )
