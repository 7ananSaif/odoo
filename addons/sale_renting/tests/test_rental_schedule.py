# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@tagged('post_install', '-at_install')
class TestRentalSchedule(SaleRentingCommon):

    def test_start_date_fixed_when_partialy_picked(self):
        self.projector_sol.qty_delivered = 1.0

        with self.assertRaises(UserError):
            self.projector_sol.web_gantt_write(
                {'start_date': self.rental_order.rental_start_date - relativedelta(days=1)}
            )

    def test_start_date_fixed_when_picked(self):
        self.projector_sol.qty_delivered = 2.0

        with self.assertRaises(UserError):
            self.projector_sol.web_gantt_write(
                {'start_date': self.rental_order.rental_start_date - relativedelta(days=1)}
            )

    def test_return_date_editable_when_partialy_returned(self):
        self.projector_sol.qty_delivered = 2.0
        self.projector_sol.qty_returned = 1.0

        new_return_date = self.rental_order.rental_return_date + relativedelta(days=1)
        self.projector_sol.web_gantt_write({'return_date': new_return_date})

        # Should allow until all items are returned
        self.assertEqual(new_return_date, self.rental_order.rental_return_date)

    def test_return_date_fixed_when_returned(self):
        self.projector_sol.qty_delivered = 2.0
        self.projector_sol.qty_returned = 2.0

        with self.assertRaises(UserError):
            self.projector_sol.web_gantt_write(
                {'return_date': self.rental_order.rental_return_date + relativedelta(days=1)}
            )

    def test_recompute_rental_prices_on_duration_changes_case_no_change(self):
        with patch(
            'odoo.addons.sale_renting.models.sale_order.SaleOrder.action_update_rental_prices', return_value=None
        ) as mock_action_update_rental_prices:
            self.projector_sol.web_gantt_write({
                # Order is pushed one day later, but the duration stays the same
                'start_date': self.rental_order.rental_start_date + relativedelta(days=1),
                'return_date': self.rental_order.rental_return_date + relativedelta(days=1),
            })

        mock_action_update_rental_prices.assert_not_called()

    def test_recompute_rental_prices_on_duration_changes_case_change(self):
        with patch(
            'odoo.addons.sale_renting.models.sale_order.SaleOrder.action_update_rental_prices',
            return_value=None,
        ) as mock_action_update_rental_prices:
            result = self.projector_sol.web_gantt_write({
                'start_date': self.rental_order.rental_start_date - relativedelta(days=1),
                'return_date': self.rental_order.rental_return_date + relativedelta(days=1),
            })

        mock_action_update_rental_prices.assert_called_once()
        self.assertTrue(  # Notify the user
            any(notif['code'] == 'rental_price_update' for notif in result['notifications'])
        )
