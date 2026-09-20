# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.point_of_sale.tests.common import archive_products
from odoo.addons.pos_urban_piper.models.pos_urban_piper_request import UrbanPiperClient
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestTaxCommonPOS
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestL10nINPosUrbanPiperCommon(TestTaxCommonPOS):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()
        archive_products(cls.env)
        cls.urban_piper_config = cls.env['pos.config'].create({
            'name': 'Urban Piper',
            'module_pos_urban_piper': True,
            'urbanpiper_delivery_provider_ids': [Command.set([cls.env.ref('l10n_in_pos_urban_piper.pos_delivery_provider_zomato').id])],
            'urbanpiper_webhook_url': cls.env['pos.config'].get_base_url()
        })
        cls.taxes_5 = cls.env['account.tax'].create({
            'name': 'GST 5%',
            'amount': 5.00,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'country_id': cls.env.ref('base.in').id,
            'tax_group_id': cls.env['account.tax.group'].create({
                'name': 'GST',
                'country_id': cls.env.ref('base.in').id,
            }).id,
        })
        cls.taxes_18 = cls.env['account.tax'].create({
            'name': 'GST 18%',
            'amount': 18.00,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'country_id': cls.env.ref('base.in').id,
            'tax_group_id': cls.env['account.tax.group'].create({
                'name': 'GST',
                'country_id': cls.env.ref('base.in').id,
            }).id,
        })
        cls.product_1 = cls.env['product.template'].create({
            'name': 'Product 1',
            'available_in_pos': True,
            'taxes_id': cls.taxes_5.ids,
            'type': 'consu',
            'list_price': 100.0,
            'urbanpiper_pos_platform_ids': [Command.set([cls.env.ref('l10n_in_pos_urban_piper.pos_delivery_provider_zomato').id])],
        })
        cls.product_2 = cls.env['product.template'].create({
            'name': 'Product 2',
            'available_in_pos': True,
            'taxes_id': cls.taxes_18.ids,
            'type': 'consu',
            'list_price': 200.0,
            'urbanpiper_pos_platform_ids': [Command.set([cls.env.ref('l10n_in_pos_urban_piper.pos_delivery_provider_zomato').id])],
        })

    def test_l10n_in_tags_included_in_urban_piper_items(self):
        """
        Test that product tags are correctly sent to Urban Piper.
        """
        up = UrbanPiperClient(self.urban_piper_config)
        items = up._prepare_items_data([self.product_1, self.product_2])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['tags'].get('default', []), [])
        self.assertEqual(
            items[1]['tags'].get('default', []),
            ['packaged-good']
        )
