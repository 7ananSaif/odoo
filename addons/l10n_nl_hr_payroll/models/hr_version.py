from odoo import api, models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_nl_30_percent = fields.Boolean(
        string="30% Exemption", groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="The 30% reimbursement ruling (also known as the 30% facility) is a tax advantage for highly skilled migrants moving to the Netherlands for a specific employment role. When the necessary conditions are met, the employer can grant a tax-free allowance equivalent to 30% of the gross salary subject to Dutch payroll tax. This reimbursement is intended as compensation for the extra costs that international employees can incur when moving to a new country for their work. ")

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "NL":
            whitelisted_fields += [
                "l10n_nl_30_percent",
            ]
        return whitelisted_fields
