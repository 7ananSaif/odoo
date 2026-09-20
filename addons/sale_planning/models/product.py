# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    planning_enabled = fields.Boolean(
        'Plan Services',
        compute='_compute_planning_enabled',
        readonly=False,
        store=True,
        help="""If enabled, a shift will automatically be generated for the selected role when confirming the Sales Order. \
                With the 'auto plan' feature, only employees with this role will be automatically assigned shifts for Sales Orders containing this service. \
                The system will consider employee availability and the remaining time to be planned. \
                You can also manually schedule open shifts for your Sales Order or assign them to any employee you prefer.""",
    )
    planning_role_id = fields.Many2one('planning.role', index='btree_not_null')

    @api.constrains('planning_enabled', 'type')
    def _check_planning_product_is_service(self):
        invalid_products = self.filtered(lambda product: product.planning_enabled and product.type != 'service')
        if invalid_products:
            raise ValidationError(_("Plannable services should be a service product, product\n%s.", '\n'.join(invalid_products.mapped('name'))))

    @api.depends('planning_role_id')
    def _compute_planning_enabled(self):
        for product in self:
            product.planning_enabled = bool(product.planning_role_id)
