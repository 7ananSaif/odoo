# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import groupby


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    recurring_invoice = fields.Boolean(
        string="Subscription Product",
        help="If set, confirming a sale order with this product will create a subscription",
    )
    allow_one_time_sale = fields.Boolean(
        string="Accept One-Time",
        help="Define if the subscription product can also be bought as a one-time.",
    )
    allow_prorated_price = fields.Boolean(
        string="Prorated Price",
        help="Define if price must be prorated or not for incomplete periods (upsell, calendar alignment, etc.)",
        compute="_compute_allow_prorated_price",
        store=True,
        readonly=False,
    )

    subscription_rule_ids = fields.One2many(
        comodel_name='product.pricelist.item',
        inverse_name='product_tmpl_id',
        string="Subscription Pricings",
        domain=lambda self: self._domain_subscription_rule_ids(),
        bypass_search_access=True,
        copy=False,
        groups='sales_team.group_sale_salesman',
    )
    # Just like the other subscription_rule_ids field but only including fixed price rules.
    # This is needed to use in the Recurring Prices list view in the product form.
    subscription_rule_ids_fixed = fields.One2many(
        comodel_name='product.pricelist.item',
        inverse_name='product_tmpl_id',
        string="Fixed Subscription Pricings",
        domain=lambda self: self._domain_subscription_rule_ids_fixed(),
        bypass_search_access=True,
        copy=False,
        groups='sales_team.group_sale_salesman',
    )
    display_subscription_pricing = fields.Char(
        string='Display Price', compute='_compute_display_subscription_pricing',
    )

    def _domain_subscription_rule_ids(self):
        return Domain.AND([
            self._base_domain_item_ids(),
            [('plan_id', '!=', False)],
        ])

    def _domain_subscription_rule_ids_fixed(self):
        """
        Alternative domain computation for the subscription_rule_ids
        field that filters out every record except the ones where
        the price is fixed (not computed)
        """
        return Domain.AND([
            self._domain_subscription_rule_ids(),
            [('compute_price', '=', 'fixed')],
        ])

    def _domain_pricelist_rule_ids(self):
        # Recurring rules shouldn't be shown in standard pricelist rules
        return Domain.AND([
            super()._domain_pricelist_rule_ids(),
            [('plan_id', '=', False)]
        ])

    @api.model
    def _get_incompatible_types(self):
        return ['recurring_invoice'] + super()._get_incompatible_types()

    @api.onchange('recurring_invoice')
    def _onchange_recurring_invoice(self):
        """
        Raise a warning if the user has checked 'Subscription Product'
        while the product has already been sold.
        In this case, the 'Subscription Product' field is automatically
        unchecked.
        """
        confirmed_lines = self.env['sale.order.line'].search([
            ('product_template_id', 'in', self.ids),
            ('state', '=', 'sale')])
        if confirmed_lines:
            self.recurring_invoice = not self.recurring_invoice
            return {'warning': {
                'title': _("Warning"),
                'message': _(
                    "You can not change the recurring property of this product because it has been sold already.")
            }}

    @api.depends('type', 'recurring_invoice', 'invoice_policy')
    def _compute_allow_prorated_price(self):
        for template in self:
            if template.recurring_invoice and template.type == 'service' and template.invoice_policy != 'delivery':
                template.allow_prorated_price = True
            else:
                template.allow_prorated_price = False

    @api.depends('subscription_rule_ids')
    def _compute_display_subscription_pricing(self):
        self.display_subscription_pricing = False
        for template in self:
            template.display_subscription_pricing = template._get_recurring_pricing(
                pricelist=template.env['product.pricelist']
            ).price

    @api.constrains('type', 'combo_ids', 'recurring_invoice')
    def _check_subscription_combo_ids(self):
        for template in self:
            if (
                template.type == 'combo'
                and template.recurring_invoice
                and any(
                    not product.recurring_invoice
                    for product in template.combo_ids.combo_item_ids.product_id
                )
            ):
                raise ValidationError(
                    _("A subscription combo product can only contain subscription products.")
                )

    def copy(self, default=None):
        copied_tmpls = super().copy(default)
        for template, template_copy in zip(self, copied_tmpls, strict=True):

            if template.company_id != template_copy.company_id:
                # Don't duplicate pricings when the copy belongs to another company to
                # avoid multi-company issues.
                continue

            # User duplicating the template might not have access to pricings
            template_sudo = template.sudo()

            # Force the order to be on id, since the others keys will have the same value/order
            # This guarantees the order of the copied pricings is the same as the original ones
            # regardless of the 'id desc' in the _order of product.pricelist.item model.
            template_pricings = template_sudo.subscription_rule_ids.sorted('id')

            # Duplicate template rules
            variant_specific_pricings = template_pricings.filtered('product_id')
            (template_pricings - variant_specific_pricings).copy({
                'product_tmpl_id': template_copy.id,
            })

            # Duplicate variant-specific rules
            if variant_specific_pricings:
                variant_mapping = dict(zip(
                    template_sudo.product_variant_ids.ids,
                    template_copy.product_variant_ids.ids,
                    strict=True,
                ))

                for product_id, pricings in groupby(
                    variant_specific_pricings,
                    lambda pricing: pricing.product_id.id
                ):
                    if product_id not in variant_mapping:
                        # Pricings of inactive variants should not be copied
                        # (removed combinations, archived products ...)
                        continue
                    self.env['product.pricelist.item'].sudo().concat(*pricings).copy({
                        'product_tmpl_id': template_copy.id,
                        'product_id': variant_mapping.get(product_id),
                    })

        return copied_tmpls

    @api.model
    def _get_configurator_price(
        self, product_or_template, quantity, date, currency, pricelist, *, plan_id=None, **kwargs
    ):
        """Override of `sale` to compute the subscription price.

        :param product.product|product.template product_or_template: The product for which to get
            the price.
        :param int quantity: The quantity of the product.
        :param datetime date: The date to use to compute the price.
        :param res.currency currency: The currency to use to compute the price.
        :param product.pricelist pricelist: The pricelist to use to compute the price.
        :param int|None plan_id: The subscription plan of the product, as a `sale.subscription.plan`
            id.
        :param dict kwargs: Locally unused data passed to `super`.
        :rtype: float
        :return: The specified product's price.
        """
        if product_or_template.recurring_invoice and not plan_id:
            if product_or_template.is_product_variant:
                template, variant = product_or_template.product_tmpl_id, product_or_template
            else:
                template, variant = product_or_template, None

            # get the default pricing and plan since the plan has not yet been chosen
            pricing = template._get_recurring_pricing(
                pricelist=pricelist, variant=variant, quantity=quantity,
            )
            if pricing:
                return (
                    pricing._compute_price(
                        product_or_template,
                        quantity,
                        uom=product_or_template.uom_id,
                        date=date,
                        currency=currency,
                    ),
                    pricing.id
                )

        return super()._get_configurator_price(
            product_or_template, quantity, date, currency, pricelist, plan_id=plan_id, **kwargs
        )

    @api.model
    def _get_additional_configurator_data(
        self, product_or_template, date, currency, pricelist, *, quantity=1.0, plan_id=None, **kwargs
    ):
        """Override of `sale` to append subscription data.

        :param product.product|product.template product_or_template: The product for which to get
            additional data.
        :param datetime date: The date to use to compute prices.
        :param res.currency currency: The currency to use to compute prices.
        :param product.pricelist pricelist: The pricelist to use to compute prices.
        :param int|None plan_id: The subscription plan of the product, as a `sale.subscription.plan`
            id.
        :param dict kwargs: Locally unused data passed to `super`.
        :rtype: dict
        :return: A dict containing additional data about the specified product.
        """
        data = super()._get_additional_configurator_data(
            product_or_template, date, currency, pricelist, plan_id=plan_id, **kwargs
        )

        if product_or_template.recurring_invoice:
            if product_or_template.is_product_variant:
                template, variant = product_or_template.product_tmpl_id, product_or_template
            else:
                template, variant = product_or_template, None

            pricing = template._get_recurring_pricing(
                pricelist=pricelist, variant=variant, plan_id=plan_id, quantity=quantity,
            )
            if pricing:
                data['price_info'] = pricing.plan_id.sudo().billing_period_display_sentence

        return data

    def _get_recurring_pricing(self, pricelist, variant=None, plan_id=None, quantity=1.0):
        self.ensure_one()
        product_or_template = variant or self
        domain = pricelist._get_applicable_rules_domain(
            products=product_or_template,
            date=fields.Datetime.now(),
            plan_id=plan_id,
            # If no plan is given, return the first one with a plan, to be used as default pricing
            any_plan=True,
        )
        order = self.env['product.pricelist.item']._get_recurring_rules_order()
        pricing = self.env['product.pricelist.item'].search(domain, order=order).filtered(
            lambda ppi: ppi._is_applicable_for(
                product=product_or_template,
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                qty_in_product_uom=quantity,
            )
        )[:1]

        if pricing or not pricelist:
            return pricing

        # If the current pricelist has no recurring rules, the recurring price (and plans) will be
        # decided by the recurring rules not linked to a specific pricelist.
        domain = self.env['product.pricelist']._get_applicable_rules_domain(
            products=variant or self,
            date=fields.Datetime.now(),
            plan_id=plan_id,
            # If no plan is given, return the first one with a plan, to be used as default pricing
            any_plan=True,
        )
        return self.env['product.pricelist.item'].search(domain, order=order).filtered(
            lambda ppi: ppi._is_applicable_for(
                product=product_or_template,
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                qty_in_product_uom=quantity,
            )
        )[:1]

    def _has_multiple_uoms(self):
        # multi-uoms doesn't work with subscription (for now)
        if self.recurring_invoice:
            return False
        return super()._has_multiple_uoms()
