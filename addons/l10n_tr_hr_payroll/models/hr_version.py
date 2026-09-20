from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_tr_is_net_to_gross = fields.Boolean(
        string='Net to Gross',
        help='If checked, the gross salary will be calculated based on the net salary.',
        groups="hr_payroll.group_hr_payroll_user"
    )
