# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    subscription_rule_ids = fields.One2many(
        string="Subscription Pricings",
        comodel_name='product.pricelist.item',
        inverse_name='product_id',
        compute='_compute_subscription_rule_ids',
        readonly=False,
    )

    @api.depends('product_tmpl_id')
    def _compute_subscription_rule_ids(self):
        for product in self:
            if not product.id:
                product.subscription_rule_ids = False
                continue
            product.subscription_rule_ids = product.product_tmpl_id.subscription_rule_ids.filtered(
                lambda rule: not rule.product_id or rule.product_id == product.id
            )
