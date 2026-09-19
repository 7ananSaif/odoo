from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.point_of_sale.tests.common_setup_methods import setup_product_combo_items
from odoo import Command, api
from unittest.mock import patch
import odoo.tests


class TestPreparationDisplayHttpCommon(TestPointOfSaleHttpCommon):

    def _get_pdis_url(self, pdis=None):
        pdis = pdis or self.pdis
        return f"/pos_preparation_display/web?display_id={pdis.id}"

    def start_pdis_tour(self, tour_name, login="pos_user", **kwargs):
        self.start_tour(self._get_pdis_url(pdis=kwargs.get('pdis')), tour_name, login=login, **kwargs)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env['pos.prep.display'].search([]).unlink()
        cls.pdis = cls.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, cls.main_pos_config.id)],
        })


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(TestPreparationDisplayHttpCommon):

    def test_01_preparation_display(self):
        self.main_pos_config.write({
            'iface_tipproduct': True,
            'tip_product_id': self.tip.id,
        })

        self.pdis.write({
            'category_ids': [(4, self.letter_tray.pos_categ_ids[0].id)],
        })

        # open a session, the /pos/ui controller will redirect to it
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('PreparationDisplayTour')

        data = self.pdis.get_preparation_display_order(None)

        pdis_line = data['pos.prep.line']

        self.assertEqual(len(pdis_line), 1, "The order has 1 preparation orderline")
        self.assertEqual(pdis_line[0]['product_id'], self.letter_tray.product_variant_id.id, "The preparation orderline has the product " + self.letter_tray.name)

    def test_printer_and_order_display(self):
        self.env['pos.printer'].create({
            'name': 'Printer',
            'printer_type': 'epson_epos',
            'epson_printer_ip': '0.0.0.0',
            'product_categories_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })

        self.main_pos_config.write({
            'is_order_printer': True,
            'printer_ids': [Command.set(self.env['pos.printer'].search([]).ids)],
        })

        self.pdis.write({
            'category_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'PreparationDisplayPrinterTour', login="pos_user")

        order = self.env['pos.order'].search([('amount_paid', '=', 5.28)], limit=1)
        preparation_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)

        self.assertEqual(len(preparation_order.prep_line_ids), 1, "The order " + str(order.amount_paid) + " has 1 preparation orderline")
        self.assertEqual(preparation_order.prep_line_ids.product_id, self.letter_tray.product_variant_id, "The preparation orderline has the product " + self.letter_tray.name)

    def test_02_preparation_display(self):
        self.main_pos_config.write({
            'iface_tipproduct': True,
            'tip_product_id': self.tip.id,
        })
        self.configurable_chair.write({
            'pos_categ_ids': [(4, self.letter_tray.pos_categ_ids[0].id)],
        })

        self.pdis.write({
            'category_ids': [(4, self.configurable_chair.pos_categ_ids[0].id)],
        })

        self.pos_user.write({
            'group_ids': [
                (4, self.env.ref('stock.group_stock_manager').id),
            ]
        })

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_tour("/pos/ui/%d" % self.main_pos_config.id, 'PreparationDisplayTourConfigurableProduct', login="pos_user")

        order = self.env['pos.order'].search([('amount_paid', '=', 11.0)], limit=1)
        preparation_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        prep_line = preparation_order.prep_line_ids[0]
        attribute_names = [attr.name for attr in prep_line.attribute_value_ids]
        self.assertEqual(attribute_names, ['Red', 'Metal', 'Leather'])
        self.assertEqual(prep_line.customer_note, 'Test customer note - orderline')

    def test_03_preparation_display_front_end(self):
        setup_product_combo_items(self)

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('MakePosOrderWithCombo')

        self.start_pdis_tour('PreparationDisplayFrontEndTour')

    def test_sending_order_in_preparation_should_not_sync_more(self):
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.main_pos_config.id)],
        })

        stats = {'nb_call': 0}
        pos_order = self.env.registry.models['pos.order']
        self.main_pos_config.write({
            'is_order_printer': True,
            'printer_ids': [Command.set(self.env['pos.printer'].search([]).ids)],
        })

        @api.model
        def sync_from_ui_patch(self, orders):
            stats['nb_call'] += 1
            return super(pos_order, self).sync_from_ui(orders)

        with patch.object(pos_order, "sync_from_ui", sync_from_ui_patch):
            self.main_pos_config.with_user(self.pos_admin).open_ui()
            self.start_pos_tour('test_sending_order_in_preparation_should_not_sync_more')

        self.assertEqual(stats['nb_call'], 2, "sync_from_ui should be called once")

    def test_preparation_display_filters(self):
        self.pdis.write({
            'category_ids': [(5, 0)]
        })
        self.preset_eat_in = self.env['pos.preset'].create({
            'name': 'Eat in',
        })
        self.preset_takeaway = self.env['pos.preset'].create({
            'name': 'Takeaway',
        })
        self.preset_delivery = self.env['pos.preset'].create({
            'name': 'Delivery',
        })
        resource_calendar = self.env['resource.calendar'].create({
            'name': 'Takeaway',
            'attendance_ids': [(0, 0, {
                'name': 'Takeaway',
                'dayofweek': str(day),
                'hour_from': 0,
                'hour_to': 24,
                'day_period': 'morning',
            }) for day in range(7)],
        })
        self.preset_takeaway.write({
            'use_timing': True,
            'resource_calendar_id': resource_calendar
        })
        self.main_pos_config.write({
            'use_presets': True,
            'default_preset_id': self.preset_eat_in.id,
            'available_preset_ids': [(6, 0, [self.preset_takeaway.id, self.preset_delivery.id])],
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        # Create various orders from POS
        self.start_pos_tour('PosOrderCreationTourPdis', login="pos_user")
        # Check orders visibility on PDIS with filters
        self.start_pdis_tour('PreparationDisplayFilterTour')
