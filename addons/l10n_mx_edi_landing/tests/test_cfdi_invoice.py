from freezegun import freeze_time

from odoo.addons.l10n_mx_edi.tests.common import EXTERNAL_MODE
from odoo.addons.l10n_mx_edi_extended.tests.common import TestMxExtendedEdiCommon
from odoo.addons.stock_landed_costs.tests.common import TestStockLandedCostsCommon

from odoo import Command
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install', *(['-standard', 'external'] if EXTERNAL_MODE else []))
class TestCFDIInvoiceLanding(TestMxExtendedEdiCommon, TestStockLandedCostsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids = [Command.link(cls.env.ref("sales_team.group_sale_salesman").id)]

        cls.picking_in_1 = cls.Picking.create({
            'partner_id': cls.supplier_id,
            'picking_type_id': cls.warehouse.in_type_id.id,
            'location_id': cls.supplier_location_id,
            'state': 'draft',
            'location_dest_id': cls.warehouse.lot_stock_id.id,
        })
        cls.picking_in_2 = cls.Picking.create({
            'partner_id': cls.supplier_id,
            'picking_type_id': cls.warehouse.in_type_id.id,
            'location_id': cls.supplier_location_id,
            'state': 'draft',
            'location_dest_id': cls.warehouse.lot_stock_id.id,
        })
        cls.product_customs = cls.env['product.product'].create({
            'name': 'Test product template with customs',
            'is_storable': True,
            'list_price': 1000.0,
            'categ_id': cls.stock_account_product_categ.id,
            'unspsc_code_id': cls.env.ref('product_unspsc.unspsc_code_01010101').id,
            'tracking': 'lot',
            'l10n_mx_edi_use_customs_invoicing': True,
            'invoice_policy': 'delivery',
            'lot_valuated': True,
            'taxes_id': [Command.link(cls.tax_16.id)],
        })

        cls.no_customs_product = cls.env['product.product'].create({
            'name': 'Test product template without customs',
            'is_storable': True,
            'categ_id': cls.stock_account_product_categ.id,
            'tracking': 'lot',
        })
        cls.Move.create([
            {
                'product_id': cls.product_customs.id,
                'product_uom_qty': 10,
                'product_uom': cls.product_customs.uom_id.id,
                'picking_id': cls.picking_in_1.id,
                'location_id': cls.supplier_location_id,
                'location_dest_id': cls.warehouse.lot_stock_id.id
            },
            {
                'product_id': cls.product_customs.id,
                'product_uom_qty': 10,
                'product_uom': cls.product_customs.uom_id.id,
                'picking_id': cls.picking_in_2.id,
                'location_id': cls.supplier_location_id,
                'location_dest_id': cls.warehouse.lot_stock_id.id
            },
        ])

    def test_landed_cost_set_customs_number(self):
        """Test that landed cost is correctly set only on products with valid customs configuration
        and that the name is computed correctly when setting and changing the landing cost"""
        lot_name = "TESTLOT01"
        self.Move.create({
            'product_id': self.no_customs_product.id,
            'product_uom_qty': 10,
            'product_uom': self.no_customs_product.uom_id.id,
            'picking_id': self.picking_in_1.id,
            'location_id': self.supplier_location_id,
            'location_dest_id': self.warehouse.lot_stock_id.id
        })
        self.picking_in_1.action_confirm()
        self.picking_in_1.move_line_ids.write({'lot_name': lot_name})
        self.picking_in_1.button_validate()

        landing_cost = self.env['stock.landed.cost'].create({
            'l10n_mx_edi_customs_number': '15  48  3009  0001234',
            'picking_ids': [Command.link(self.picking_in_1.id)],
            'account_journal_id': self.company_data['default_journal_misc'].id,
        })

        landing_cost.button_validate()
        lot_with_customs = self.picking_in_1.move_line_ids.lot_id.filtered(
            lambda l: l.l10n_mx_edi_customs_number and l.product_id.l10n_mx_edi_use_customs_invoicing
        )

        self.assertEqual(len(lot_with_customs), 1)
        self.assertRecordValues(lot_with_customs, [{
            "l10n_mx_edi_landed_cost_id": landing_cost.id,
            "name": f"{lot_name} / {landing_cost.l10n_mx_edi_customs_number}",
        }])

        other_landing_cost = self.env['stock.landed.cost'].create({
            'l10n_mx_edi_customs_number': '15  48  3009  0001235',
            'picking_ids': [Command.link(self.picking_in_1.id)],
            'account_journal_id': self.company_data['default_journal_misc'].id,
        })
        other_landing_cost.button_validate()

        # If we change the landed cost, the customs number should change which means the name too.
        lot_with_customs.l10n_mx_edi_landed_cost_id = other_landing_cost
        self.assertEqual(lot_with_customs.name, f"{lot_name} / {other_landing_cost.l10n_mx_edi_customs_number}")

        lot_with_customs.l10n_mx_edi_landed_cost_id = False
        self.assertEqual(lot_with_customs.name, lot_name)

    def test_invoice_cfdi_customs(self):
        with self.mx_external_setup(self.frozen_today):
            pickings = self.picking_in_1 | self.picking_in_2
            pickings.action_confirm()
            self.picking_in_1.move_line_ids.write({
                "lot_name": "LOT001",
            })
            self.picking_in_2.move_line_ids.write({
                "lot_name": "LOT002",
            })
            pickings.button_validate()
            with freeze_time("2025-08-15"):
                landed_costs = self.env['stock.landed.cost'].create([
                    {
                        'l10n_mx_edi_customs_number': '15  48  3009  0001234',
                        'picking_ids': [Command.link(self.picking_in_1.id)],
                        'account_journal_id': self.company_data['default_journal_misc'].id,
                    },
                    {
                        'l10n_mx_edi_customs_number': '15  48  3009  0001235',
                        'picking_ids': [Command.link(self.picking_in_2.id)],
                        'account_journal_id': self.company_data['default_journal_misc'].id,
                    }
                ]).sorted("l10n_mx_edi_customs_number")

            landed_costs.button_validate()

            sale = self.env['sale.order'].create({
                'partner_id': self.partner_mx.id,
                'order_line': [
                    (0, 0, {
                        'name': self.product_customs.name,
                        'product_id': self.product_customs.id,
                        'product_uom_qty': 20,
                        'price_unit': 1000,
                    })
                ],
            })

            # New workflow should work even if we disabled config since the line is already created
            self.product_customs.l10n_mx_edi_use_customs_invoicing = False

            sale.action_confirm()
            picking_sale = sale.picking_ids
            picking_sale.action_confirm()
            picking_sale.button_validate()
            # A sales user should be able to create the invoice without triggering an access error
            invoice_1 = sale._create_invoices()

            # Two invoice lines should have been created with
            # '15  48  3009  0001234' and '15  48  3009  0001235' customs numbers and 10 quantity each
            self.assertEqual(len(invoice_1.invoice_line_ids), 2)
            invoice_lines = invoice_1.invoice_line_ids.sorted('l10n_mx_edi_customs_number')
            self.assertRecordValues(invoice_lines, [
                {
                    "l10n_mx_edi_customs_number": "15  48  3009  0001234",
                    "quantity": 10.0,
                },
                {
                    "l10n_mx_edi_customs_number": "15  48  3009  0001235",
                    "quantity": 10.0,
                }
            ])

            invoice_lines[0].quantity = 2
            invoice_1.action_post()
            invoice_2 = sale._create_invoices()

            # Since we reduced the quantity before, there should be 8 units to invoice.
            # Only one line should be created for customs '15  48  3009  0001234' for that quantity
            self.assertEqual(len(invoice_2.invoice_line_ids), 1)
            self.assertRecordValues(invoice_2.invoice_line_ids, [{
                "l10n_mx_edi_customs_number": "15  48  3009  0001234",
                "quantity": 8,
            }])

            invoice_2.action_post()

            with self.with_mocked_pac_sign_success():
                invoice_1._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice_1, 'test_invoice_cfdi_1_customs')

            with self.with_mocked_pac_sign_success():
                invoice_2._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice_2, 'test_invoice_cfdi_2_customs')
