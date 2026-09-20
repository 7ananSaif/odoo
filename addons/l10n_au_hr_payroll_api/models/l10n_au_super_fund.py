# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from ..exceptions import _l10n_au_raise_user_error


class L10n_AuSuperFund(models.Model):
    _inherit = "l10n_au.super.fund"

    is_valid = fields.Boolean(string="Is Valid", tracking=True)
    scfi = fields.Char(string="SCFI", readonly=True)

    @api.model
    def _update_active_funds(self):
        """Return all super funds that are valid."""
        Partner = self.env["res.partner"]
        if au_company := self.env["res.company"].search([("partner_id.country_code", "=", "AU")], limit=1):
            results = au_company._l10n_au_make_public_request("/superchoice/active_funds", timeout=60)
            if "error" in results:
                _l10n_au_raise_user_error(results["error"])
            existing_funds = self.search_fetch([("fund_type", "=", "APRA")], ["usi", "scfi", "abn"])
            existing_funds.write({"is_valid": False})
            grouped_scfi_funds = existing_funds.grouped("scfi")
            grouped_usi_funds = existing_funds.grouped("usi")
            grouped_abn_funds = existing_funds.grouped("abn")
            funds_to_create = []
            for result in results["funds"]:
                fund = (result.get("scfi") and grouped_scfi_funds.get(result["scfi"])) or \
                       grouped_usi_funds.get(result["usi"]) or \
                        grouped_abn_funds.get(result["australianBusinessNumber"])

                if fund:
                    fund.write({
                        "name": result["fundName"],
                        "is_valid": True,
                        "abn": result["australianBusinessNumber"],
                        "usi": result["usi"],
                        "scfi": result.get("scfi", False),
                    })
                    fund.address_id.write({
                        "name": result["contactDetails"]["name"],
                        "phone": result["contactDetails"]["phoneNumber"]["value"],
                        "email": result["contactDetails"]["email"]["value"],
                    })
                else:
                    funds_to_create.append({
                        "name": result["fundName"],
                        "abn": result["australianBusinessNumber"],
                        "usi": result["usi"],
                        "address_id": Partner.create({
                            "name": result["contactDetails"]["name"],
                            "phone": result["contactDetails"]["phoneNumber"]["value"],
                            "email": result["contactDetails"]["email"]["value"],
                            "active": False,
                        }).id,
                        "is_valid": True,
                        "scfi": result.get("scfi", False),
                    })
            self.create(funds_to_create)
