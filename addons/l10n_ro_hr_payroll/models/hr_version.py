from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_ro_work_type = fields.Selection([
        ('1', 'Normal Conditions'),
        ('2', 'Particular Conditions'),
        ('3', 'Special Conditions')
    ], string='Work type', default="1", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "RO":
            whitelisted_fields += [
                "l10n_ro_work_type",
            ]
        return whitelisted_fields
