# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_hk_ir56f_code = fields.Selection(
        string="Reason For Cessation (IR56F)",
        selection=[
            ("1", "Resignation"),
            ("2", "Retirement"),
            ("3", "Dismissal"),
            ("4", "Death"),
            ("5", "Others"),
        ]
    )
