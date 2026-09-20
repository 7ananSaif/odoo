# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    plan_id = fields.Many2one(
        string="Recurring Plan",
        comodel_name='sale.subscription.plan',
        check_company=True,
        index=True,
    )

    # === COMPUTE METHODS === #

    @api.depends('plan_id')
    def _compute_company_id(self):
        rules_with_pricelist = self.filtered('pricelist_id')
        super(ProductPricelistItem, rules_with_pricelist)._compute_company_id()
        for item in (self - rules_with_pricelist):
            # must have a plan if there is no pricelist
            if not item.plan_id:
                continue
            item.company_id = item.plan_id.company_id

    @api.depends('plan_id')
    def _compute_is_pricelist_required(self):
        # Pricelist rules can be generic (and apply regardless of pricelist), only if plan is set
        rules_with_plan = self.filtered('plan_id')
        super(ProductPricelistItem, self - rules_with_plan)._compute_is_pricelist_required()
        rules_with_plan.is_pricelist_required = False

    @api.depends('plan_id')
    def _compute_price_label(self):
        super()._compute_price_label()
        for item in self:
            if item.plan_id and item.compute_price in ('fixed', 'percentage'):
                item.price = item.env._(
                    "%(price_details)s %(recurrence)s",
                    price_details=item.price,
                    recurrence=item.plan_id.sudo().billing_period_display_sentence,
                )

    # === BUSINESS METHODS === #

    def _is_applicable_for(self, product, qty_in_product_uom):
        # Subscription rules should not apply to non-recurring products
        if self.plan_id and not product.recurring_invoice:
            return False
        if not self.plan_id and product.recurring_invoice and not product.allow_one_time_sale:
            return False
        return super()._is_applicable_for(product, qty_in_product_uom)

    def _compute_base_price(self, product, quantity, uom, date, currency, *, plan_id=None, **kwargs):
        """Override of `product` to consider pricelist items without pricelists as 'sales price' for recurring products.

        :param product: recordset of product (product.product/product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: currency in which the returned price must be expressed
        :param int plan_id: requested subscription plan

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        rule_base = self.base or 'list_price'
        if rule_base == 'list_price' and product.recurring_invoice and plan_id:
            domain = self.env['product.pricelist']._get_applicable_rules_domain(
                products=product,
                date=fields.Datetime.now(),
                plan_id=plan_id,
            )
            no_pl_rule = self.env['product.pricelist.item'].search(domain, order='plan_id', limit=1)
            if no_pl_rule:
                return no_pl_rule._compute_price(
                    product, quantity, uom, date, currency, plan_id=plan_id, **kwargs,
                )
        return super()._compute_base_price(
            product, quantity, uom, date, currency, plan_id=plan_id, **kwargs
        )

    # === TOOLING === #

    def _get_recurring_rules_order(self):
        return f'pricelist_id, plan_id, {self._order}'
