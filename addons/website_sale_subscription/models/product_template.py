# Part of Odoo. See LICENSE file for full copyright and licensing details.

from math import floor

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import format_amount


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('optional_product_ids')
    def _constraints_optional_product_ids(self):
        for template in self:
            if not template.recurring_invoice:
                continue
            plan_ids = set(template.subscription_rule_ids.plan_id.ids)
            for optional_template in template.optional_product_ids:
                if not optional_template.recurring_invoice:
                    continue
                optional_plan_ids = optional_template.subscription_rule_ids.plan_id.ids
                if not plan_ids.intersection(optional_plan_ids):
                    raise UserError(_('You cannot have an optional product that has a no common pricing\'s plan.'))

    def _website_can_be_added(self, product=None) -> bool:
        """Return whether the product/template can be added to the active SO."""
        self.ensure_one()
        if not self.recurring_invoice:
            return True

        if request.cart._has_one_time_sale() and not self.allow_one_time_sale:
            return False

        has_pricing = bool(
            self._get_recurring_pricing(
                pricelist=request.pricelist,
                variant=product,
                plan_id=request.cart.plan_id.id,
            )
        )
        if not has_pricing and not product:
            # If pricings are only defined by variant, there are no pricing applicable to the
            # template itself. In this situation, we need to search for a pricing on a variant
            # otherwise customers wouldn't be able to add the product to their cart.
            has_pricing = bool(
                self._get_recurring_pricing(
                    pricelist=request.pricelist,
                    variant=self.product_variant_id,
                    plan_id=request.cart.plan_id.id,
                )
            )

        return has_pricing or (
            self.allow_one_time_sale
            and not request.cart.plan_id
        )

    def _get_recurring_pricings(self, pricelist, variant=None, quantity=1.0):
        """Return the first pricing applicable for each of the available subscription plans."""
        self.ensure_one()

        pricings = self.env['product.pricelist.item']
        domain = pricelist._get_applicable_rules_domain(
            products=variant or self,
            date=fields.Datetime.now(),
            any_plan=True,
        )

        all_pricings = self.env['product.pricelist.item'].search(
            domain, order=self.env['product.pricelist.item']._get_recurring_rules_order()
        )
        if pricelist:
            # Add the rules not restricted to a specific pricelist, only for the plans that had no
            # rule for the current pricelist.
            domain = self.env['product.pricelist']._get_applicable_rules_domain(
                products=variant or self,
                date=fields.Datetime.now(),
                any_plan=True,
            )
            all_pricings |= self.env['product.pricelist.item'].search(
                Domain.AND([domain, [('plan_id', 'not in', all_pricings.plan_id.ids)]]),
                order=self.env['product.pricelist.item']._get_recurring_rules_order()
            )

        found_plan_ids = set()
        for pricing in all_pricings:
            if (
                (plan_id := pricing.plan_id.id) not in found_plan_ids
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                and pricing._is_applicable_for(product=variant or self, qty_in_product_uom=quantity)
            ):
                found_plan_ids.add(plan_id)
                pricings |= pricing

        return pricings

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        res = super()._get_additionnal_combination_info(product_or_template, quantity, uom, date, website)

        if not product_or_template.recurring_invoice:
            return res

        product = (product_or_template.is_product_variant and product_or_template) or self.env['product.product']
        pricings = self._get_recurring_pricings(pricelist=request.pricelist, variant=product, quantity=quantity)

        res['list_price'] = res['price']  # No pricelist discount for subscription prices

        if not pricings:
            res.update({
                'is_subscription': True,
                'is_plan_possible': False,
                'pricings': [],
                'allow_one_time_sale': not request.cart.plan_id and self.allow_one_time_sale,
            })
            return res

        to_year = {'year': 1, 'month': 12, 'week': 52}
        translation_mapping = {
            'year': _('year'),
            'month': _('month'),
            'week': _('week'),
        }

        # Find the plan with the shortest billing period to use as base for comparison
        base_plan = min(pricings.sudo().plan_id, key=lambda x: 1 / to_year[x.billing_period_unit])
        minimum_period = base_plan.billing_period_unit

        # Compute base period price and max price for discount calculation
        base_plan_pricings = pricings.filtered(lambda pr: pr.plan_id == base_plan)
        base_period_price = min(base_plan_pricings.mapped('fixed_price'), default=0.0)
        max_price = max(pricings.mapped('fixed_price'), default=0.0)

        currency = website.currency_id
        requested_plan = request and request.params.get('plan_id')
        requested_plan_id = requested_plan and requested_plan.isdigit() and int(requested_plan)
        requested_plan_id = requested_plan_id or request.cart.plan_id.id
        if requested_plan_id:
            chosen_pricing = pricings.filtered(lambda pricing: pricing.plan_id.id == requested_plan_id) or pricings[0]
        else:
            chosen_pricing = pricings[0]

        sales_price = res['price']

        def _get_pricing_data(pricing):
            if not pricing:
                return {}

            price = pricing._compute_price(
                product=product_or_template,
                quantity=quantity or 1.0,
                date=date,
                uom=product_or_template.uom_id,
                currency=currency,
                plan_id=pricing.plan_id.id,
            )

            if res.get('product_taxes', False):
                price = self.env['product.template']._apply_taxes_to_price(
                    price, currency, res['product_taxes'], res['taxes'], product_or_template,
                )

            price_format = format_amount(self.env, amount=price, currency=currency)
            pricing_plan_sudo = pricing.plan_id.sudo()  # Not accessible to public users
            price_in_minimum_period = (
                price
                / pricing_plan_sudo.billing_period_value
                * to_year[pricing_plan_sudo.billing_period_unit]
                / to_year[minimum_period]
            )

            if product_or_template.type == 'consu':
                # For consumable products, use billing period (e.g., "3 month") instead of plan name
                value = pricing.plan_id.billing_period_value
                table_name = f"{value if value != 1 else ''} {pricing.plan_id.billing_period_unit}".strip()
            else:
                # For non-consumable products, use plan name with non-breaking spaces
                table_name = pricing.plan_id.name.replace(" ", "\u00A0")

            pricing_data = {
                'plan_id': pricing_plan_sudo.id,
                'price': f"{pricing.plan_id.name}: {price_format}",
                'price_value': price,
                'table_price': price_format,
                'table_name': table_name,
                'to_minimum_billing_period': f'{format_amount(self.env, amount=price_in_minimum_period, currency=currency)}'
                                             f' / {translation_mapping.get(minimum_period, minimum_period)}',
                'can_be_added': request.cart.plan_id.id in (pricing_plan_sudo.id, False),
            }

            # Calculate discount percentage
            if product_or_template.allow_one_time_sale and 0 < price <= sales_price:  # One-time sale: compare against sale price
                discount = ((sales_price - price) * 100) / sales_price
            elif (product_or_template.type == 'consu' and 0 < price <= max_price):  # Consumables: compare against max price
                discount = ((max_price - price) * 100) / max_price
            elif 0 < price_in_minimum_period <= base_period_price:  # Non-consumables: compare against base period price
                discount = ((base_period_price - price_in_minimum_period) * 100) / base_period_price
            else:
                discount = 0.0
            pricing_data['discounted_price'] = floor(discount) if discount > 0 else 0.0

            return pricing_data

        default_pricing_data = _get_pricing_data(chosen_pricing)

        pricing_details = [
            _get_pricing_data(pricing)
            for pricing in pricings
        ]

        unit_price = default_pricing_data.get('price_value', 0)
        return {
            **res,
            'is_subscription': True,
            'pricings': pricing_details,
            'is_plan_possible': bool(chosen_pricing),
            'price': unit_price,
            'subscription_default_pricing_price': default_pricing_data.get('price', ''),
            'subscription_default_pricing_plan_id': default_pricing_data.get('plan_id', False),
            'subscription_pricing_select': (product_or_template.allow_one_time_sale or len(pricings) > 1) and not request.cart.plan_id,
            'prevent_zero_price_sale': website.prevent_zero_price_sale and currency.is_zero(
                unit_price,
            ),
            'allow_one_time_sale': not request.cart.plan_id and self.allow_one_time_sale,
            'allow_recurring': not request.cart._has_one_time_sale(),
        }

    # Search bar
    def _search_render_results_prices(self, mapping, combination_info):
        if not combination_info.get('is_subscription'):
            return super()._search_render_results_prices(mapping, combination_info)

        if not combination_info['is_plan_possible']:
            return '', 0

        return self.env['ir.ui.view']._render_template(
            'website_sale_subscription.subscription_search_result_price',
            values={
                'subscription_default_pricing_price': combination_info['subscription_default_pricing_price'],
            }
        ), 0

    def _get_sales_prices(self, website):
        prices = super()._get_sales_prices(website)

        pricelist = request.pricelist
        currency = website.currency_id
        fiscal_position_sudo = request.fiscal_position
        so_plan_id = request.cart.plan_id.id
        date = fields.Date.context_today(self)

        for template in self:
            if not template.recurring_invoice:
                continue

            pricing = template._get_recurring_pricing(pricelist=pricelist, plan_id=so_plan_id)
            if not pricing:
                prices[template.id].update({
                    'is_subscription': True,
                    'is_plan_possible': False,
                })
                continue

            unit_price = pricing._compute_price(
                product=template,
                quantity=1.0,
                date=date,
                uom=template.uom_id,
                currency=currency,
                plan_id=so_plan_id,
            )

            # taxes application
            product_taxes = template.sudo().taxes_id.filtered(lambda t: t.company_id == t.env.company)
            if product_taxes:
                taxes = fiscal_position_sudo.map_tax(product_taxes)
                unit_price = self.env['product.template']._apply_taxes_to_price(
                    unit_price, currency, product_taxes, taxes, template)

            plan_sudo = pricing.plan_id.sudo()
            prices[template.id].update({
                'is_subscription': True,
                'price_reduce': unit_price,
                'is_plan_possible': True,  # The plan can only be valid at this point
                'temporal_unit_display': plan_sudo.billing_period_display_sentence,
            })

        return prices

    def _website_show_quick_add(self):
        self.ensure_one()
        return super()._website_show_quick_add() and self._website_can_be_added()

    def _can_be_added_to_cart(self):
        self.ensure_one()
        return super()._can_be_added_to_cart() and self._website_can_be_added()
