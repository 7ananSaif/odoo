# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartnerBank(models.Model):
    _name = "res.partner.bank"
    _inherit = ["res.partner.bank", "l10n_au.audit.logging.mixin"]

    @api.model
    def _get_display_name_fields(self):
        return ["acc_number", "acc_holder_name"]

    @api.model
    def _get_audit_logging_fields(self):
        return ["acc_number", "aba_bsb", "partner_id", "bank_id"]

    def _records_to_log(self):
        return self.filtered(lambda r: r.partner_id and "AU" in r.partner_id.sudo().employee_ids.mapped("company_country_code"))
