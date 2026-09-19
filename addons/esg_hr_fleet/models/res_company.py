from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    weekly_days_at_office = fields.Float(default=3.0)

    _weekly_days_at_office_check = models.Constraint(
        "CHECK(weekly_days_at_office >= 0 AND weekly_days_at_office <= 7)",
        "The Weekly Days at the Office must be a value between 0 and 7.",
    )
