# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class HREmployee(models.Model):
    _name = "hr.employee"
    _inherit = ["hr.employee", "l10n_au.audit.logging.mixin"]

    def _records_to_log(self):
        return self.filtered(lambda r: r.company_country_code == "AU")

    @api.model
    def _get_audit_logging_fields(self):
        return [
            "name",
            "l10n_au_other_names",
            "birthday",
            "private_street",
            "private_street2",
            "private_city",
            "private_state_id",
            "private_zip",
            "private_country_id",
            "l10n_au_tfn",
        ]
