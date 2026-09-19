# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class SaleCommissionPlanAchievement(models.Model):
    _name = 'sale.commission.plan.achievement'
    _description = 'Commission Plan Achievement'
    _order = 'id'

    plan_id = fields.Many2one('sale.commission.plan', required=True, ondelete='cascade', index=True)

    type = fields.Selection([
        ('amount_invoiced', "Amount Invoiced"),
        ('amount_sold', "Amount Sold"),
        ('qty_invoiced', "Quantity Invoiced"),
        ('qty_sold', "Quantity Sold"),
    ], index=True, required=True)

    product_id = fields.Many2one('product.product', "Product")
    product_categ_id = fields.Many2one('product.category', "Category")

    rate = fields.Float("Rate", default=lambda self: 1 if self.plan_id.type == 'target' else 0.05, required=True)

    def _compute_display_name(self):
        for record in self:
            product_name = record.product_id.name or ""
            product_categ_id_name = record.product_categ_id.name or ""
            labels = dict(self._fields['type']._description_selection(self.env))
            record_type = _("%s", record.type and labels[record.type]) or ""
            record.display_name = _("%(plan)s - %(type)s %(product)s %(categ)s",
                                    plan=record.plan_id.name,
                                    type=record_type,
                                    product=product_name,
                                    categ=product_categ_id_name)
