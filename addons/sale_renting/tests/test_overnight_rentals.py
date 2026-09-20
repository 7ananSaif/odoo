# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from odoo.addons.sale_renting.tests.common import SaleRentingCommon


@tagged('post_install', '-at_install')
class TestOvernightRentals(SaleRentingCommon):

    def test_switching_from_to_overnight_period(self):
        # Switching from night should reset the night specific fields
        self.recurrence_night_15_10.displayed_unit = 'day'
        self.assertEqual(self.recurrence_night_15_10.unit, 'day')
        self.assertFalse(self.recurrence_night_15_10.overnight)
        self.assertFalse(self.recurrence_night_15_10.pickup_time)
        self.assertFalse(self.recurrence_night_15_10.return_time)

        # Switching to night should set the night specific fields
        self.recurrence_night_15_10.displayed_unit = 'night'
        self.assertTrue(self.recurrence_night_15_10.overnight)
        self.assertEqual(self.recurrence_night_15_10.duration, 24)
        self.assertEqual(self.recurrence_night_15_10.unit, 'hour')

    def test_converted_duration_and_label_for_overnight_period(self):
        """Test displayed durations and units are properly converted for overnight period."""
        duration, unit_label = self.recurrence_night_15_10._get_converted_duration_and_label(24)
        self.assertEqual((duration, unit_label), (1, 'Night'))
        duration, unit_label = self.recurrence_night_15_10._get_converted_duration_and_label(48)
        self.assertEqual((duration, unit_label), (2, 'Nights'))
        duration, unit_label = self.recurrence_hour._get_converted_duration_and_label(24)
        self.assertEqual((duration, unit_label), (24, 'Hours'))

    def test_unique_night_period(self):
        """The overnight period cannot be mixed with other periods for the same product."""
        with self.assertRaises(
                ValidationError, msg="Night period cannot be mixed with other rental periods."
        ):
            self.env['product.pricing'].create({
                'product_template_id': self.projector.product_tmpl_id.id,
                'recurrence_id': self.recurrence_night_15_10.id,
            })
