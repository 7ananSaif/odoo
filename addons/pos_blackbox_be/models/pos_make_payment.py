# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class PosMakePayment(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self):
        order = self.env["pos.order"].browse(self.env.context.get("active_id"))
        if order.config_id.certified_blackbox_identifier:
            urban_piper_installed = self.env['ir.module.module']._get('pos_urban_piper').state == 'installed'
            # order.delivery_provider_id only exists if pos_urban_piper is installed
            if not (urban_piper_installed and order.delivery_provider_id):
                raise UserError(
                    _("Adding additional payments to registered orders is not allowed.")
                )

        return super().check()
