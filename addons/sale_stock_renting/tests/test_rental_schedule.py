# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@tagged('post_install', '-at_install')
class TestRentalSchedule(SaleRentingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.quick_ref('sale_stock_renting.group_rental_stock_picking')

        cls.projector.is_storable = True
        cls.projector.tracking = 'serial'

        lots_to_create_vals = [
            {'product_id': cls.projector.id, 'name': lot_name}
            for lot_name in cls.env['stock.lot'].generate_lot_names('bilou-87', 5)
        ]
        cls.projector_lots = cls.env['stock.lot'].create(lots_to_create_vals)

    def test_warn_on_stock_quantity_inconsistency(self):
        # Get a time reference
        t = self.rental_order.rental_start_date
        conflicting_order = self._create_rental_so(
            order_line=[Command.create({
                'product_id': self.projector.id,
                'product_uom_qty': 4.0,  # 5 in stock but `self.rental_order` already asks for 2
            })],
            # Originally scheduled one week before
            rental_start_date=t - relativedelta(days=7),
            rental_return_date=t - relativedelta(days=6),
        )

        # Rescheduled for the next week but now conflicts with `self.rental_order`
        result = conflicting_order.order_line.web_gantt_write({
            'start_date': t,
            'return_date': t + relativedelta(days=1),
        })

        self.assertTrue(
            any(notif['code'] == 'stock_inconsistency' for notif in result['notifications'])
        )

    def test_warn_on_lot_overbooking(self):
        conflicting_order = self._create_rental_so(
            order_line=[Command.create({
                'product_id': self.projector.id,
                'product_uom_qty': 1.0,
            })],
            rental_start_date=self.rental_order.rental_start_date,
            rental_return_date=self.rental_order.rental_return_date,
        )
        self.rental_order.order_line.reserved_lot_ids = self.projector_lots[:2]

        # Reserve the first lot again at the same time as `self.rental_order`
        result = conflicting_order.order_line.web_gantt_write({
            'reserved_lot_ids': self.projector_lots[0].ids,
        })

        self.assertTrue(
            any(notif['code'] == 'lot_overbooking' for notif in result['notifications'])
        )

    def test_warn_on_missing_reserved_lots(self):
        result = self.projector_sol.web_gantt_write({
            'reserved_lot_ids': self.projector_lots[0].ids,
        })

        self.assertTrue(
            any(notif['code'] == 'insufficient_reserved_lots' for notif in result['notifications'])
        )
        self.assertTrue(result['actions'])  # Show the assign popup
