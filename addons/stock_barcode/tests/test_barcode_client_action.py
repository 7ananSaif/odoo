# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestBarcodeClientAction(HttpCase):
    def setUp(self):
        super(TestBarcodeClientAction, self).setUp()
        # Disables the sound effect so we don't go crazy while running the test tours locally.
        self.env['ir.config_parameter'].set_param('stock_barcode.mute_sound_notifications', True)

        self.uid = self.env.ref('base.user_admin').id

        self.env.user.email = 'info@example.com'
        self.supplier_location = self.env.ref('stock.stock_location_suppliers')
        self.customer_location = self.env.ref('stock.stock_location_customers')
        # Create a company and a warehouse dedicated to the tests and configure its locations.
        self.company = self.env['res.company'].create({'name': "Test Company"})
        self.env.user.company_id = self.company
        self.warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)])
        self.warehouse.update({'name': 'Test Warehouse', 'code': 'WH'})
        self.stock_location = self.warehouse.lot_stock_id
        self.stock_location.barcode = 'LOC-01-00-00'
        self.warehouse.wh_input_stock_loc_id.barcode = 'WHINPUT'
        self.warehouse.wh_qc_stock_loc_id.barcode = 'WHQUALITY'
        self.warehouse.wh_output_stock_loc_id.barcode = 'WHOUTPUT'
        self.warehouse.wh_pack_stock_loc_id.barcode = 'WHPACKING'
        self.shelf3 = self.env['stock.location'].create({
            'name': 'Section 3',
            'location_id': self.stock_location.id,
            'barcode': 'shelf3',
        })
        self.shelf1 = self.env["stock.location"].create({
            'name': 'Section 1',
            'location_id': self.stock_location.id,
            'barcode': 'LOC-01-01-00',
        })
        self.shelf2 = self.env['stock.location'].create({
            'name': 'Section 2',
            'location_id': self.stock_location.id,
            'barcode': 'LOC-01-02-00',
        })
        self.shelf4 = self.env['stock.location'].create({
            'name': 'Section 4',
            'location_id': self.stock_location.id,
            'barcode': 'shelf4',
        })
        self.picking_type_in = self.warehouse.in_type_id
        self.picking_type_internal = self.warehouse.int_type_id
        self.picking_type_out = self.warehouse.out_type_id
        self.picking_type_out.restrict_scan_source_location = 'mandatory'

        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.uom_dozen = self.env.ref('uom.product_uom_dozen')

        # Two stockable products without tracking
        self.product1 = self.env['product.product'].create({
            'name': 'product1',
            'default_code': 'TEST',
            'is_storable': True,
            'barcode': 'product1',
        })
        self.product2 = self.env['product.product'].create({
            'name': 'product2',
            'is_storable': True,
            'barcode': 'product2',
        })
        self.productserial1 = self.env['product.product'].create({
            'name': 'productserial1',
            'is_storable': True,
            'barcode': 'productserial1',
            'tracking': 'serial',
        })
        self.productlot1 = self.env['product.product'].create({
            'name': 'productlot1',
            'is_storable': True,
            'barcode': 'productlot1',
            'tracking': 'lot',
        })
        self.package = self.env['stock.package'].create({
            'name': 'P00001',
        })
        self.owner = self.env['res.partner'].create({
            'name': 'Azure Interior',
        })

        # Creates records specific to GS1 use cases.
        self.product_tln_gtn8 = self.env['product.product'].create({
            'name': 'Battle Droid',
            'default_code': 'B1',
            'is_storable': True,
            'tracking': 'lot',
            'barcode': '76543210',  # (01)00000076543210 (GTIN-8 format)
            'uom_id': self.env.ref('uom.product_uom_unit').id
        })

        # Remove all access rights linked to stock application to "reset" Inventory settings.
        group_uom_id = self.ref('uom.group_uom')
        self.env.ref('base.group_user').write({'implied_ids': [
            Command.unlink(group_uom_id),
            Command.unlink(self.ref('stock.group_stock_multi_locations')),
            Command.unlink(self.ref('stock.group_stock_multi_warehouses')),
            Command.unlink(self.ref('stock.group_production_lot')),
            Command.unlink(self.ref('stock.group_tracking_lot')),
        ]})
        self.env.user.write({'group_ids': [Command.unlink(group_uom_id)]})
        self.call_count = 0

    def tearDown(self):
        self.call_count = 0
        super(TestBarcodeClientAction, self).tearDown()

    def _get_client_action_url(self, picking_id):
        return f'/odoo/{picking_id}/action-stock_barcode.stock_barcode_picking_client_action'
