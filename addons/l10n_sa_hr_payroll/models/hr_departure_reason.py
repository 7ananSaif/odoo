# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_sa_reason_type = fields.Selection([
        ('fired', "Fired"),
        ('retired', "Retired"),
        ('resigned', "Resigned"),
        ('end_of_contract', "End of Contract"),
        ('clause_77', "Clause 77"),
    ], default='resigned')
