import json

from odoo.tests import HttpCase, tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestEpcEncoder(HttpCase):
    # To ensure correctness, validation data are themselves taken from https://www.gs1.org/services/epc-encoderdecoder
    def test_get_epc_sgtin(self):

        expected_responses = {
            ('09521141123454', False): {
                "000000000000": "3036451fd40c0e4000000000",
                "000000000001": "3036451fd40c0e4000000001",
                "009876543210": "3036451fd40c0e424cb016ea",
                "274877906943": "3036451fd40c0e7fffffffff",
                "274877906944": "An error occurred with field 'serial_integer': An error occurred with method '_encode_integer': Value 274877906944 cannot be represented with 38 bits",  # Invalid tracking number : 2^34 is out of bound
            },
            ('2349', True): {  # Though '2349' is not a valid GTIN length, we assume it to be '00000000002349'
                "Y00050": "3634000000003aacb060c1ab0000000000000000000000000000",
                "Z00050": "3634000000003aad3060c1ab0000000000000000000000000000",
                "!/%&+-*": "3634000000003a90af4a995ad540000000000000000000000000",
                "!/%&+-*$@@": "An error occurred with field 'serial_string': An error occurred with method '_encode_string': Value to encode contains invalid character(s): `$`, `@`",
                "!/%&+-*\\$$$$$####@ @@@@": "An error occurred with field 'serial_string': An error occurred with method '_encode_string': Value to encode contains invalid character(s): `\\`, `$`, `#`, `@`, ` `",
                "ThisIsWayTooLooooooooong": "An error occurred with field 'serial_string': An error occurred with method '_encode_string': Value 2069674681595411174842736530632876419756036725000752819815 cannot be represented with 140 bits",
            },
        }

        self.authenticate('admin', 'admin')

        for gtin_alpha, expected_epc in expected_responses.items():
            gtin, alphanumeric_tracking = gtin_alpha
            tracking_number_list = list(expected_epc.keys())

            payload = json.dumps({
                'params': {
                    "gtin" : gtin,
                    "tracking_number_list" : tracking_number_list,
                    "filter" : 1,
                    "company_prefix_length" : 7,
                    "alphanumeric_tracking" : alphanumeric_tracking,
                },
            })
            response = self.url_open(
                '/stock_barcode/get_epc_sgtin',
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            received_epc = response.json()['result']  # key is tracking number, value is epc
            self.assertDictEqual(expected_epc, received_epc)


@tagged('post_install', '-at_install')
class TestEpcIntegration(TransactionCase):
    def test_move_line_no_lot(self):
        stock_location = self.env.ref('stock.stock_location_stock')
        supplier_location = self.env.ref('stock.stock_location_suppliers')

        product_serial = self.env['product.product'].create({
            'name': 'Product S',
            'is_storable': True,
            'tracking': 'serial',
            'barcode': '11223344556677',
        })
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'location_id': supplier_location.id,
            'location_dest_id': stock_location.id,
            'state': 'draft',
        })
        move = self.env['stock.move'].create({
            'product_id': product_serial.id,
            'product_uom_qty': 30.0,
            'product_uom': product_serial.uom_id.id,
            'location_id': supplier_location.id,
            'location_dest_id': stock_location.id,
            'picking_id': picking.id,
            'state': 'draft',
        })
        picking.action_confirm()
        # move_lines don't have either a lot_id or a lot_name, resulting in an EPC calculation error
        self.assertIn("Error", move.move_line_ids[0].electronic_product_code)
