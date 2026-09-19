# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class L10n_AuAuditLog(models.Model):
    _name = "l10n_au.audit.log"
    _description = "Audit Log for Payroll"
    _order = "create_date desc"

    log_description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, string="Company", required=True)

    @api.model
    def _sync_audit_logs(self):
        audit_logs = self.sudo().search([("company_id.partner_id.country_code", "=", "AU")])
        for company, records in audit_logs.grouped(lambda x: x.company_id).items():
            if not records or company.l10n_au_payroll_mode == 'test':
                continue
            if iap_proxy := company._l10n_au_payroll_get_proxy_user():
                result = iap_proxy._l10n_au_payroll_request(
                    "/sync_audit_logs",
                    params={"logs": records.mapped("log_description")},
                )
                if "error" in result:
                    _logger.error("Sync Audit Log Failed (Company: %s): %s", company.name, result["error"])

                if result.get("success"):
                    records.sudo().unlink()
                    _logger.info("Logs synced successfully for company %s", company.name)
