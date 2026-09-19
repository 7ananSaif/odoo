# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    def l10n_br_action_open_product_product(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.product",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _l10n_br_avatax_action_missing_fields(self, is_services):
        """A list view for filling in missing fields required for Avatax Brazil."""
        action = {
            "name": _("Products"),
            "type": "ir.actions.act_window",
            "res_model": "product.product",
            "domain": [("id", "in", self.ids)],
            "context": {"create": False, "delete": False},
        }

        if is_services:
            action["views"] = [(self.env.ref("l10n_br_avatax.product_product_view_services_list").id, "list"), (False, "form")]
        else:
            action["views"] = [(self.env.ref("l10n_br_avatax.product_product_view_goods_list").id, "list"), (False, "form")]

        return action
