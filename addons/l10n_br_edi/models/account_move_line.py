# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_br_cfop = fields.Char(
        "CFOP",
        compute="_compute_l10n_br_cfop",
        help="Brazil: CFOP returned from the tax calculation that will be used for submitting your electronic invoice per line. This is computed based on the Operation Type, product, contact and company configuration.",
    )

    def _compute_l10n_br_cfop(self):
        for move, lines in self.grouped("move_id").items():
            tax_calculation_response = json.loads(move.l10n_br_edi_avatax_data) if move.l10n_br_edi_avatax_data else {}
            aml_id_to_cfop = {line["lineCode"]: line["cfop"] for line in tax_calculation_response.get("lines", [])}

            for line in lines:
                line.l10n_br_cfop = aml_id_to_cfop.get(line.id)
