# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from dateutil.relativedelta import relativedelta
from math import floor
from pytz import UTC, timezone

from odoo import fields, models
from odoo.http import request


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_default_start_date(self, pickup_time):
        """ Override to take the padding time into account """
        start_date = super()._get_default_start_date(pickup_time)

        now = fields.Datetime.now()
        hours_before_start_date = (start_date - now).total_seconds() / 3600
        if hours_before_start_date < self.preparation_time:
            # we need more time to prepare
            start_date = (now + relativedelta(hours=self.preparation_time))
            if pickup_time:
                # we need to respect the pickup time constraint
                website_tz = timezone(request.website.tz)
                # convert start_date in website TZ before replacing the hours
                pickup_hour = floor(pickup_time)
                start_date_website_tz = website_tz.localize(start_date).replace(
                    hour=pickup_hour,
                    minute=round((pickup_time - pickup_hour) * 60),
                )
                start_date = start_date_website_tz.astimezone(UTC).replace(tzinfo=None)
        return start_date

    def _filter_on_available_rental_products(self, from_date, to_date, warehouse_id):
        """
        Filters self on available record for the given period.

        It will return true if any variant has an available stock.
        """
        if to_date < from_date:
            return self.filtered(lambda p: not p.rent_ok)

        products_infinite_qty = products_finite_qty = self.env['product.template']
        for product in self:
            if not product.rent_ok or not product.is_storable or product.allow_out_of_stock_order:
                products_infinite_qty |= product
            else:
                products_finite_qty |= product

        if not products_finite_qty:
            return products_infinite_qty

        # Prefetch qty_available for all variants
        variants_to_check = products_finite_qty.with_context(
            from_date=from_date,
            to_date=to_date,
            warehouse_id=warehouse_id,
        ).product_variant_ids.filtered(lambda p: bool(p.qty_available > 0 or p.qty_in_rent > 0))
        templates_with_available_qty = self.env['product.template']
        if variants_to_check:
            search_domain = [
                ('is_rental', '=', True),
                ('product_id', 'in', variants_to_check.ids),
                ('state', 'in', ('sent', 'sale')),
                ('return_date', '>', from_date),
                '|', ('reservation_begin', '<', to_date),
                     ('qty_delivered', '>', 0),
                # We're in sudo, need to restrict the search to the SOL of the website company
                ('company_id', '=', self.env.company.id),
            ]
            if warehouse_id:
                # Only load SOLs targeting the same warehouse whose stock we're considering
                search_domain.append(('order_id.warehouse_id', '=', warehouse_id))
            sols = self.env['sale.order.line'].search(search_domain, order='reservation_begin asc')
            # Group SOL by product_id
            sol_by_variant = defaultdict(lambda: self.env['sale.order.line'])
            for sol in sols:
                sol_by_variant[sol.product_id] |= sol

            def has_any_available_qty(variant, sols):
                # Returns False if the rented quantity was higher or equal to the available qty at any point in time.
                rented_quantities, key_dates = sols._get_rented_quantities([from_date, to_date])
                max_rentable = variant.qty_available + variant.qty_in_rent
                for date in key_dates:
                    max_rentable -= rented_quantities[date]
                    if max_rentable <= 0:
                        return False
                return True

            templates_with_available_qty = variants_to_check.filtered(
                lambda v: v not in sol_by_variant or has_any_available_qty(v, sol_by_variant[v])
            ).product_tmpl_id

        return products_infinite_qty | templates_with_available_qty
