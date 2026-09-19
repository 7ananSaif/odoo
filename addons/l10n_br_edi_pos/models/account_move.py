# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_l10n_br_avatax_service_params(self):
        # EXTENDS 'account.external.tax.mixin'. This is called for invoiced refunds. It will return the original POS
        # order for which the refund was issued.
        res = super()._get_l10n_br_avatax_service_params()
        if 'invoice_refs' not in res and self.move_type == "out_refund":
            related_pos_order = self.env["pos.order"].search([("account_move", "=", self.id)], limit=1)
            refunded_order = related_pos_order.refunded_order_id
            if related_pos_order and refunded_order.l10n_br_last_avatax_status != "accepted":
                raise ValidationError(
                    _(
                        "%(order_name)s must be successfully invoiced before invoicing this refund.",
                        order_name=refunded_order.display_name,
                    )
                )

            res['invoice_refs'] = {
                "invoicesRefs": [
                    {
                        "type": "refNFe",
                        "refNFe": refunded_order.l10n_br_access_key,
                    }
                ]
            }
        return res
