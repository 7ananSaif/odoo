from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    weekly_days_at_office = fields.Float(related="company_id.weekly_days_at_office", readonly=False)
