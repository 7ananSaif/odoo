# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = 'hr.departure.reason'

    # ------------------
    # Fields declaration
    # ------------------

    l10n_hk_empf_code = fields.Selection(
        string="Reason Of Termination (eMPF)",
        selection=[
            ('RESIGN', "Resignation"),
            ('RETIRE', "Retirement"),
            ('EARLY_RETIRE', "Early Retirement"),
            ('DISMIS', "Dismissal"),
            ('SUM_DISMISS', "Summary Dismissal"),
            ('REDUNDANCY', "Redundancy"),
            ('LAID_OFF', "Laid Off"),
            ('CONTRACT_END', "Contract Ended"),
            ('DEATH', "Death"),
            ('ILL_HEALTH', "Ill Health"),
            ('TOTAL_INCAP', "Total Incapacity"),
        ],
    )
