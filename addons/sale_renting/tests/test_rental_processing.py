# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo.tests import Form, tagged
from odoo.tests.common import freeze_time

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@tagged('post_install', '-at_install')
class TestRentalProcessing(SaleRentingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rental_order.company_id.min_extra_hour = 2

    def test_add_late_fee(self):
        self.assertEqual(len(self.rental_order.order_line), 1)  # Only the projector
        self.projector_sol.qty_delivered = self.projector_sol.product_uom_qty
        self.assertEqual(self.rental_order.has_pickable_lines, False)

        with freeze_time(self.rental_order.rental_return_date + relativedelta(days=1)):
            wizard_form = Form.from_action(self.env, self.rental_order.action_open_return())
            wizard_form.rental_wizard_line_ids.qty_returned = self.projector_sol.qty_delivered
            wizard_form.save()
            wizard_form.record.apply()

        # Customer was late, a fee was added to the order
        self.assertEqual(self.rental_order.rental_status, 'returned')
        self.assertEqual(len(self.rental_order.order_line), 2)

    def test_late_fee_allow_buffer(self):
        self.assertEqual(len(self.rental_order.order_line), 1)  # Only the projector
        self.projector_sol.qty_delivered = self.projector_sol.product_uom_qty
        self.assertEqual(self.rental_order.has_pickable_lines, False)

        with freeze_time(self.rental_order.rental_return_date + relativedelta(minutes=30)):
            wizard_form = Form.from_action(self.env, self.rental_order.action_open_return())
            wizard_form.rental_wizard_line_ids.qty_returned = self.projector_sol.qty_delivered
            wizard_form.save()
            wizard_form.record.apply()

        # Customer was late, but less than the company policy, no fee is added
        self.assertEqual(self.rental_order.rental_status, 'returned')
        self.assertEqual(len(self.rental_order.order_line), 1)
