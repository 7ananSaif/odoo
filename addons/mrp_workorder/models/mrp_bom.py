# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MrpBom(models.Model):
    _name = 'mrp.bom'
    _inherit = ['mail.activity.mixin', 'mrp.bom']

    quality_point_count = fields.Integer('Instructions Count', compute='_compute_quality_point_count')

    @api.depends('operation_ids.quality_point_ids')
    def _compute_quality_point_count(self):
        for bom in self:
            bom.quality_point_count = sum(bom.operation_ids.mapped('quality_point_count'))

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals or 'product_tmpl_id' in vals:
            self.operation_ids.quality_point_ids._change_product_ids_for_bom(self)
        return res
