# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def fec_import_action(self):
        """ This action is triggered when the Configuration > FEC Import menu button is pressed."""
        wizard = self.env['account.fec.import.wizard'].create({})
        return wizard._get_records_action(name=self.env._("FEC Import"), target='new')
