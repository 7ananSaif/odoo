# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosMakePayment(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self):
        """Override. EDI this order when it's paid through the backend."""
        res = super().check()

        order = self.env["pos.order"].browse(self.env.context.get("active_id", False))
        if order.state == "paid" and order.l10n_br_is_avatax:
            order._l10n_br_do_edi(save_avalara_pdf=True)

        return res
