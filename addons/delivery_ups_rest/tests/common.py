# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.delivery.tests.common import DeliveryCommon


class DeliveryUPSCommon(DeliveryCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        shipping_product = cls.env['product.product'].create({
            'name': 'UPS Delivery',
            'type': 'service',
        })

        cls.ups_delivery = cls.env['delivery.carrier'].create({
            'name': 'ups',
            'delivery_type': 'ups_rest',
            'ups_shipper_number': 'mock',
            'ups_client_id': 'mock',
            'ups_client_secret': 'mock',
            'ups_default_service_type': '11',
            'product_id': shipping_product.id,
            'ups_label_file_type': 'ZPL',
            'ups_default_packaging_id': cls.env.ref('delivery_ups_rest.ups_packaging_25').id,  # 10 kg box
        })
