# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.fields import Command

from odoo.addons.sale.tests.common import SaleCommon


class SaleRentingCommon(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Recurrence = cls.env['sale.temporal.recurrence']
        cls.recurrence_hour = Recurrence.create({'duration': 1, 'unit': 'hour'})
        cls.recurrence_day = Recurrence.create({'duration': 1, 'unit': 'day'})
        cls.recurrence_night_15_10 = Recurrence.create(
            {'duration': 24, 'unit': 'hour', 'overnight': True, 'pickup_time': 15, 'return_time': 10}
        )

        cls.projector = cls._create_product(
            name='Projector',
            type='consu',
            extra_hourly=7.0,
            extra_daily=30.0,
        )
        cls.env['product.pricing'].create({
            'price': 3.5,
            'product_template_id': cls.projector.product_tmpl_id.id,
            'recurrence_id': cls.recurrence_hour.id,
        })
        cls.rental_order = cls._create_rental_so()
        cls.projector_sol = cls.rental_order.order_line[0]
        cls.rental_order.action_confirm()

    @classmethod
    def _create_product(cls, **kwargs):
        if 'rent_ok' not in kwargs:
            kwargs['rent_ok'] = True
        return super()._create_product(**kwargs)

    @classmethod
    def _create_rental_so(cls, **values):
        default_values = {
            'partner_id': cls.partner.id,
            'order_line': [
                Command.create({
                    'product_id': cls.projector.id,
                    'product_uom_qty': 2.0,
                }),
            ],
            'rental_start_date': datetime(2023, 1, 1, hour=9),
            'rental_return_date': datetime(2023, 1, 1, hour=18),
            **values,
        }

        return cls.env['sale.order'].with_context(in_rental_app=True).create(default_values)
