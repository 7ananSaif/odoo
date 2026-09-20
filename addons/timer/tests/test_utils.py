# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from odoo.addons.timer.utils.timer_utils import round_time_spent


@tagged('post_install', '-at_install')
class TestUtils(TransactionCase):
    def test_timer_round_time_spent(self):
        minutes_spent, minimum, rounding = 4.5, 10, 5
        result = round_time_spent(minutes_spent, minimum, rounding)
        self.assertEqual(result, 10, 'It should have been round to the minimum amount')

        minutes_spent = 12.4
        result = round_time_spent(minutes_spent, minimum, rounding)
        self.assertEqual(result, 15, 'It should have been round to the next multiple of 15')
