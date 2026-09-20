from odoo.tests import tagged
from ...product_barcodelookup.tests.test_barcodelookup_flow import TestBarcodelookup
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install', '-at_install')
class TestPOSBarcodelookup(TestPointOfSaleHttpCommon, TestBarcodelookup):
    def test_01_pos_barcodelookup_flow(self):
        with self.mockBarcodelookupAutofill():
            self.main_pos_config.open_ui()
            self.start_pos_tour('PosBarcodelookupFlow', login="accountman")
        product = self.env['product.template'].sudo().search([('name', '=', 'Odoo Scale up')], limit=1)
        self.assertEqual(product.name, "Odoo Scale up")
        self.assertEqual(product.list_price, 100)
        #  Product created from pos should be available_in_pos by default
        self.assertTrue(product.available_in_pos)
