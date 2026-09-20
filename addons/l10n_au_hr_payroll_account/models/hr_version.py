# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_au_report_to_w3 = fields.Boolean('Report in BAS - W3', help="Report the PAYG withholding in W3 instead of W1 and W2.", groups="hr_payroll.group_hr_payroll_user", tracking=True)
