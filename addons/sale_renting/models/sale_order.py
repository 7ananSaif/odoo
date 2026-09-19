# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from math import ceil

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools import float_compare


RENTAL_STATUS = [
    ('draft', "Quotation"),
    ('sent', "Quotation Sent"),
    ('pickup', "Reserved"),
    ('return', "Pickedup"),
    ('returned', "Returned"),
    ('cancel', "Cancelled"),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    _rental_period_coherence = models.Constraint(
        'CHECK(rental_start_date < rental_return_date)',
        "The rental start date must be before the rental return date if any.",
    )

    @api.model
    def default_get(self, fields):
        """Override to map relevant default `sale.order.line` fields to `sale.order` fields.

        Mainly used to create a new rental order from the rental schedule view, as it works on
        `sale.order.line` records.

        :param Sequence[str] fields: Fields without values.
        :return: A dictionary mapping the default field values.
        :rtype: dict[str, Any]
        """
        defaults = super().default_get(fields)

        if self.env.context.get('convert_default_order_line_values'):
            missing_fields = set(fields) - defaults.keys()

            SO_TO_SOL_FIELDS_MAPPING = [
                ('partner_id', 'order_partner_id'),
                ('rental_start_date', 'start_date'),
                ('rental_return_date', 'return_date'),
            ]
            for so_fname, sol_fname in SO_TO_SOL_FIELDS_MAPPING:
                if so_fname in missing_fields and (
                    default_value := self.env.context.get(f'default_{sol_fname}')
                ):
                    defaults[so_fname] = default_value

            if 'order_line' in missing_fields:
                defaults['order_line'] = [self._build_default_order_line_values()]

            # Convert added default values to the right format (see also `BaseModel.default_get`)
            for fname in defaults.keys() & missing_fields:
                field = self._fields[fname]
                value = field.convert_to_cache(defaults[fname], self, validate=False)
                defaults[fname] = field.convert_to_write(value, self)

        return defaults

    def _build_default_order_line_values(self):
        """Generate default values for `sale.order.line` based on context keys prefixed with
        'default_'."""
        # Extract field names from context keys that start with 'default_'
        default_field_names = (
            key.replace('default_', '', 1)  # Remove the 'default_' prefix
            for key in self.env.context
            if key.startswith('default_')
        )
        # Filter field names to include only those that exist in `sale.order.line` fields
        sol_field_names = (
            field_name
            for field_name in default_field_names
            if field_name in self.env['sale.order.line']._fields
        )

        return {
            'product_uom_qty': 1.0,
            **{
                field_name: self.env.context[f'default_{field_name}']
                for field_name in sol_field_names
            },
        }

    #=== FIELDS ===#

    is_rental_order = fields.Boolean(
        string="Created In App Rental",
        compute='_compute_is_rental_order',
        store=True, precompute=True, readonly=False,
        # By default, all orders created in rental app are Rental Orders
        default=lambda self: self.env.context.get('in_rental_app'))
    has_rented_products = fields.Boolean(compute='_compute_has_rented_products')
    rental_start_date = fields.Datetime(string="Rental Start Date", tracking=True)
    rental_return_date = fields.Datetime(string="Rental Return Date", tracking=True)
    duration_days = fields.Integer(
        string="Duration in days",
        compute='_compute_duration',
        help="The duration in days of the rental period.",
    )
    remaining_hours = fields.Integer(
        string="Remaining duration in hours",
        compute='_compute_duration',
        help="The leftover hours of the rental period.",
    )
    show_update_duration = fields.Boolean(string="Has Duration Changed", store=False)

    rental_status = fields.Selection(
        selection=RENTAL_STATUS,
        string="Rental Status",
        compute='_compute_rental_status',
        store=True)
    # rental_status = next action to do basically, but shown string is action done.
    next_action_date = fields.Datetime(
        string="Next Action", compute='_compute_rental_status', store=True)

    has_pickable_lines = fields.Boolean(compute='_compute_has_action_lines')
    has_returnable_lines = fields.Boolean(compute='_compute_has_action_lines')

    is_late = fields.Boolean(
        string="Is overdue",
        help="The products haven't been picked-up or returned in time."
             " This excludes any grace period before late fees apply.",
        compute='_compute_is_late',
        search='_search_is_late',
    )

    #=== COMPUTE METHODS ===#

    @api.depends('order_line.is_rental')
    def _compute_is_rental_order(self):
        for order in self:
            # If a rental product is added in the rental app to the order, it becomes a rental order
            order.is_rental_order = order.is_rental_order or order.has_rented_products

    @api.depends('order_line.is_rental')
    def _compute_has_rented_products(self):
        for so in self:
            so.has_rented_products = any(line.is_rental for line in so.order_line)

    @api.depends('rental_start_date', 'rental_return_date')
    def _compute_duration(self):
        self.duration_days = 0
        self.remaining_hours = 0
        for order in self:
            if order.rental_start_date and order.rental_return_date:
                duration = order.rental_return_date - order.rental_start_date
                order.duration_days = duration.days
                order.remaining_hours = ceil(duration.seconds / 3600)

    @api.depends(
        'rental_start_date',
        'rental_return_date',
        'state',
        'order_line.is_rental',
        'order_line.product_uom_qty',
        'order_line.qty_delivered',
        'order_line.qty_returned',
    )
    def _compute_rental_status(self):
        self.next_action_date = False
        for order in self:
            if not order.is_rental_order:
                order.rental_status = False
            elif order.state != 'sale':
                order.rental_status = order.state
            # As soon as an item is picked, the order status turns to "Pickedup"
            elif order.has_returnable_lines:
                order.rental_status = 'return'
                order.next_action_date = order.rental_return_date
            elif order.has_pickable_lines:
                order.rental_status = 'pickup'
                order.next_action_date = order.rental_start_date
            else:
                order.rental_status = 'returned'

    @api.depends(
        'is_rental_order',
        'state',
        'order_line.is_rental',
        'order_line.product_uom_qty',
        'order_line.qty_delivered',
        'order_line.qty_returned',
    )
    def _compute_has_action_lines(self):
        self.has_pickable_lines = False
        self.has_returnable_lines = False
        for order in self:
            if order.state == 'sale' and order.is_rental_order:
                rental_order_lines = order.order_line.filtered(
                    lambda line: line.is_rental and line.product_type != 'combo'
                )
                order.has_pickable_lines = any(
                    sol.qty_delivered < sol.product_uom_qty for sol in rental_order_lines
                )
                order.has_returnable_lines = any(
                    sol.qty_returned < sol.qty_delivered for sol in rental_order_lines
                )

    @api.depends('is_rental_order', 'next_action_date', 'rental_status')
    def _compute_is_late(self):
        now = fields.Datetime.now()
        for order in self:
            order.is_late = (
                order.is_rental_order
                and order.rental_status in ['pickup', 'return']  # has_pickable_lines or has_returnable_lines
                and order.next_action_date
                and order.next_action_date < now
            )

    # === SEARCH METHODS === #

    def _search_is_late(self, operator, value):
        if operator != 'in' and True not in value:
            return NotImplemented

        return Domain([
            ('is_rental_order', '=', True),
            ('rental_status', 'in', ('pickup', 'return')),
            ('next_action_date', '!=', False),
            ('next_action_date', '<', 'now'),
        ])

    #=== ONCHANGE METHODS ===#

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id_show_update_prices(self):
        """Override of `sale` to not show the "Update Prices" button when creating a new order from
        the rental schedule."""
        if (
            self.env.context.get('in_rental_schedule')
            and self.env.context.get('sale_onchange_first_call')
        ):
            return
        return super()._onchange_pricelist_id_show_update_prices()

    @api.onchange('company_id')
    def _onchange_company_id_warning(self):
        """Override of `sale` to not show the "Update Prices" button when creating a new order from
        the rental schedule."""
        if (
            self.env.context.get('in_rental_schedule')
            and self.env.context.get('sale_onchange_first_call')
        ):
            return
        return super()._onchange_company_id_warning()

    @api.onchange('rental_start_date', 'rental_return_date')
    def _onchange_duration_show_update_duration(self):
        # Hide the "Update Rental Prices" button when creating a new order from the rental schedule.
        if (
            self.env.context.get('in_rental_schedule')
            and self.env.context.get('sale_onchange_first_call')
        ):
            return

        self.show_update_duration = any(line.is_rental for line in self.order_line)

    @api.onchange('is_rental_order')
    def _onchange_is_rental_order(self):
        self.ensure_one()
        if self.is_rental_order:
            self._rental_set_dates()

    @api.onchange('rental_start_date')
    def _onchange_rental_start_date(self):
        self.order_line.filtered('is_rental')._compute_name()

    @api.onchange('rental_return_date')
    def _onchange_rental_return_date(self):
        self.order_line.filtered('is_rental')._compute_name()

    #=== ACTION METHODS ===#

    def action_update_rental_prices(self):
        self.ensure_one()
        self._recompute_rental_prices()
        self.message_post(body=_("Rental prices have been recomputed with the new period."))

    def _recompute_rental_prices(self):
        self.with_context(rental_recompute_price=True)._recompute_prices()

    def _get_update_prices_lines(self):
        """ Exclude non-rental lines from price recomputation"""
        lines = super()._get_update_prices_lines()
        if not self.env.context.get('rental_recompute_price'):
            return lines
        return lines.filtered('is_rental')

    # PICKUP / RETURN : rental.processing wizard

    def action_open_pickup(self):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        lines_to_pickup = self.order_line.filtered(
            lambda r:
                r.is_rental
                and r.product_type != 'combo'
                and float_compare(r.product_uom_qty, r.qty_delivered, precision_digits=precision) > 0)
        return self._open_rental_wizard('pickup', lines_to_pickup.ids)

    def action_open_return(self):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        lines_to_return = self.order_line.filtered(
            lambda r:
                r.is_rental
                and r.product_type != 'combo'
                and float_compare(r.qty_delivered, r.qty_returned, precision_digits=precision) > 0)
        return self._open_rental_wizard('return', lines_to_return.ids)

    def _open_rental_wizard(self, status, order_line_ids):
        context = {
            'order_line_ids': order_line_ids,
            'default_status': status,
            'default_order_id': self.id,
        }
        return {
            'name': _('Validate a pickup') if status == 'pickup' else _('Validate a return'),
            'view_mode': 'form',
            'res_model': 'rental.order.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

    def _get_portal_return_action(self):
        """ Return the action used to display orders when returning from customer portal. """
        if self.is_rental_order:
            return self.env.ref('sale_renting.rental_order_action')
        else:
            return super()._get_portal_return_action()

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        if self.is_rental_order:
            return domain | Domain([
                ('rent_ok', '=', True),
                ('company_id', 'in', [self.company_id.id, False]),
                ('type', '!=', 'combo'),
            ])
        return domain

    #=== TOOLING ===#

    def _rental_set_dates(self):
        self.ensure_one()
        if self.rental_start_date and self.rental_return_date:
            return

        start_date = fields.Datetime.now().replace(minute=0, second=0) + relativedelta(hours=1)
        return_date = start_date + relativedelta(days=1)
        self.update({
            'rental_start_date': start_date,
            'rental_return_date': return_date,
        })

    #=== BUSINESS METHODS ===#

    def _get_product_catalog_order_data(self, products, **kwargs):
        """ Override to add the rental dates for the price computation """
        return super()._get_product_catalog_order_data(
            products,
            start_date=self.rental_start_date,
            end_date=self.rental_return_date,
            **kwargs,
        )

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """ Override to add the context to mark the line as rental and the rental dates for the
        price computation
        """
        if self.is_rental_order:
            self = self.with_context(in_rental_app=True)
            product = self.env['product.product'].browse(product_id)
            if product.rent_ok:
                self._rental_set_dates()
        return super()._update_order_line_info(
            product_id,
            quantity,
            start_date=self.rental_start_date,
            end_date=self.rental_return_date,
            **kwargs,
        )

    def _get_action_add_from_catalog_extra_context(self):
        """ Override to add rental dates in the context for product availabilities. """
        extra_context = super()._get_action_add_from_catalog_extra_context()
        extra_context.update(start_date=self.rental_start_date, end_date=self.rental_return_date)
        return extra_context
