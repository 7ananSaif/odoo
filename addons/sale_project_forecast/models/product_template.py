# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('service_policy')
    def _compute_planning_enabled(self):
        templates_with_disabled_planning = self.filtered(lambda template: template.service_policy in ['delivered_manual', 'delivered_milestones'])
        templates_with_disabled_planning.planning_enabled = False
        super(ProductTemplate, self - templates_with_disabled_planning)._compute_planning_enabled()
