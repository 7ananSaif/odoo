# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class IrActionsServer(models.Model):
    _name = 'ir.actions.server'
    _inherit = ['studio.mixin', 'ir.actions.server']

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if self.env.context.get("web_studio.auto_add_to_context"):
            res.create_action()
        return res
